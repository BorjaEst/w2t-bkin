# Phase 3 RED Phase Summary

**Date:** 2025-01-12  
**GitHub Issue:** #4  
**Phase:** Phase 3 - Optional Modalities (Transcode, Pose, Facemap)  
**TDD Stage:** RED (Tests created, implementations pending)

## Overview

Created comprehensive RED phase test infrastructure for Phase 3 optional modalities:
- **Transcode:** Video transcoding to mezzanine format
- **Pose:** Import/harmonize DLC and SLEAP pose estimation data
- **Facemap:** ROI-based facial motion analysis

All tests are designed to **fail** (RED phase) until implementations are created (GREEN phase).

## Test Count

| Category | File | Tests | Status |
|----------|------|-------|--------|
| **Unit Tests** | | | |
| Pose | `tests/unit/test_pose.py` | 15 | ❌ RED (ModuleNotFoundError) |
| Facemap | `tests/unit/test_facemap.py` | 15 | ❌ RED (ModuleNotFoundError) |
| Transcode | `tests/unit/test_transcode.py` | 15 | ❌ RED (ModuleNotFoundError) |
| **Integration Tests** | | | |
| Phase 3 | `tests/integration/test_phase_3_optionals.py` | 7 | ❌ RED (ModuleNotFoundError) |
| **Total Phase 3** | | **52** | **All failing (proper RED)** |
| **Existing Tests** | | 177 | ✅ All passing |

## Requirements Coverage

### FR-4: Video Transcoding (Optional)
**Unit Tests (15):**
- `test_Should_CreateDefaultOptions_When_NoParamsProvided`
- `test_Should_OverrideDefaults_When_ParamsProvided`
- `test_Should_ValidateCRF_When_CreatingOptions`
- `test_Should_SkipTranscode_When_AlreadyExists` (idempotence, NFR-2)
- `test_Should_Transcode_When_OptionsChanged`
- `test_Should_ComputeChecksum_When_VideoProvided`
- `test_Should_UseDeterministicChecksum_When_SameContent`
- `test_Should_GeneratePathFromChecksum_When_Transcoding`
- `test_Should_TranscodeVideo_When_ValidInputProvided`
- `test_Should_PreserveFrameCount_When_Transcoding`
- `test_Should_HandleMissingFile_When_Transcoding`
- `test_Should_UpdateManifest_When_TranscodeComplete`
- `test_Should_PreserveOriginalPaths_When_UpdatingManifest`
- `test_Should_CallFFmpeg_When_Transcoding`
- `test_Should_HandleFFmpegError_When_TranscodeFails`

**Integration Tests (2):**
- `test_Should_TranscodeVideos_When_Enabled_Issue4`
- `test_Should_SkipTranscode_When_AlreadyExists_Issue4`

### FR-5: Pose Import/Harmonization (Optional)
**Unit Tests (15):**
- `test_Should_ImportDLCCSV_When_ValidFormatProvided`
- `test_Should_PreserveConfidence_When_ImportingDLC`
- `test_Should_HandleInvalidFormat_When_ImportingDLC`
- `test_Should_ImportSLEAPH5_When_ValidFormatProvided`
- `test_Should_PreserveConfidence_When_ImportingSLEAP`
- `test_Should_MapDLCToCanonical_When_MappingProvided`
- `test_Should_MapSLEAPToCanonical_When_MappingProvided`
- `test_Should_WarnForMissingKeypoints_When_Harmonizing`
- `test_Should_AlignFrameIndices_When_NearestMapping`
- `test_Should_AlignFrameIndices_When_LinearMapping`
- `test_Should_HandleOutOfBounds_When_Aligning`
- `test_Should_ComputeMeanConfidence_When_ValidatingPose`
- `test_Should_WarnForLowConfidence_When_BelowThreshold`
- `test_Should_CreatePoseBundle_When_AllDataProvided`
- `test_Should_EnforceFrozen_When_PoseBundleCreated`

**Integration Tests (2):**
- `test_Should_ImportDLCPose_When_FilesProvided_Issue4`
- `test_Should_ImportSLEAPPose_When_FilesProvided_Issue4`

### FR-6: Facemap Computation/Import (Optional)
**Unit Tests (15):**
- `test_Should_DefineROIs_When_ValidSpecificationProvided`
- `test_Should_ValidateROIBounds_When_CreatingROI`
- `test_Should_WarnForOverlappingROIs_When_Detected`
- `test_Should_ImportFacemapNPY_When_ValidFileProvided`
- `test_Should_HandleMissingFile_When_ImportFacemap`
- `test_Should_ComputeMotionEnergy_When_ROIsProvided`
- `test_Should_MatchVideoFrameCount_When_ComputingSignals`
- `test_Should_AlignSignalTimestamps_When_TimebaseProvided`
- `test_Should_UseLinearMapping_When_Configured`
- `test_Should_FailAlignment_When_LengthMismatch`
- `test_Should_ValidateSamplingRate_When_CheckingConsistency`
- `test_Should_FailValidation_When_RateMismatch`
- `test_Should_CreateFacemapBundle_When_AllDataProvided`
- `test_Should_EnforceFrozen_When_FacemapBundleCreated`
- `test_Should_ValidateROIsMatchSignals_When_CreatingBundle`

**Integration Tests (1):**
- `test_Should_ComputeFacemap_When_Enabled_Issue4`

### Optional Nature (Cross-cutting)
**Integration Tests (2):**
- `test_Should_SkipOptionals_When_Disabled_Issue4` - Pipeline runs without Phase 3
- `test_Should_AlignAllModalities_When_UsingRealSession_Issue4` - Real Session-000001 end-to-end

## Domain Models Added

Added 8 new models to `src/w2t_bkin/domain.py` (~110 lines):

```python
# Pose estimation models
@dataclass(frozen=True, kw_only=True)
class PoseKeypoint:
    name: str
    x: float
    y: float
    confidence: float

@dataclass(frozen=True, kw_only=True)
class PoseFrame:
    frame_index: int
    timestamp: float
    keypoints: List[PoseKeypoint]
    source: str

@dataclass(frozen=True, kw_only=True)
class PoseBundle:
    session_id: str
    camera_id: str
    model_name: str
    skeleton: List[str]
    frames: List[PoseFrame]
    alignment_method: str
    mean_confidence: float

# Facemap models
@dataclass(frozen=True, kw_only=True)
class FacemapROI:
    name: str
    x: int
    y: int
    width: int
    height: int

@dataclass(frozen=True, kw_only=True)
class FacemapSignal:
    roi_name: str
    timestamps: List[float]
    values: List[float]
    sampling_rate: float

@dataclass(frozen=True, kw_only=True)
class FacemapBundle:
    session_id: str
    camera_id: str
    rois: List[FacemapROI]
    signals: List[FacemapSignal]
    alignment_method: str
    generated_at: str

# Transcode models
@dataclass(frozen=True, kw_only=True)
class TranscodeOptions:
    codec: str
    crf: int
    preset: str
    keyint: int

@dataclass(frozen=True, kw_only=True)
class TranscodedVideo:
    camera_id: str
    original_path: Path
    output_path: Path
    codec: str
    checksum: str
    frame_count: int
```

## Test Fixtures Created

### Pose Fixtures
- **DLC:** `tests/fixtures/pose/dlc/pose_sample.csv`
  - 5 frames, 3 keypoints (nose, left_ear, right_ear)
  - Realistic confidence values (0.92-0.97)
  - Standard DLC CSV format with scorer/bodyparts headers

- **SLEAP:** `tests/fixtures/pose/sleap/README.md`
  - Documented mock JSON format for SLEAP data
  - Placeholder for H5 files

### Facemap Fixtures
- `tests/fixtures/facemap/facemap_output.npy` - Placeholder for Facemap outputs

## Expected API Surface (Not Yet Implemented)

### `src/w2t_bkin/pose.py` (Not created)
```python
def import_dlc_pose(csv_path: Path) -> List[Dict]
def import_sleap_pose(h5_path: Path) -> List[Dict]
def harmonize_dlc_to_canonical(data, mapping: Dict[str, str]) -> List[Dict]
def harmonize_sleap_to_canonical(data, mapping: Dict[str, str]) -> List[Dict]
def align_pose_to_timebase(data, reference_times: List[float], mapping: str) -> List[PoseFrame]
def validate_pose_confidence(frames: List[PoseFrame], threshold: float = 0.8) -> bool
```

### `src/w2t_bkin/facemap.py` (Not created)
```python
def define_rois(roi_specs: List[Dict]) -> List[FacemapROI]
def import_facemap_output(npy_path: Path) -> Dict
def compute_facemap_signals(video_path: Path, rois: List[FacemapROI]) -> List[FacemapSignal]
def align_facemap_to_timebase(signals, reference_times: List[float], mapping: str) -> List[FacemapSignal]
def validate_facemap_sampling_rate(signal: FacemapSignal, expected_rate: float, tolerance: float) -> bool
```

### `src/w2t_bkin/transcode.py` (Not created)
```python
def create_transcode_options(**kwargs) -> TranscodeOptions
def transcode_video(video_path: Path, options: TranscodeOptions, output_dir: Path) -> TranscodedVideo
def compute_video_checksum(video_path: Path) -> str
def is_already_transcoded(video_path: Path, options: TranscodeOptions, transcoded_path: Path) -> bool
def update_manifest_with_transcode(manifest: Dict, transcoded: TranscodedVideo) -> Dict
```

## Verification

### RED Phase Validation
All Phase 3 tests correctly fail with `ModuleNotFoundError`:

```bash
$ pytest tests/unit/test_pose.py -v
# ERROR: ModuleNotFoundError: No module named 'w2t_bkin.pose'

$ pytest tests/unit/test_facemap.py -v
# ERROR: ModuleNotFoundError: No module named 'w2t_bkin.facemap'

$ pytest tests/unit/test_transcode.py -v
# ERROR: ModuleNotFoundError: No module named 'w2t_bkin.transcode'

$ pytest tests/integration/test_phase_3_optionals.py -v
# ERROR: fixture 'minimal_config_dict' works, modules missing
```

### Existing Tests Still Pass
All 177 existing tests (Phase 0-2) remain passing:

```bash
$ pytest tests/unit/ tests/integration/ \
    --ignore=tests/unit/test_pose.py \
    --ignore=tests/unit/test_facemap.py \
    --ignore=tests/unit/test_transcode.py \
    --ignore=tests/integration/test_phase_3_optionals.py
# ============================= 177 passed in 11.72s =============================
```

## Next Steps (GREEN Phase)

1. **Implement `src/w2t_bkin/pose.py`**
   - DLC CSV parser
   - SLEAP H5 parser
   - Canonical skeleton harmonization
   - Timebase alignment (reuse Phase 2 alignment logic)
   - Confidence validation

2. **Implement `src/w2t_bkin/facemap.py`**
   - ROI definition and validation
   - Facemap NPY import
   - Motion energy computation (OpenCV)
   - Signal alignment to timebase
   - Sampling rate validation

3. **Implement `src/w2t_bkin/transcode.py`**
   - TranscodeOptions configuration
   - FFmpeg wrapper with subprocess
   - Content-addressed output paths (SHA256)
   - Idempotence checks (NFR-2)
   - Manifest updates

4. **Run GREEN Phase**
   ```bash
   pytest tests/unit/test_pose.py -v
   pytest tests/unit/test_facemap.py -v
   pytest tests/unit/test_transcode.py -v
   pytest tests/integration/test_phase_3_optionals.py -v
   ```

5. **Expected Final Count:** 177 (current) + 52 (Phase 3) = **229 tests**

## TDD Principles Applied

✅ **Write tests first** - All 52 tests written before implementation  
✅ **Tests fail for right reason** - ModuleNotFoundError confirms missing implementations  
✅ **Clear behavior specs** - Test names describe expected behavior  
✅ **AAA pattern** - Arrange, Act, Assert structure throughout  
✅ **Domain-driven** - Tests use domain models from `domain.py`  
✅ **Issue-linked** - All tests reference GitHub Issue #4  
✅ **Edge cases** - Boundary conditions, error handling tested  
✅ **Immutability** - NFR-7 verified for new bundles  
✅ **Idempotence** - NFR-2 tested for transcoding  

## Dependencies

Phase 3 depends on Phase 2 sync/timebase infrastructure:
- Pose alignment uses `reference_times` from Phase 2
- Facemap alignment uses `reference_times` from Phase 2
- Integration tests load `alignment.json` from Phase 2 output

## Files Modified/Created

**Modified:**
- `src/w2t_bkin/domain.py` - Added 8 Phase 3 domain models (~110 lines)

**Created:**
- `tests/unit/test_pose.py` - 15 pose unit tests (~250 lines)
- `tests/unit/test_facemap.py` - 15 facemap unit tests (~220 lines)
- `tests/unit/test_transcode.py` - 15 transcode unit tests (~200 lines)
- `tests/integration/test_phase_3_optionals.py` - 7 integration tests (~250 lines)
- `tests/fixtures/pose/dlc/pose_sample.csv` - Sample DLC data
- `tests/fixtures/pose/sleap/README.md` - SLEAP format docs
- `tests/fixtures/facemap/facemap_output.npy` - Placeholder
- `tests/phase_3_red_summary.md` - This document

**Not Created (Pending GREEN phase):**
- `src/w2t_bkin/pose.py`
- `src/w2t_bkin/facemap.py`
- `src/w2t_bkin/transcode.py`

---

**TDD Status:** ✅ RED phase complete - Ready for GREEN phase implementation
