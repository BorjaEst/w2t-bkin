# Metadata Parameters Guide

This document describes metadata parameters for the w2t-bkin pipeline. Metadata describes **WHAT** your experimental data looks like.

> **Note**: For pipeline processing parameters (verification, preprocessing), see [Configuration Parameters Guide](configuration-parameters.md).

## Metadata vs Configuration

- **Metadata** (`.toml` files in `data/raw/`): Data description and NWB metadata

  - Examples: Camera paths, TTL channels, Bpod sync mappings, subject info
  - Location: Hierarchical files in raw data directory
  - Scope: Experiment/subject/session specific

- **Configuration (`config.toml`)**: Pipeline behavior and processing parameters
  - Examples: `force_rerun`, `gpu_index`, `check_sync_mismatch`
  - Location: Project root or specified via `--config` flag
  - Scope: Project-wide processing behavior
  - See: [Configuration Parameters Guide](configuration-parameters.md)

## Table of Contents

- [Metadata File Hierarchy](#metadata-file-hierarchy)
- [NWB Metadata Fields](#nwb-metadata-fields)
- [Camera Configuration](#camera-configuration)
- [TTL Configuration](#ttl-configuration)
- [Bpod Configuration](#bpod-configuration)
- [Bpod Trial Synchronization](#bpod-trial-synchronization)
- [Device Configuration](#device-configuration)
- [Subject Information](#subject-information)
- [Session Information](#session-information)
- [Complete Examples](#complete-examples)

---

## Metadata File Hierarchy

Metadata is loaded in hierarchical layers, with later layers overriding earlier ones:

### Loading Order

1. **Root metadata**: `config.paths.root_metadata` (if specified in config.toml)
2. **Experiment metadata**: `{raw_root}/metadata.toml` (if exists)
3. **Subject metadata**: `{raw_root}/{subject_id}/subject.toml` (if exists)
4. **Session metadata**: `{raw_root}/{subject_id}/{session_id}/session.toml` (if exists)

### When to Use Each Level

**Root metadata** (`config.paths.root_metadata`):

- Lab-wide defaults shared across all experiments
- Standard equipment configurations
- Common analysis parameters

**Experiment metadata** (`data/raw/metadata.toml`):

- Equipment and setup shared across all subjects/sessions in this experiment
- Common camera configurations
- Common TTL channel definitions
- Experiment description and metadata

**Subject metadata** (`data/raw/{subject}/subject.toml`):

- Subject-specific information (age, weight, genotype)
- Subject description
- Overrides that apply to all sessions for this subject

**Session metadata** (`data/raw/{subject}/{session}/session.toml`):

- Session-specific information (start time, experimenter, description)
- Equipment changes for this specific session
- Per-session overrides

### Directory Structure Example

```text
data/raw/
├── metadata.toml                    # Experiment-wide defaults
├── subject-001/
│   ├── subject.toml                # Subject info
│   ├── session_20251120/
│   │   ├── session.toml            # Session-specific metadata
│   │   ├── Video/
│   │   ├── TTLs/
│   │   └── Bpod/
│   └── session_20251121/
│       └── session.toml
└── subject-002/
    └── ...
```

---

## NWB Metadata Fields

Standard NWB file metadata fields for describing your experiment.

### Core NWB Fields

```toml
# Session identification
session_id = "session_20251120"
identifier = "unique-session-id-001"
session_description = "Behavioral training with pose tracking"
session_start_time = "2025-11-20T14:30:00Z"

# Experiment context
experimenter = ["Doe, John", "Smith, Jane"]
experiment_description = """
Water-to-target behavioral task with simultaneous video tracking.
"""
institution = "University Name"
lab = "Lab Name"
protocol = "IACUC-2025-001"

# Descriptive fields
keywords = ["behavior", "pose tracking", "synchronization"]
notes = "Session conducted with standard lighting."
related_publications = []

# Experimental details
pharmacology = "None"
surgery = "Cranial window implant 2 weeks prior"
virus = "None"
stimulus_notes = "Visual targets on LED screen"
data_collection = "Bpod behavioral control, video at 30 fps"
```

### Processing Modules

Define how processed data is organized in the NWB file:

```toml
[[processing_modules]]
name = "behavior"
description = "Processed behavioral data including pose estimates"

[[processing_modules]]
name = "sync"
description = "Synchronization data between Bpod and cameras"
```

**Standard modules**:

- `behavior`: Behavioral data, pose estimates, trial information
- `sync`: Synchronization signals and alignment data
- `ecephys`: Electrophysiology data (spikes, LFP)
- `ophys`: Optical physiology data (calcium imaging)

---

## Camera Configuration

Defines video recording equipment and file locations.

### Basic Camera Definition

```toml
[[cameras]]
id = "camera_0"
paths = "Video/top/*.avi"
fps = 30.0
ttl_id = "ttl_camera"
optional = false
```

### Parameters

#### `id` (string, required)

- Unique identifier for this camera
- Used in pose estimation and NWB file organization
- Convention: `camera_0`, `camera_1`, or descriptive names like `overhead`, `side_left`

#### `paths` (string, required)

- Glob pattern for video files (relative to session directory)
- Examples:
  - `"Video/cam0/*.avi"` - All .avi files in Video/cam0/
  - `"Video/overhead/recording_*.mp4"` - Specific naming pattern
  - `"*.avi"` - All .avi files in session root

#### `fps` (float, required)

- Frame rate in frames per second
- Used for timestamp generation and validation
- Must match actual video frame rate

#### `ttl_id` (string, required)

- TTL channel ID used for camera frame synchronization
- Must match an `id` in `[[TTLs]]` configuration
- Multiple cameras can share the same TTL channel

#### `optional` (boolean, default: `false`)

- If `true`: Pipeline continues if no videos found (logs warning)
- If `false`: Pipeline fails if no videos match pattern
- Use cases:
  - Optional supplementary cameras
  - Equipment that may not be present in all sessions
  - Incomplete datasets

### Advanced Camera Configuration

```toml
[[cameras]]
id = "overhead"
paths = "Video/overhead/*.avi"
fps = 30.0
ttl_id = "ttl_camera"
optional = false
description = "Top-down view for body tracking"
manufacturer = "FLIR"
model = "Blackfly S"
```

**Additional fields**:

- `description`: Human-readable camera description
- `manufacturer`: Camera manufacturer
- `model`: Camera model name

### Multi-Camera Example

```toml
# Required primary camera
[[cameras]]
id = "overhead"
paths = "Video/top/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = false

# Optional side cameras
[[cameras]]
id = "side_left"
paths = "Video/left/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = true

[[cameras]]
id = "side_right"
paths = "Video/right/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = true

# Different frame rate camera
[[cameras]]
id = "pupil"
paths = "Video/pupil/*.avi"
fps = 60.0
ttl_id = "ttl_pupil_cam"
optional = false
```

---

## TTL Configuration

Defines TTL (transistor-transistor logic) pulse channels for synchronization.

### Basic TTL Definition

```toml
[[TTLs]]
id = "ttl_camera"
paths = "TTLs/*_frame.txt"
description = "Camera exposure pulses"
```

### Parameters

#### `id` (string, required)

- Unique identifier for this TTL channel
- Referenced by cameras (`ttl_id`) and Bpod sync (`sync_ttl`)
- Convention: `ttl_camera`, `ttl_cue`, `ttl_reward`, etc.

#### `paths` (string, required)

- Glob pattern for TTL timestamp files (relative to session directory)
- Examples:
  - `"TTLs/*_frame.txt"` - All frame trigger files
  - `"TTLs/session.nidq.xa_7_0_frame.txt"` - Specific SpikeGLX file
  - `"sync/*.csv"` - CSV files in sync directory

#### `description` (string, optional)

- Human-readable description of TTL channel purpose
- Helps document experimental setup

### TTL File Format

TTL files should contain one timestamp per line (in seconds):

```text
0.0000
0.0333
0.0667
0.1000
...
```

**Supported formats**:

- Plain text (`.txt`)
- CSV (`.csv`) - first column used
- SpikeGLX format (`.txt`)

### Common TTL Channels

```toml
# Camera frame triggers
[[TTLs]]
id = "ttl_camera"
paths = "TTLs/*_frame.txt"
description = "Camera exposure pulses (frame sync)"

# Behavioral event triggers
[[TTLs]]
id = "ttl_cue"
paths = "TTLs/*_cue.txt"
description = "Audio/visual cue onset pulses"

# Trial outcome markers
[[TTLs]]
id = "ttl_hitmiss"
paths = "TTLs/*_hitmiss.txt"
description = "Trial outcome signals (hit/miss)"

# Reward delivery
[[TTLs]]
id = "ttl_reward"
paths = "TTLs/*_reward.txt"
description = "Reward valve opening signals"
```

---

## Bpod Configuration

Defines Bpod behavioral control system file locations and parsing.

### Basic Bpod Configuration

```toml
[bpod]
path = "Bpod/*.mat"
order = "time_asc"
continuous_time = false
```

### Parameters

#### `path` (string, required)

- Glob pattern for Bpod .mat files (relative to session directory)
- Examples:
  - `"Bpod/*.mat"` - All .mat files in Bpod/
  - `"Bpod/Session_*.mat"` - Files matching pattern
  - `"behavior/*.mat"` - Files in behavior directory

#### `order` (string, default: `"time_asc"`)

- File sorting order for multi-file sessions
- Options:
  - `"time_asc"`: Sort by file modification time (oldest first)
  - `"time_desc"`: Sort by file modification time (newest first)
  - `"name_asc"`: Sort by filename (alphabetical)
  - `"name_desc"`: Sort by filename (reverse alphabetical)

#### `continuous_time` (boolean, default: `false`)

- If `true`: Trial timestamps are continuous across files
- If `false`: Each file starts at t=0, offsets computed during sync

---

## Bpod Trial Synchronization

**Critical**: This configuration maps Bpod trial structures to TTL synchronization signals.

### Structure

```toml
[bpod.sync]
[bpod.sync.trial_types]

# Dictionary mapping trial type ID → sync configuration
[bpod.sync.trial_types."1"]
sync_signal = "W2T_Audio"
sync_ttl = "ttl_cue"

[bpod.sync.trial_types."2"]
sync_signal = "A2L_Audio"
sync_ttl = "ttl_cue"
```

### Parameters

#### Trial Type Key (string, required)

- Must match Bpod `TrialTypes` values (as string)
- Examples: `"1"`, `"2"`, `"3"`
- If Bpod data doesn't have `TrialTypes`, defaults to type `"1"`

#### `sync_signal` (string, required)

- Bpod state or event name that triggers synchronization TTL
- Must exist in your Bpod protocol's state machine
- Common examples:
  - `"W2T_Audio"` - Water-to-target audio cue
  - `"ITI"` - Inter-trial interval start
  - `"trial_start"` - Trial start marker
  - `"Cue"` - Stimulus cue state
  - `"Flex1Trig2"` - Hardware trigger event

#### `sync_ttl` (string, required)

- TTL channel ID that records sync pulses
- Must match an `id` in `[[TTLs]]` configuration
- Multiple trial types can use the same TTL channel

### How It Works

1. For each Bpod trial, the pipeline finds when `sync_signal` state/event occurred
2. Matches this to the corresponding TTL pulse in `sync_ttl` channel
3. Computes time offset to align Bpod timeline with absolute TTL time
4. All Bpod timestamps converted to absolute time using this offset

### Finding Your sync_signal Names

**Method 1: Check your Bpod protocol**

- Look at your state machine definition
- Common states: `ITI`, `WaitForPoke`, `Reward`, `Punishment`
- Common events: `Port1In`, `Port1Out`, `BNC1High`, `Tup`

**Method 2: Inspect .mat files**

```python
import scipy.io as sio
data = sio.loadmat('Bpod/session.mat')
trial = data['SessionData']['RawEvents']['Trial'][0][0]
print("States:", trial['States'].dtype.names)
print("Events:", trial['Events'].dtype.names)
```

**Method 3: Check pipeline logs**

If sync fails, logs will show available states/events:

```text
Trial 1: sync_signal 'InvalidName' not found
Available states: ITI, Response_window, HIT, Miss, RightReward
```

### Complete Example

```toml
[bpod]
path = "Bpod/*.mat"
order = "time_asc"
continuous_time = false

[bpod.sync]
[bpod.sync.trial_types]

# Water-to-target left trials
[bpod.sync.trial_types."1"]
sync_signal = "W2T_Audio"
sync_ttl = "ttl_cue"

# Air-to-left trials
[bpod.sync.trial_types."2"]
sync_signal = "A2L_Audio"
sync_ttl = "ttl_cue"

# Microstimulation trials
[bpod.sync.trial_types."3"]
sync_signal = "Microstim"
sync_ttl = "ttl_cue"
```

---

## Device Configuration

Defines experimental equipment for NWB metadata.

### Basic Device Definition

```toml
[[devices]]
name = "bpod"
description = "Bpod State Machine r2.5 for behavioral control"
manufacturer = "Sanworks"
```

### Parameters

- `name` (string, required): Unique device identifier
- `description` (string, optional): Device description
- `manufacturer` (string, optional): Manufacturer name
- `model_name` (string, optional): Model name/number

### Common Devices

```toml
[[devices]]
name = "bpod"
description = "Bpod State Machine r2.5"
manufacturer = "Sanworks"

[[devices]]
name = "camera_0"
description = "High-speed camera - overhead view"
manufacturer = "FLIR"
model_name = "Blackfly S"

[[devices]]
name = "neuropixels_1.0"
description = "Neuropixels 1.0 probe"
manufacturer = "IMEC"
```

---

## Subject Information

Subject-specific metadata, typically in `subject.toml`.

### Basic Subject Configuration

```toml
[subject]
subject_id = "M001"
species = "Mus musculus"
sex = "M"
age = "P84D"
description = "Adult male C57BL/6J mouse, 12 weeks old"
```

### Parameters

#### `subject_id` (string, required)

- Unique identifier for the subject
- Should match directory name

#### `species` (string, recommended)

- Formal latin binomial name
- Examples: `"Mus musculus"`, `"Rattus norvegicus"`, `"Homo sapiens"`

#### `sex` (string, recommended)

- Standard values: `"M"` (male), `"F"` (female), `"U"` (unknown), `"O"` (other)

#### `age` (string, optional)

- ISO 8601 duration format recommended
- Examples: `"P90D"` (90 days), `"P12W"` (12 weeks), `"P3M"` (3 months)

#### `age__reference` (string, optional)

- Reference point for age
- Values: `"birth"` or `"gestational"`

#### Optional Fields

```toml
[subject]
# ... required fields ...
genotype = "C57BL/6J wild-type"
strain = "C57BL/6J"
weight = "0.025 kg"
date_of_birth = "2024-10-23T00:00:00Z"
description = "Additional subject details"
```

---

## Session Information

Session-specific metadata, typically in `session.toml`.

### Required Session Fields

```toml
session_description = "Behavioral training session with pose tracking"
identifier = "session_20251120"
session_start_time = "2025-11-20T14:30:00Z"
```

### Parameters

#### `session_description` (string, required)

- Description of what happened in this session
- Should be specific to this session

#### `identifier` (string, required)

- Unique identifier for the NWB file
- Often matches session_id or includes additional info

#### `session_start_time` (string, required)

- ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`
- Absolute timestamp for session start
- Used as time zero for all relative timestamps

### Optional Session Fields

```toml
experimenter = ["Doe, John"]
notes = "Animal showed normal behavior"
```

---

## Complete Examples

### Example 1: Minimal Session Metadata

Suitable for sessions that use experiment-wide defaults:

```toml
# session.toml
session_description = "Training session day 5"
identifier = "subject-001_session-005"
session_start_time = "2025-11-20T14:30:00Z"
```

### Example 2: Complete Experiment Metadata

Root metadata with all common equipment:

```toml
# metadata.toml

# Experiment description
experiment_description = """
Water-to-target behavioral task with pose tracking.
"""
institution = "University Name"
lab = "Lab Name"
keywords = ["behavior", "pose", "synchronization"]

# Devices
[[devices]]
name = "bpod"
description = "Bpod State Machine r2.5"
manufacturer = "Sanworks"

[[devices]]
name = "camera_system"
description = "Multi-camera pose tracking"
manufacturer = "FLIR"

# Processing modules
[[processing_modules]]
name = "behavior"
description = "Processed behavioral data"

[[processing_modules]]
name = "sync"
description = "Synchronization data"

# Bpod configuration
[bpod]
path = "Bpod/*.mat"
order = "time_asc"
continuous_time = false

# Bpod synchronization
[bpod.sync]
[bpod.sync.trial_types]

[bpod.sync.trial_types."1"]
sync_signal = "W2T_Audio"
sync_ttl = "ttl_cue"

[bpod.sync.trial_types."2"]
sync_signal = "A2L_Audio"
sync_ttl = "ttl_cue"

# Cameras
[[cameras]]
id = "camera_0"
paths = "Video/top/*.avi"
fps = 30.0
ttl_id = "ttl_camera"
optional = false

[[cameras]]
id = "camera_1"
paths = "Video/side/*.avi"
fps = 30.0
ttl_id = "ttl_camera"
optional = true

# TTL channels
[[TTLs]]
id = "ttl_camera"
paths = "TTLs/*_frame.txt"
description = "Camera frame triggers"

[[TTLs]]
id = "ttl_cue"
paths = "TTLs/*_cue.txt"
description = "Behavioral cue triggers"
```

### Example 3: Subject Metadata

```toml
# subject.toml

[subject]
subject_id = "M001"
description = "Adult male C57BL/6J mouse"
species = "Mus musculus"
sex = "M"
age = "P84D"
age__reference = "birth"
genotype = "C57BL/6J wild-type"
strain = "C57BL/6J"
weight = "0.025 kg"
date_of_birth = "2024-10-23T00:00:00Z"
```

---

## Common Patterns

### Pattern 1: Session with Modified Camera Setup

Use session.toml to override specific cameras:

```toml
# session.toml
session_description = "Session with additional pupil camera"
identifier = "session_20251120"
session_start_time = "2025-11-20T14:30:00Z"

# Add new camera (in addition to those in metadata.toml)
[[cameras]]
id = "pupil_left"
paths = "Video/pupil/*.avi"
fps = 60.0
ttl_id = "ttl_pupil"
optional = false

# Add corresponding TTL channel
[[TTLs]]
id = "ttl_pupil"
paths = "TTLs/*_pupil_frame.txt"
description = "Pupil camera frame triggers"
```

### Pattern 2: Optional Cameras for Incomplete Data

```toml
# metadata.toml (experiment-wide)
[[cameras]]
id = "overhead"
paths = "Video/top/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = false  # Always required

[[cameras]]
id = "side_left"
paths = "Video/left/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = true  # May be missing in some sessions

[[cameras]]
id = "side_right"
paths = "Video/right/*.avi"
fps = 150.0
ttl_id = "ttl_camera"
optional = true  # May be missing in some sessions
```

### Pattern 3: Multiple Trial Types

```toml
[bpod.sync]
[bpod.sync.trial_types]

# Different trial types with different sync signals
[bpod.sync.trial_types."1"]
sync_signal = "TargetLeft"
sync_ttl = "ttl_cue"

[bpod.sync.trial_types."2"]
sync_signal = "TargetRight"
sync_ttl = "ttl_cue"

[bpod.sync.trial_types."3"]
sync_signal = "TargetCenter"
sync_ttl = "ttl_cue"

# Control trials with different TTL
[bpod.sync.trial_types."99"]
sync_signal = "ControlTrial"
sync_ttl = "ttl_control"
```

---

## Troubleshooting

### No figures generated

**Symptom**: Figures directory empty or missing  
**Likely cause**: Missing Bpod trial synchronization configuration  
**Solution**: Add `[bpod.sync.trial_types]` to your metadata.toml

### "Skipping trial alignment (no trial_type configs in metadata)"

**Symptom**: Message in pipeline.log  
**Cause**: Missing or incorrectly structured `[bpod.sync.trial_types]`  
**Solution**:

1. Verify structure uses dictionary format: `[bpod.sync.trial_types."1"]`
2. Do NOT use array format: `[[bpod.sync.trial_types]]`

### "sync_signal 'XYZ' not found"

**Symptom**: Trial alignment warnings  
**Cause**: `sync_signal` name doesn't match Bpod state/event names  
**Solution**: Inspect your Bpod .mat files to find correct state names

### Camera marked optional but pipeline still fails

**Symptom**: Pipeline fails even with `optional = true`  
**Cause**: Setting might be in wrong file (config vs metadata)  
**Solution**: Ensure `optional` is in metadata file (metadata.toml or session.toml), NOT in config.toml

### TTL verification failing

**Symptom**: Frame/TTL count mismatch errors  
**Cause**: Either sync issue or verification too strict  
**Solutions**:

1. Check if TTL files exist and match `paths` pattern
2. Verify `ttl_id` in camera matches `id` in TTLs
3. If expected, disable check: `verification.check_sync_mismatch = false` in config.toml (not metadata)

---

## See Also

- **[Configuration Parameters Guide](configuration-parameters.md)** - Pipeline processing parameters
- **[Templates](../../templates/README.md)** - Example metadata files with detailed comments
- **[Templates/metadata.toml](../../templates/metadata.toml)** - Complete example with all options
- [NWB Format Specification](https://nwb-schema.readthedocs.io/) - Official NWB documentation
