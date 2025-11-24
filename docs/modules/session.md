# Session Module - NWBFile Creation from TOML

The `session` module provides functionality to load session metadata from TOML files and create `pynwb.NWBFile` objects with complete metadata.

## Features

- **TOML Loading**: Parse `session.toml` files with validation
- **NWBFile Creation**: Convert session metadata to `pynwb.NWBFile` objects
- **Subject Metadata**: Full `pynwb.file.Subject` object creation
- **Device Management**: Create Device objects from configuration
- **Flexible Input**: Accept Path, str, or dict
- **ISO 8601 Support**: Parse datetime strings correctly

## Quick Start

```python
from pathlib import Path
from w2t_bkin.session import create_nwb_file

# Create NWBFile from session.toml
session_path = Path("data/raw/Session-000001/session.toml")
nwbfile = create_nwb_file(session_path)

# Access metadata
print(f"Session: {nwbfile.session_id}")
print(f"Subject: {nwbfile.subject.subject_id}")
print(f"Devices: {list(nwbfile.devices.keys())}")
```

## Main Functions

### `load_session_metadata(session_path)`

Load and parse a `session.toml` file.

**Parameters:**

- `session_path` (str | Path): Path to session.toml file

**Returns:**

- `dict`: Parsed session metadata

**Example:**

```python
from w2t_bkin.session import load_session_metadata

metadata = load_session_metadata("Session-000001/session.toml")
print(metadata["identifier"])  # "Session-000001"
```

---

### `create_nwb_file(metadata, add_devices=True)`

Create an NWBFile object from session metadata.

**Parameters:**

- `metadata` (dict | str | Path): Session metadata or path to session.toml
- `add_devices` (bool): Whether to add devices to NWBFile (default: True)

**Returns:**

- `NWBFile`: Configured pynwb.NWBFile object

**Example:**

```python
from w2t_bkin.session import create_nwb_file

# From file path
nwbfile = create_nwb_file("Session-000001/session.toml")

# From metadata dict
metadata = {
    "identifier": "S001",
    "session_description": "Test session",
    "session_start_time": "2025-01-15T14:30:00",
}
nwbfile = create_nwb_file(metadata)
```

---

### `create_subject(subject_data)`

Create a pynwb Subject object from metadata.

**Parameters:**

- `subject_data` (dict): Subject metadata dictionary

**Returns:**

- `Subject`: pynwb Subject object

**Example:**

```python
from w2t_bkin.session import create_subject

subject_data = {
    "subject_id": "M001",
    "species": "Mus musculus",
    "sex": "M",
    "age": "P84D",
}
subject = create_subject(subject_data)
```

---

### `create_devices(devices_data)`

Create Device objects from device metadata list.

**Parameters:**

- `devices_data` (list[dict]): List of device metadata dictionaries

**Returns:**

- `dict[str, Device]`: Dictionary mapping device names to Device objects

**Example:**

```python
from w2t_bkin.session import create_devices

devices_data = [
    {"name": "camera_0", "description": "Overhead camera"},
    {"name": "bpod", "description": "Behavioral control"},
]
devices = create_devices(devices_data)
```

---

### `get_nwb_metadata_summary(nwbfile)`

Extract summary of metadata from NWBFile.

**Parameters:**

- `nwbfile` (NWBFile): NWBFile object to summarize

**Returns:**

- `dict`: Summary dictionary with key metadata fields

**Example:**

```python
from w2t_bkin.session import create_nwb_file, get_nwb_metadata_summary

nwbfile = create_nwb_file("Session-000001/session.toml")
summary = get_nwb_metadata_summary(nwbfile)
print(summary["session_id"])  # "000001"
```

## session.toml Structure

The `session.toml` file should follow the NWBFile specification structure:

```toml
# Required fields
session_description = "Description of the session"
identifier = "Session-000001"
session_start_time = "2025-01-15T14:30:00"

# Optional metadata
session_id = "000001"
experimenter = ["Experimenter Name"]
institution = "Institution Name"
lab = "Lab Name"
keywords = ["keyword1", "keyword2"]

# Subject information
[subject]
subject_id = "M001"
species = "Mus musculus"
sex = "M"
age = "P84D"

# Devices
[[devices]]
name = "camera_0"
description = "Overhead camera"
manufacturer = "FLIR"
```

See `data/raw/Session-000001/session.toml` for a complete example.

## Complete Workflow

```python
from pathlib import Path
from pynwb import NWBHDF5IO
from w2t_bkin.session import (
    load_session_metadata,
    create_nwb_file,
    get_nwb_metadata_summary,
)

# 1. Load metadata
session_path = Path("data/raw/Session-000001/session.toml")
metadata = load_session_metadata(session_path)

# 2. Create NWBFile
nwbfile = create_nwb_file(metadata)

# 3. Get summary
summary = get_nwb_metadata_summary(nwbfile)
print(f"Session: {summary['session_id']}")
print(f"Subject: {summary['subject']['subject_id']}")

# 4. Save to file
output_path = Path("output/session.nwb")
with NWBHDF5IO(str(output_path), mode="w") as io:
    io.write(nwbfile)

# 5. Read and verify
with NWBHDF5IO(str(output_path), mode="r") as io:
    read_nwbfile = io.read()
    print(f"Identifier: {read_nwbfile.identifier}")
```

## Testing

Run the unit tests:

```bash
pytest tests/unit/test_session.py -v
```

Run the example script:

```bash
python examples/create_nwb_from_session.py
```

## Integration with Pipeline

The session module integrates with the existing pipeline:

```python
from w2t_bkin import config, session, nwb

# Load configuration
cfg = config.load_config("config.toml")

# Create NWBFile from session metadata
nwbfile = session.create_nwb_file("Session-000001/session.toml")

# Add acquisition data (videos, pose, etc.)
# ... (using existing nwb module functions)

# Save final NWB file
# ... (using pynwb)
```

## Dependencies

- `pynwb>=2.8.0`: NWB file creation
- `tomli>=2.0.0`: TOML parsing
- `hdmf>=3.14.0`: Data format handling

## Notes

- Datetime strings support ISO 8601 format: `YYYY-MM-DDTHH:MM:SS`
- Missing timezone information will trigger warnings but will be auto-corrected
- The `was_generated_by` field is handled gracefully for different pynwb versions
- All NWBFile fields from the specification are supported

## References

- [NWBFile Documentation](https://pynwb.readthedocs.io/en/stable/pynwb.file.html#pynwb.file.NWBFile)
- [Subject Documentation](https://pynwb.readthedocs.io/en/stable/pynwb.file.html#pynwb.file.Subject)
- [Device Documentation](https://pynwb.readthedocs.io/en/stable/pynwb.device.html)
