# Validation Commands

Commands for validating and inspecting NWB files.

## `validate` - Validate NWB File

Run comprehensive validation checks using nwbinspector.

### Usage

```bash
w2t-bkin validate NWB_PATH [OPTIONS]
```

### Arguments

- `NWB_PATH` - Path to NWB file to validate

### Options

- `--show-warnings / --no-show-warnings` - Show warnings in output (default: show)
- `--output PATH` - Save results to JSON file

### Examples

```bash
# Basic validation
w2t-bkin validate output/session-001/session-001.nwb

# Save results to JSON
w2t-bkin validate file.nwb --output validation.json

# Hide warnings (show only errors)
w2t-bkin validate file.nwb --no-show-warnings
```

### Output

The command displays:

1. **Summary Table** - Count of critical errors, errors, and warnings
2. **Details** - Specific issues with location and message
3. **Exit Code** - 0 if valid, 1 if errors/critical issues

Example output:

```text
Validating: session-001.nwb

╭─── Validation Summary ────╮
│ Severity    Count         │
├───────────────────────────┤
│ ERROR       2             │
│ WARNING     5             │
╰───────────────────────────╯

Details:

● [ERROR] check_timestamps_match
  Timestamps do not match session_start_time
  Location: /acquisition/Videos/camera_0

● [WARNING] check_description
  Description field is empty
  Location: /general/devices/bpod
```

---

## `inspect` - Inspect NWB File

Display summary of NWB file structure and contents.

### Inspect Usage

```bash
w2t-bkin inspect NWB_PATH [OPTIONS]
```

### Inspect Arguments

- `NWB_PATH` - Path to NWB file to inspect

### Inspect Options

- `--show-acquisition / --no-show-acquisition` - Show acquisition data (default: show)
- `--show-trials / --no-show-trials` - Show trials table (default: show)
- `--show-devices / --no-show-devices` - Show devices (default: show)

### Inspect Examples

```bash
# Full inspection
w2t-bkin inspect output/session-001/session-001.nwb

# Show only session metadata and subject
w2t-bkin inspect file.nwb --no-show-acquisition --no-show-trials --no-show-devices
```

### Inspect Output

The command displays:

1. **File Info** - Identifier, session description, file size
2. **Session Metadata** - Start time, experimenter, lab, institution
3. **Subject Info** - ID, species, sex, age
4. **Devices** - Available recording devices
5. **Acquisition Data** - Videos, TTL signals, etc.
6. **Processing Modules** - Processed data containers
7. **Trials Table** - Number of trials and columns

Example output:

```text
╭──────────── NWB File Inspection ────────────╮
│ NWB File Inspection                         │
│ Identifier: subject-001-session-001         │
│ Session: Behavioral session                 │
╰─────────────────────────────────────────────╯

╭─── Session Metadata ───╮
│ Field          Value   │
├─────────────────────────┤
│ Start Time     2024... │
│ Experimenter   Alice   │
│ Lab            Larkum  │
│ Institution    HU      │
╰────────────────────────────╯

╭─── Subject ───╮
│ Field   Value │
├──────────────┤
│ ID      m001  │
│ Species Mus   │
│ Sex     F     │
╰──────────────────╯

╭─── Devices ───────────────╮
│ Name    Description       │
├──────────────────────────┤
│ bpod    State machine    │
╰────────────────────────────────╯

╭─── Acquisition Data ──────────╮
│ Name             Type          │
├──────────────────────────────┤
│ camera_0_video   ImageSeries  │
│ ttl_camera       Events        │
╰──────────────────────────────────╯

Trials: 150 trials
Columns: start_time, stop_time, trial_type, ...
```

---

## See Also

- [Pipeline Commands](pipeline-commands.md) - Process sessions
- [Data Management](data-management.md) - Experiment setup
- [NWB Inspector Documentation](https://nwbinspector.readthedocs.io/) - Validation details
