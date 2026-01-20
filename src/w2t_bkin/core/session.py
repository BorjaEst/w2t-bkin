"""Session metadata loading and NWBFile creation.

This module provides functionality to load metadata.toml files and create
pynwb.NWBFile objects with complete metadata. It bridges session configuration
files and NWB file generation.

Key Features:
-------------
- **TOML Loading**: Parse metadata.toml with validation
- **Hierarchical Configuration**: Merge multiple TOML files (global->subject->session)
- **NWBFile Creation**: Convert session metadata to pynwb.NWBFile
- **Subject Metadata**: Full pynwb.file.Subject object creation
- **Device Management**: Create Device objects from config
- **Flexible Input**: Accept Path, str, dict, or list of paths
- **ISO 8601 Support**: Parse datetime strings correctly

Main Functions:
---------------
- load_metadata: Load and merge metadata.toml file(s) hierarchically
- create_nwb_file: Create pynwb.NWBFile from session metadata dictionary
- create_subject: Create pynwb.file.Subject from metadata
- create_device: Create pynwb.device.Device from metadata

Helper Functions:
-----------------
For recursive dictionary merging, see utils.recursive_dict_update()

Requirements:
-------------
- FR-7: NWB file assembly with metadata
- FR-10: Configuration management
- NFR-1: Reproducibility (complete metadata)
- NFR-11: Provenance tracking

Example:
--------
>>> from w2t_bkin.session import load_metadata, create_nwb_file
>>> from pathlib import Path
>>>
>>> # Load session metadata from TOML
>>> session_path = Path("data/raw/Session-000001/metadata.toml")
>>> metadata = load_metadata(session_path)
>>>
>>> # Or load with hierarchical merging
>>> metadata = load_metadata([
...     Path("data/raw/metadata.toml"),              # Global
...     Path("data/raw/subject_01/subject.toml"),    # Subject
...     Path("data/raw/subject_01/session_01/session.toml")  # Session
... ])
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

from w2t_bkin import utils


def build_metadata_paths(
    raw_root: Path,
    subject_id: str,
    session_id: str,
    root_metadata: Optional[Path] = None,
) -> List[Path]:
    """Build ordered list of metadata paths for hierarchical loading.

    Constructs the metadata file path hierarchy from configuration, checking
    for file existence at each level. Only existing files are included.

    Hierarchy order (first to last, later overrides earlier):
    1. root_metadata (if provided) - Lab/project-wide defaults
    2. raw_root/metadata.toml - Experiment-wide settings
    3. raw_root/subject_id/subject.toml - Subject-specific metadata
    4. raw_root/subject_id/session_id/session.toml - Session-specific metadata

    Parameters
    ----------
    raw_root : Path
        Root directory containing raw data
    subject_id : str
        Subject identifier (directory name)
    session_id : str
        Session identifier (directory name)
    root_metadata : Optional[Path], optional
        Path to global metadata file outside raw_root (default: None)

    Returns
    -------
    List[Path]
        Ordered list of existing metadata file paths

    Example
    -------
    >>> from pathlib import Path
    >>> paths = build_metadata_paths(
    ...     raw_root=Path("data/raw"),
    ...     subject_id="subject_01",
    ...     session_id="session_01",
    ...     root_metadata=Path("config/lab_defaults.toml")
    ... )
    >>> print(paths)
    [Path('config/lab_defaults.toml'),
     Path('data/raw/metadata.toml'),
     Path('data/raw/subject_01/subject.toml'),
     Path('data/raw/subject_01/session_01/session.toml')]
    """
    paths = []

    # 1. Root metadata (lab/project-wide defaults)
    if root_metadata is not None:
        root_meta = Path(root_metadata)
        if root_meta.exists():
            paths.append(root_meta)

    # 2. Raw root global metadata (experiment-wide)
    raw_meta = raw_root / "metadata.toml"
    if raw_meta.exists():
        paths.append(raw_meta)

    # 3. Subject metadata
    subject_meta = raw_root / subject_id / "subject.toml"
    if subject_meta.exists():
        paths.append(subject_meta)

    # 4. Session metadata (try session.toml first, then metadata.toml as fallback)
    session_meta = raw_root / subject_id / session_id / "session.toml"
    if session_meta.exists():
        paths.append(session_meta)
    else:
        # Fallback to metadata.toml (synthetic sessions use this name)
        metadata_file = raw_root / subject_id / session_id / "metadata.toml"
        if metadata_file.exists():
            paths.append(metadata_file)

    return paths


def load_metadata(session_path: Union[str, Path, List[Union[str, Path]]]) -> Dict[str, Any]:
    """Load session metadata from TOML file(s) with hierarchical merging.

    Reads and parses metadata from one or more TOML files. When multiple paths
    are provided, configurations are merged hierarchically where later files
    override earlier ones. This enables a cascade configuration pattern:
    - Global metadata (e.g., experiment-wide settings)
    - Subject metadata (e.g., subject-specific information)
    - Session metadata (e.g., session-specific details)

    Nested dictionaries are recursively merged, allowing partial overrides.
    Lists and scalar values are replaced entirely by later configurations.

    Parameters
    ----------
    session_path : Union[str, Path, List[Union[str, Path]]]
        Path to metadata.toml file, or list of paths to merge hierarchically.
        When a list is provided, files are merged in order (first to last),
        with later files taking precedence.

    Returns
    -------
    Dict[str, Any]
        Parsed and merged session metadata dictionary

    Raises
    ------
    FileNotFoundError
        If any metadata file does not exist
    ValueError
        If TOML is invalid or malformed

    Example
    -------
    >>> # Single file
    >>> metadata = load_metadata("Session-000001/metadata.toml")
    >>> print(metadata["identifier"])
    Session-000001

    >>> # Hierarchical merge: global -> subject -> session
    >>> metadata = load_metadata([
    ...     "data/raw/metadata.toml",          # Global settings
    ...     "data/raw/subject_01/subject.toml", # Subject info
    ...     "data/raw/subject_01/session_01/session.toml"  # Session specifics
    ... ])
    >>> # Session-specific values override subject and global values
    """
    # Normalize input to list of paths
    if isinstance(session_path, (str, Path)):
        paths = [Path(session_path)]
    else:
        paths = [Path(p) for p in session_path]

    # Start with empty metadata dictionary
    metadata: Dict[str, Any] = {}

    # Load and merge each configuration file in order
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Metadata file not found: {path}")

        # Load TOML file using utils for consistency
        file_data = utils.read_toml(path)

        # Recursively merge into accumulated metadata
        utils.recursive_dict_update(metadata, file_data)

    return metadata


def create_nwb_file(metadata: Dict[str, Any]) -> NWBFile:
    """Create NWBFile object from session metadata dictionary.

    Parameters
    ----------
    metadata : Dict[str, Any]
        Session metadata dictionary (from load_metadata())

    Returns
    -------
    NWBFile
        Configured NWBFile object

    Example
    -------
    >>> # Load metadata first, then create NWBFile
    >>> metadata = load_metadata("Session-000001/metadata.toml")
    >>> nwbfile = create_nwb_file(metadata)
    >>>
    >>> # Or with hierarchical merge
    >>> metadata = load_metadata([
    ...     "data/raw/metadata.toml",
    ...     "data/raw/subject_01/subject.toml",
    ...     "data/raw/subject_01/session_01/session.toml"
    ... ])
    >>> nwbfile = create_nwb_file(metadata)
    """
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

    # Add cameras as devices if provided (and not already added)
    if "cameras" in metadata:
        for camera_info in metadata["cameras"]:
            # Check if device with this name already exists
            if camera_info["id"] not in nwbfile.devices:
                # Create device info from camera info
                device_info = {"name": camera_info["id"], "description": camera_info.get("description", "Camera device"), "manufacturer": "unknown"}
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
    frame_counts: Optional[List[int]] = None,
) -> NWBFile:
    """Add video ImageSeries to NWBFile acquisition.

    Creates an ImageSeries object with external video file links (videos are not
    embedded in the NWB file) and adds it to the acquisition section. Uses
    rate-based timing for efficiency.

    Supports multiple video files per camera (e.g., split recordings, experiment pauses).
    When multiple files are provided, computes starting_frame indices by counting frames
    in each video file sequentially.

    Parameters
    ----------
    nwbfile : NWBFile
        NWBFile object to add acquisition to
    camera_id : str
        Camera identifier (becomes ImageSeries name)
    video_files : List[str]
        List of absolute paths to video files (in correct order)
    frame_rate : float, optional
        Video frame rate in Hz (default: 30.0)
    device : Device, optional
        pynwb Device object representing the camera
    frame_counts : List[int], optional
        Frame count for each video file (if None, will count frames - slower)

    Returns
    -------
    NWBFile
        Updated NWBFile object (same as input, modified in place)

    Example
    -------
    >>> from w2t_bkin.session import create_nwb_file, add_video_acquisition, load_metadata
    >>> metadata = load_metadata("metadata.toml")
    >>> nwbfile = create_nwb_file(metadata)
    >>> nwbfile = add_video_acquisition(
    ...     nwbfile,
    ...     camera_id="camera_0",
    ...     video_files=["/path/to/video1.avi", "/path/to/video2.avi"],
    ...     frame_rate=30.0,
    ...     frame_counts=[30, 25]  # Optional, avoids recounting
    ... )
    >>> print(nwbfile.acquisition["camera_0"])
    """

    # For multiple video files, compute starting_frame indices
    # PyNWB requires starting_frame array when external_file has multiple files
    starting_frame = None
    if len(video_files) > 1:
        # Get frame counts (either provided or count now)
        if frame_counts is None or not frame_counts:
            raise ValueError(
                f"Frame counts required for multi-file ImageSeries '{camera_id}' with {len(video_files)} files. " "This should have been computed during the discovery phase."
            )

        # starting_frame[i] is the cumulative frame count up to file i
        # e.g., files with [30, 25, 40] frames -> starting_frame = [0, 30, 55]
        starting_frame = [0]
        for i in range(len(frame_counts) - 1):
            starting_frame.append(starting_frame[-1] + frame_counts[i])

    image_series = ImageSeries(
        name=camera_id,
        external_file=video_files,
        format="external",
        rate=frame_rate,
        starting_time=0.0,
        starting_frame=starting_frame,  # None for single file, array for multiple
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
    >>> from w2t_bkin.session import create_nwb_file, write_nwb_file, load_metadata
    >>> from pathlib import Path
    >>>
    >>> metadata = load_metadata("metadata.toml")
    >>> nwbfile = create_nwb_file(metadata)
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
