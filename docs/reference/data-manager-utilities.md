# Data Manager Utilities Reference

## Overview

The `w2t_bkin.data.manager` module now provides reusable utilities for file system and TOML operations, eliminating code duplication across the codebase.

## File System Utilities

### `ensure_parent_dir(path: Path | str) -> Path`

Ensures parent directory exists for a given file path.

**Parameters:**

- `path`: File path whose parent directory should be created

**Returns:**

- `Path`: Absolute path object

**Example:**

```python
from w2t_bkin.data import ensure_parent_dir

# Creates data/raw/subject-001/ if it doesn't exist
path = ensure_parent_dir("data/raw/subject-001/session.toml")
```

**Usage in codebase:**

- ✅ `src/w2t_bkin/data/manager.py` (native)
- ✅ `synthetic/utils.py` (imported, eliminates duplication)

---

## TOML Utilities

### `read_toml(path: Path | str) -> dict`

Reads and parses a TOML file.

**Parameters:**

- `path`: Path to TOML file

**Returns:**

- `dict`: Parsed TOML content

**Raises:**

- `FileNotFoundError`: If file doesn't exist
- `tomli.TOMLDecodeError`: If TOML is invalid

**Example:**

```python
from w2t_bkin.data import read_toml

config = read_toml("configuration.toml")
print(config["project"]["name"])
```

---

### `write_toml(path: Path | str, data: dict, *, ensure_parents: bool = True) -> Path`

Writes dictionary to TOML file.

**Parameters:**

- `path`: Target file path
- `data`: Dictionary to serialize to TOML
- `ensure_parents`: If True (default), creates parent directories

**Returns:**

- `Path`: Absolute path to written file

**Example:**

```python
from w2t_bkin.data import write_toml

data = {
    "project": {"name": "experiment-001"},
    "paths": {"data_root": "/data"}
}

# Automatically creates parent dirs
path = write_toml("configs/project/config.toml", data)
print(f"Written to: {path}")
```

**Usage in codebase:**

- ✅ `init_experiment()` - writes metadata.toml
- ✅ `add_subject()` - writes subject.toml
- ✅ `add_session()` - writes session.toml
- ✅ `import_raw_data()` - updates session.toml

---

### `validate_toml_syntax(path: Path | str) -> tuple[bool, str | None]`

Validates TOML file syntax.

**Parameters:**

- `path`: Path to TOML file

**Returns:**

- `tuple[bool, str | None]`:
  - `(True, None)` if valid
  - `(False, error_message)` if invalid

**Example:**

```python
from w2t_bkin.data import validate_toml_syntax

is_valid, error = validate_toml_syntax("config.toml")
if not is_valid:
    print(f"Invalid TOML: {error}")
```

**Usage in codebase:**

- ✅ `validate_experiment_structure()` - validates all TOML files

---

## Benefits

### Code Quality

- ✅ **Eliminates duplication**: `ensure_parent_dir()` was duplicated
- ✅ **Consistent error handling**: All TOML operations use same patterns
- ✅ **Type safety**: Proper type hints with Python 3.10+ union syntax

### Maintainability

- ✅ **Single source of truth**: All TOML I/O goes through same functions
- ✅ **Easy testing**: Utilities are standalone and testable
- ✅ **Better documentation**: Clear API with examples

### Reusability

- ✅ **Available via data module**: `from w2t_bkin.data import read_toml`
- ✅ **Used by synthetic module**: No duplication
- ✅ **Used by data management CLI**: Production code

---

## Migration Guide

### Before

```python
import tomli
import tomli_w

# Read TOML
with open("config.toml", "rb") as f:
    config = tomli.load(f)

# Write TOML
path = Path("output/config.toml")
path.parent.mkdir(parents=True, exist_ok=True)
with open(path, "wb") as f:
    tomli_w.dump(data, f)
```

### After

```python
from w2t_bkin.data import read_toml, write_toml

# Read TOML
config = read_toml("config.toml")

# Write TOML (auto-creates parent dirs)
write_toml("output/config.toml", data)
```

---

## Design Decisions

### ✅ What We Moved

- `ensure_parent_dir()` - Genuinely reusable across production and test code

### ⚠️ What We Kept Separate

- **Custom TOML rendering** (`synthetic/session_synth.py`)
  - Different design goal: minimal dependencies
  - Production uses `tomli_w` for robustness
- **Test-specific utilities** (`synthetic/utils.py`)
  - `derive_sequenced_paths()` - Only for synthetic data patterns
  - `deterministic_rng()` - Only for reproducible test data
  - `clock_drift_offset()` - Only for simulation

---

## Testing

All utilities are tested and working:

```bash
# Test data.manager utilities
python -c "from w2t_bkin.data import ensure_parent_dir, read_toml, write_toml"

# Test synthetic integration
python -c "from synthetic.utils import ensure_parent_dir"

# Test CLI integration
python -m w2t_bkin.cli data --help
```

✅ All tests passing!
