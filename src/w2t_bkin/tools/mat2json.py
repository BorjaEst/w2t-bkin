#!/usr/bin/env python3
"""MATLAB to JSON Converter

Converts MATLAB .mat files to JSON format with proper handling of nested structures,
arrays, and MATLAB-specific objects.

This module provides a converter that properly recovers Python dictionaries from mat files,
handling mat-objects that scipy.io.loadmat doesn't properly convert by default.

Original MATLAB loading logic credit: Nora
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict

import numpy as np
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import scipy.io
from scipy.io.matlab import mat_struct


class ConverterSettings(BaseSettings):
    """Configuration settings for MATLAB to JSON conversion.

    Attributes:
        input_file: Path to the input .mat file to convert
        output_file: Path to the output JSON file (default: same name as input with .json extension)
        indent: Number of spaces for JSON indentation (default: 4)
        verbose: Enable verbose output during conversion
    """

    model_config = SettingsConfigDict(cli_parse_args=True)

    input_file: Path = Field(..., description="Path to the input .mat file")
    output_file: Path | None = Field(None, description="Path to the output JSON file")
    indent: int = Field(4, description="JSON indentation spaces", ge=0, le=8)
    verbose: bool = Field(False, description="Enable verbose output")

    @field_validator("input_file")
    @classmethod
    def validate_input_file(cls, v: Path) -> Path:
        """Validate that the input file exists and has .mat extension."""
        if not v.exists():
            raise ValueError(f"Input file does not exist: {v}")
        if not v.is_file():
            raise ValueError(f"Input path is not a file: {v}")
        if v.suffix.lower() != ".mat":
            raise ValueError(f"Input file must have .mat extension, got: {v.suffix}")
        return v

    @model_validator(mode="after")
    def set_default_output(self) -> ConverterSettings:
        """Set default output filename based on input filename if not provided."""
        if self.output_file is None:
            self.output_file = self.input_file.with_suffix(".json")
        return self


class MatlabObjectConverter:
    """Converts MATLAB objects to Python dictionaries and arrays.

    This converter handles the complexities of MATLAB's mat_struct objects
    and nested cell arrays, recursively transforming them into native Python
    data structures suitable for JSON serialization.
    """

    @staticmethod
    def _check_vars(data: Dict[str, Any]) -> Dict[str, Any]:
        """Check and convert mat-objects in dictionary entries.

        Args:
            data: Dictionary potentially containing mat-objects

        Returns:
            Dictionary with all mat-objects converted to nested dictionaries
        """
        for key in data:
            if isinstance(data[key], mat_struct):
                data[key] = MatlabObjectConverter._to_dict(data[key])
            elif isinstance(data[key], np.ndarray):
                data[key] = MatlabObjectConverter._to_array(data[key])
        return data

    @staticmethod
    def _to_dict(mat_obj: mat_struct) -> Dict[str, Any]:
        """Recursively convert MATLAB mat_struct to nested dictionary.

        Args:
            mat_obj: MATLAB mat_struct object

        Returns:
            Nested dictionary representation of the mat_struct
        """
        result = {}
        for field_name in mat_obj._fieldnames:
            elem = mat_obj.__dict__[field_name]
            if isinstance(elem, mat_struct):
                result[field_name] = MatlabObjectConverter._to_dict(elem)
            elif isinstance(elem, np.ndarray):
                result[field_name] = MatlabObjectConverter._to_array(elem)
            else:
                result[field_name] = elem
        return result

    @staticmethod
    def _to_array(ndarray: np.ndarray) -> np.ndarray | list:
        """Recursively convert MATLAB cell arrays to Python lists/arrays.

        Args:
            ndarray: NumPy array potentially containing mat-objects

        Returns:
            Converted array with mat-objects transformed to dictionaries
        """
        if ndarray.dtype != "float64":
            elem_list = []
            for sub_elem in ndarray:
                if isinstance(sub_elem, mat_struct):
                    elem_list.append(MatlabObjectConverter._to_dict(sub_elem))
                elif isinstance(sub_elem, np.ndarray):
                    elem_list.append(MatlabObjectConverter._to_array(sub_elem))
                else:
                    elem_list.append(sub_elem)
            return np.array(elem_list, dtype="object")
        return ndarray

    @classmethod
    def load_mat(cls, filename: Path) -> Dict[str, Any]:
        """Load MATLAB .mat file and convert to nested Python dictionary.

        This method should be used instead of direct scipy.io.loadmat as it
        properly handles mat-objects that aren't automatically converted.

        Args:
            filename: Path to the .mat file

        Returns:
            Nested dictionary representation of the MATLAB data

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file cannot be loaded
        """
        if not filename.exists():
            raise FileNotFoundError(f"File not found: {filename}")

        try:
            data = scipy.io.loadmat(str(filename), struct_as_record=False, squeeze_me=True)
            return cls._check_vars(data)
        except Exception as e:
            raise ValueError(f"Failed to load MATLAB file: {e}") from e


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for NumPy and bytes types."""

    def default(self, obj: Any) -> Any:
        """Convert NumPy and bytes types to JSON-serializable types.

        Args:
            obj: Object to serialize

        Returns:
            JSON-serializable representation of the object
        """
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, bytes):
            # Try to decode bytes as UTF-8, fallback to base64 encoding
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                import base64

                return {"__type__": "bytes", "data": base64.b64encode(obj).decode("ascii")}
        return super().default(obj)


class MatToJsonConverter:
    """High-level converter orchestrating MATLAB to JSON conversion."""

    def __init__(self, settings: ConverterSettings):
        """Initialize the converter with settings.

        Args:
            settings: Configuration settings for the conversion
        """
        self.settings = settings
        self.converter = MatlabObjectConverter()

    def convert(self) -> None:
        """Execute the conversion from MATLAB to JSON.

        Raises:
            Exception: If conversion fails at any stage
        """
        if self.settings.verbose:
            print(f"Loading MATLAB file: {self.settings.input_file}")

        # Load and convert MATLAB data
        mat_data = self.converter.load_mat(self.settings.input_file)

        if self.settings.verbose:
            print(f"Loaded {len(mat_data)} top-level keys")
            print(f"Writing JSON to: {self.settings.output_file}")

        # Write JSON output
        with open(self.settings.output_file, "w", encoding="utf-8") as f:
            json.dump(mat_data, f, indent=self.settings.indent, cls=JSONEncoder)

        if self.settings.verbose:
            print(f"✓ Conversion complete: {self.settings.output_file}")


def main() -> int:
    """Main entry point for the converter.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        settings = ConverterSettings()
        converter = MatToJsonConverter(settings)
        converter.convert()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
