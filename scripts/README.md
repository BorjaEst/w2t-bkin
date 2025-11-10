# Scripts

This directory contains utility scripts for the W2T Body Kinematics project.

## mat2json.py

**MATLAB to JSON Converter** - Converts MATLAB .mat files to JSON format with proper handling of nested structures, arrays, and MATLAB-specific objects.

### Features

- **OOP Design**: Follows object-oriented best practices with clear separation of concerns
- **Pydantic Settings**: Uses `pydantic-settings` for configuration and CLI argument parsing
- **Type Safety**: Full type hints throughout the codebase
- **Validation**: Automatic validation of input files (existence, file type)
- **Flexible Output**: Auto-generates output filename or accepts custom path
- **Environment Variables**: Supports configuration via environment variables with `MAT2JSON_` prefix
- **Custom JSON Encoder**: Handles NumPy types, bytes, and MATLAB-specific objects

### Usage

#### Basic Usage

Convert a .mat file to JSON (output file will have same name with .json extension):

```bash
python scripts/mat2json.py --input_file path/to/file.mat
```

#### With Verbose Output

```bash
python scripts/mat2json.py --input_file path/to/file.mat --verbose True
```

#### Custom Output File

```bash
python scripts/mat2json.py --input_file path/to/file.mat --output_file path/to/output.json
```

#### Custom Indentation

```bash
python scripts/mat2json.py --input_file path/to/file.mat --indent 2
```

#### Using Environment Variables

```bash
export MAT2JSON_INPUT_FILE="path/to/file.mat"
export MAT2JSON_OUTPUT_FILE="path/to/output.json"
export MAT2JSON_INDENT=2
export MAT2JSON_VERBOSE=True
python scripts/mat2json.py
```

### Configuration Options

| Option          | Type | Default        | Description                                 |
| --------------- | ---- | -------------- | ------------------------------------------- |
| `--input_file`  | Path | _required_     | Path to the input .mat file                 |
| `--output_file` | Path | `<input>.json` | Path to the output JSON file                |
| `--indent`      | int  | 4              | Number of spaces for JSON indentation (0-8) |
| `--verbose`     | bool | False          | Enable verbose output during conversion     |

### Architecture

The script is organized into four main classes:

1. **ConverterSettings**: Pydantic settings model for configuration management

   - Validates input file existence and format
   - Auto-generates output filename if not provided
   - Supports environment variable configuration

2. **MatlabObjectConverter**: Low-level converter for MATLAB objects

   - Recursively converts `mat_struct` objects to Python dictionaries
   - Handles nested arrays and cell arrays
   - Preserves data structure and hierarchy

3. **JSONEncoder**: Custom JSON encoder

   - Serializes NumPy integer and floating-point types
   - Converts NumPy arrays to lists
   - Handles bytes objects (UTF-8 decode or base64 encoding)

4. **MatToJsonConverter**: High-level orchestrator
   - Coordinates the conversion process
   - Manages file I/O operations
   - Provides user feedback based on verbosity setting

### Example

```python
# As a module
from pathlib import Path
from scripts.mat2json import MatlabObjectConverter

# Load MATLAB file
mat_data = MatlabObjectConverter.load_mat(Path("data.mat"))

# Process the data
print(mat_data.keys())
```

### Error Handling

The script provides clear error messages for common issues:

- Input file doesn't exist
- Input file is not a .mat file
- MATLAB file cannot be loaded
- JSON serialization errors

### Original Credit

Original MATLAB loading logic by Nora, refactored to follow modern Python and OOP best practices.
