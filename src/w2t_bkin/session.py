"""Session metadata loading and NWBFile creation.

This module provides functionality to load session.toml files and create
pynwb.NWBFile objects with complete metadata. It bridges session configuration
files and NWB file generation.

Key Features:
-------------
- **TOML Loading**: Parse session.toml with validation
- **NWBFile Creation**: Convert session metadata to pynwb.NWBFile
- **Subject Metadata**: Full pynwb.file.Subject object creation
- **Device Management**: Create Device objects from config
- **Flexible Input**: Accept Path, str, or dict
- **ISO 8601 Support**: Parse datetime strings correctly

Main Functions:
---------------
- load_session_metadata: Load and parse session.toml file
- create_nwb_file: Create pynwb.NWBFile from session metadata
- create_subject: Create pynwb.file.Subject from metadata
- create_devices: Create Device objects from device list

Requirements:
-------------
- FR-7: NWB file assembly with metadata
- FR-10: Configuration management
- NFR-1: Reproducibility (complete metadata)
- NFR-11: Provenance tracking

Example:
--------
>>> from w2t_bkin.session import load_session_metadata, create_nwb_file
>>> from pathlib import Path
>>>
>>> # Load session metadata from TOML
>>> session_path = Path("data/raw/Session-000001/session.toml")
>>> metadata = load_session_metadata(session_path)
>>>
>>> # Create NWBFile object
>>> nwbfile = create_nwb_file(metadata)
>>> print(f"Session: {nwbfile.session_id}")
>>> print(f"Subject: {nwbfile.subject.subject_id}")
"""

# TODO: lab_meta_data create NWB extension to hold lab-specific metadata

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pynwb import NWBHDF5IO, NWBFile
from pynwb.device import Device, DeviceModel
from pynwb.file import Subject
from pynwb.image import ImageSeries
import tomli

from w2t_bkin import utils


def load_session_metadata(session_path: Union[str, Path]) -> Dict[str, Any]:
    """Load session metadata from TOML file.

    Reads and parses a session.toml file containing NWB metadata.

    Parameters
    ----------
    session_path : Union[str, Path]
        Path to session.toml file

    Returns
    -------
    Dict[str, Any]
        Parsed session metadata dictionary

    Raises
    ------
    FileNotFoundError
        If session.toml does not exist
    ValueError
        If TOML is invalid or malformed

    Example
    -------
    >>> metadata = load_session_metadata("Session-000001/session.toml")
    >>> print(metadata["identifier"])
    Session-000001
    """
    session_path = Path(session_path)

    if not session_path.exists():
        raise FileNotFoundError(f"Session file not found: {session_path}")

    with open(session_path, "rb") as f:
        metadata = tomli.load(f)

    return metadata


def create_nwb_file(session_file: Union[str, Path]) -> NWBFile:
    """Create NWBFile object from session metadata.

    Example
    -------
    >>> # From file path
    >>> nwbfile = create_nwb_file("Session-000001/session.toml")
    >>>
    >>> # From metadata dict
    >>> metadata = {"identifier": "S001", "session_start_time": "2025-01-15T14:30:00", ...}
    >>> nwbfile = create_nwb_file(metadata)
    """
    # Load metadata if path provided
    metadata = load_session_metadata(session_file)

    # Create NWBFile with all metadata
    nwbfile = NWBFile(
        session_description=metadata.get("session_description"),
        identifier=metadata.get("identifier"),
        session_start_time=utils.parse_datetime(metadata["session_start_time"]) if "session_start_time" in metadata else None,
        timestamps_reference_time=utils.parse_datetime(metadata["timestamps_reference_time"]) if "timestamps_reference_time" in metadata else None,
        experimenter=metadata.get("experimenter", None),
        experiment_description=metadata.get("experiment_description", None),
        session_id=metadata.get("session_id", None),
        institution=metadata.get("institution", None),
        keywords=metadata.get("keywords", None),
        notes=metadata.get("notes", None),
        pharmacology=metadata.get("pharmacology", None),
        protocol=metadata.get("protocol", None),
        related_publications=metadata.get("related_publications", None),
        slices=metadata.get("slices", None),
        source_script=utils.get_source_script(),
        source_script_file_name=utils.get_source_script_file_name(),
        was_generated_by=utils.get_software_packages(),
        data_collection=metadata.get("data_collection", None),
        surgery=metadata.get("surgery", None),
        virus=metadata.get("virus", None),
        stimulus_notes=metadata.get("stimulus_notes", None),
        lab=metadata.get("lab", None),
    )

    # Add subject if provided
    if "subject" in metadata:
        nwbfile.subject = create_subject(metadata["subject"])

    # Add devices if provided
    if "devices" in metadata:
        for device_info in metadata["devices"]:
            nwbfile.add_device(create_device(device_info))

    # Add electrode groups if provided
    if "electrode_groups" in metadata:
        for eg_info in metadata["electrode_groups"]:
            pass
            # TODO: implement create_electrode_group function

    if "imaging_planes" in metadata:
        for ip_info in metadata["imaging_planes"]:
            pass
            # TODO: implement create_imaging_plane function

    if "ogen_sites" in metadata:
        for os_info in metadata["ogen_sites"]:
            pass
            # TODO: implement create_ogen_site function

    if "processing_modules" in metadata:
        for pm_info in metadata["processing_modules"]:
            pass
            # TODO: implement create_processing_module function

    return nwbfile


def create_subject(subject_data: Dict[str, Any]) -> Subject:
    """Create pynwb.file.Subject object from metadata dictionary.

    Constructs a Subject object with all standard NWB subject fields including
    demographics, genotype information, and date of birth.

    Parameters
    ----------
    subject_data : Dict[str, Any]
        Dictionary containing subject metadata with optional fields:
        - age: Age of subject (e.g., "P90D" for 90 days)
        - age__reference: Reference point for age (default: "birth")
        - description: Free-form text description
        - genotype: Genetic strain designation
        - sex: Sex of subject (e.g., "M", "F", "U")
        - species: Species name (e.g., "Mus musculus")
        - subject_id: Unique identifier for subject
        - weight: Weight of subject
        - date_of_birth: ISO 8601 datetime string
        - strain: Genetic strain name

    Returns
    -------
    Subject
        Configured pynwb.file.Subject object

    Example
    -------
    >>> subject_data = {
    ...     "subject_id": "M001",
    ...     "species": "Mus musculus",
    ...     "sex": "M",
    ...     "age": "P90D",
    ...     "date_of_birth": "2024-10-15T00:00:00"
    ... }
    >>> subject = create_subject(subject_data)
    >>> print(subject.subject_id)
    M001
    """
    return Subject(
        age=subject_data.get("age", None),
        age__reference=subject_data.get("age__reference", "birth"),
        description=subject_data.get("description", None),
        genotype=subject_data.get("genotype", None),
        sex=subject_data.get("sex", None),
        species=subject_data.get("species", None),
        subject_id=subject_data.get("subject_id", None),
        weight=subject_data.get("weight", None),
        date_of_birth=utils.parse_datetime(subject_data["date_of_birth"]) if "date_of_birth" in subject_data else None,
        strain=subject_data.get("strain", None),
    )


def create_device(device_info: Dict[str, Any]) -> Device:
    """Create pynwb.device.Device object from metadata dictionary.

    Constructs a Device object representing physical hardware used in the experiment,
    such as cameras, behavioral apparatus, or recording equipment.

    Parameters
    ----------
    device_info : Dict[str, Any]
        Dictionary containing device metadata:
        - name: Unique device name (required)
        - description: Text description of device (optional)
        - serial_number: Serial number or identifier (optional)
        - manufacturer: Manufacturer name (optional)
        - model: Dictionary with model information (optional):
            - model_name: Name of device model (required if model provided)
            - manufacturer: Model manufacturer (optional)
            - model_number: Model number/version (optional)
            - description: Model description (optional)

    Returns
    -------
    Device
        Configured pynwb.device.Device object

    Example
    -------
    >>> device_info = {
    ...     "name": "Camera_Top",
    ...     "description": "Top-view behavioral camera",
    ...     "manufacturer": "FLIR",
    ...     "serial_number": "FL-12345",
    ...     "model": {
    ...         "model_name": "Blackfly S BFS-U3-31S4M",
    ...         "model_number": "BFS-U3-31S4M-C"
    ...     }
    ... }
    >>> device = create_device(device_info)
    >>> print(device.name)
    Camera_Top
    """
    return Device(
        name=device_info["name"],
        description=device_info.get("description", None),
        serial_number=device_info.get("serial_number", None),
        manufacturer=device_info.get("manufacturer", None),
        model=device_model(device_info["model"]) if "model" in device_info else None,
    )


def device_model(device_info: Dict[str, Any]) -> DeviceModel:
    """Create pynwb.device.DeviceModel object from metadata dictionary.

    Constructs a DeviceModel object representing the specific model/version
    of a hardware device used in the experiment.

    Parameters
    ----------
    device_info : Dict[str, Any]
        Dictionary containing device model metadata:
        - model_name: Name of device model (required)
        - manufacturer: Manufacturer name (optional)
        - model_number: Model number or version identifier (optional)
        - description: Text description of the model (optional)

    Returns
    -------
    DeviceModel
        Configured pynwb.device.DeviceModel object

    Example
    -------
    >>> model_info = {
    ...     "model_name": "Blackfly S BFS-U3-31S4M",
    ...     "manufacturer": "FLIR",
    ...     "model_number": "BFS-U3-31S4M-C",
    ...     "description": "3.1 MP USB3 monochrome camera"
    ... }
    >>> model = device_model(model_info)
    >>> print(model.name)
    Blackfly S BFS-U3-31S4M
    """
    return DeviceModel(
        name=device_info["model_name"],
        manufacturer=device_info.get("manufacturer", None),
        model_number=device_info.get("model_number", None),
        description=device_info.get("description", None),
    )


# =============================================================================
# NWB File Writing and Acquisition
# =============================================================================


def add_video_acquisition(
    nwbfile: NWBFile,
    camera_id: str,
    video_files: List[str],
    frame_rate: float = 30.0,
    device: Optional[Device] = None,
) -> NWBFile:
    """Add video ImageSeries to NWBFile acquisition.

    Creates an ImageSeries object with external video file links (videos are not
    embedded in the NWB file) and adds it to the acquisition section. Uses
    rate-based timing for efficiency.

    Parameters
    ----------
    nwbfile : NWBFile
        NWBFile object to add acquisition to
    camera_id : str
        Camera identifier (becomes ImageSeries name)
    video_files : List[str]
        List of absolute paths to video files
    frame_rate : float, optional
        Video frame rate in Hz (default: 30.0)
    device : Device, optional
        pynwb Device object representing the camera

    Returns
    -------
    NWBFile
        Updated NWBFile object (same as input, modified in place)

    Example
    -------
    >>> from w2t_bkin.session import create_nwb_file, add_video_acquisition
    >>> nwbfile = create_nwb_file("session.toml")
    >>> nwbfile = add_video_acquisition(
    ...     nwbfile,
    ...     camera_id="camera_0",
    ...     video_files=["/path/to/video1.avi", "/path/to/video2.avi"],
    ...     frame_rate=30.0
    ... )
    >>> print(nwbfile.acquisition["camera_0"])
    """

    image_series = ImageSeries(
        name=camera_id,
        external_file=video_files,
        format="external",
        rate=frame_rate,
        starting_time=0.0,
        unit="n/a",
        device=device,
    )

    nwbfile.add_acquisition(image_series)
    return nwbfile


def write_nwb_file(nwbfile: NWBFile, output_path: Path) -> Path:
    """Write NWBFile to disk using NWBHDF5IO.

    Serializes an in-memory NWBFile object to an HDF5 file on disk.
    Creates parent directories if needed.

    Parameters
    ----------
    nwbfile : NWBFile
        NWBFile object to write
    output_path : Path
        Output file path (should end with .nwb)

    Returns
    -------
    Path
        Path to written NWB file (same as output_path)

    Raises
    ------
    IOError
        If file cannot be written

    Example
    -------
    >>> from w2t_bkin.session import create_nwb_file, write_nwb_file
    >>> from pathlib import Path
    >>>
    >>> nwbfile = create_nwb_file("session.toml")
    >>> output_path = Path("output/session.nwb")
    >>> write_nwb_file(nwbfile, output_path)
    >>> print(f"Written: {output_path}")
    """

    # Ensure parent directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write NWBFile
    with NWBHDF5IO(str(output_path), "w") as io:
        io.write(nwbfile)

    return output_path
