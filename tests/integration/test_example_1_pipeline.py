"""Integration test for example_1.py pipeline.

This test replicates the complete data processing pipeline from example_1.py
using test fixtures to ensure all components work together correctly.
"""

from pathlib import Path

from pynwb import NWBHDF5IO
import pytest

from w2t_bkin import behavior, bpod, config, pose, session, sync, ttl


@pytest.fixture
def test_config(tmp_path):
    """Create test configuration with fixture paths."""
    # Use the existing fixtures
    fixtures_root = Path(__file__).parent.parent / "fixtures"

    return {
        "raw_dir": fixtures_root / "data" / "raw" / "Session-000001",
        "interim_dir": fixtures_root / "data" / "interim",
        "output_dir": tmp_path / "output",
    }


def test_full_pipeline_integration(test_config, tmp_path):
    """Test complete pipeline from raw data to NWB file.

    This test validates:
    1. Configuration loading and path validation
    2. Session metadata creation
    3. TTL pulse loading
    4. Bpod data parsing
    5. Trial synchronization
    6. Behavioral data extraction (Task, TaskRecording, Trials)
    7. Pose data import and processing
    8. NWB file assembly and writing
    9. NWB file validation and readability
    """
    # Setup paths
    rawdata_dir = test_config["raw_dir"]
    interim_dir = test_config["interim_dir"]
    output_dir = test_config["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate required paths exist
    assert (rawdata_dir / "metadata.toml").exists(), "Session metadata missing"
    assert (rawdata_dir / "Bpod").exists(), "Bpod directory missing"
    assert (rawdata_dir / "TTLs").exists(), "TTLs directory missing"

    # Step 1: Create NWB file from session metadata
    nwbfile = session.create_nwb_file(rawdata_dir / "metadata.toml")
    assert nwbfile.identifier == "Session-000001"
    assert nwbfile.session_description is not None

    # Step 2: Load TTL pulses
    ttl_patterns = {
        "ttl_camera": "TTLs/*frame*.txt",
        "ttl_cue": "TTLs/*cue*.txt",
    }
    ttl_pulses = ttl.get_ttl_pulses(rawdata_dir, ttl_patterns)
    assert "ttl_camera" in ttl_pulses
    assert len(ttl_pulses["ttl_camera"]) > 0

    # Step 3: Parse Bpod data
    bpod_data = bpod.parse_bpod(rawdata_dir, pattern="Bpod/*.mat", order="name_asc", continuous_time=False)
    assert "SessionData" in bpod_data
    n_trials = bpod_data["SessionData"]["nTrials"]
    assert n_trials > 0

    # Step 4: Synchronize trials (with minimal config)
    # Create minimal sync config for test
    from w2t_bkin.config import BpodSyncTrialType

    trial_type_configs = [
        BpodSyncTrialType(trial_type=1, sync_signal="W2T_Audio", sync_ttl="ttl_cue"),
        BpodSyncTrialType(trial_type=2, sync_signal="A2L_Audio", sync_ttl="ttl_cue"),
        BpodSyncTrialType(trial_type=3, sync_signal="Microstim", sync_ttl="ttl_cue"),
    ]

    trial_offsets, warnings = sync.align_bpod_trials_to_ttl(
        trial_type_configs=trial_type_configs,
        bpod_data=bpod_data,
        ttl_pulses=ttl_pulses,
    )
    assert len(trial_offsets) > 0

    # Step 5: Extract TTL table
    ttl_table = ttl.extract_ttl_table(ttl_pulses)
    assert len(ttl_table) > 0

    # Step 6: Extract behavioral data with shared instances
    # Step 6: Extract behavioral data with shared instances (SIMPLIFIED API)
    task, recording, trials = behavior.extract_behavioral_data(bpod_data, trial_offsets)
    assert task is not None
    assert recording is not None
    assert len(trials) == n_trials

    # Step 7: Import pose data (if available)
    pose_dir = interim_dir / "dlc-pose" / "pupil_left"
    if pose_dir.exists():
        pose_files = list(pose_dir.glob("*.h5"))
        if pose_files:
            pose_path = pose_files[0]
            dlc_data = pose.import_dlc_pose(pose_path)
            pose_data, pose_metadata = dlc_data

            # Create skeleton
            skeleton = pose.create_skeleton(
                name="BA_W2T",
                nodes=pose_metadata.bodyparts,
            )
            skeletons = pose.Skeletons(skeletons=[skeleton])

            # Build pose estimation with TTL camera timestamps
            camera_times = ttl_table[:][ttl_table[:]["channel"] == "ttl_camera"]["timestamp"].values
            pose_estimation = pose.build_pose_estimation(
                data=dlc_data,
                reference_times=camera_times,
                skeleton=skeleton,
            )
            assert pose_estimation is not None

    # Step 8: Assemble NWB file
    # Add TTL events
    nwbfile.add_acquisition(ttl_table)

    # Add Task FIRST (contains type tables)
    nwbfile.add_lab_meta_data(task)

    # Add TaskRecording AFTER Task (references type tables from task)
    nwbfile.add_acquisition(recording)

    # Add Trials table
    nwbfile.trials = trials

    # Add Pose if available
    if pose_dir.exists() and pose_files:
        behavior_pm = nwbfile.create_processing_module(
            name="behavior",
            description="Processed behavioral data including pose estimation",
        )
        behavior_pm.add(skeletons)
        behavior_pm.add(pose_estimation)

    # Step 9: Write NWB file
    output_path = output_dir / "test_example_1.nwb"
    with NWBHDF5IO(output_path, mode="w") as io:
        io.write(nwbfile)

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    # Step 10: Validate written file
    with NWBHDF5IO(output_path, mode="r") as io:
        read_nwb = io.read()

        # Validate structure
        assert read_nwb.identifier == "Session-000001"
        assert len(read_nwb.trials) == n_trials
        assert "TTLEvents" in read_nwb.acquisition
        assert "task_recording" in read_nwb.acquisition

        # Validate behavioral data
        task_recording = read_nwb.acquisition["task_recording"]
        assert task_recording.states is not None
        assert task_recording.events is not None
        assert task_recording.actions is not None

        # Validate trials reference data tables
        trial_states = read_nwb.trials["states"]
        assert trial_states is not None

        # Validate pose if present
        if "behavior" in read_nwb.processing:
            behavior_module = read_nwb.processing["behavior"]
            assert "Skeletons" in behavior_module.data_interfaces
            # PoseEstimation is named with skeleton suffix
            pose_estimations = [k for k in behavior_module.data_interfaces.keys() if k.startswith("PoseEstimation")]
            assert len(pose_estimations) > 0, "PoseEstimation not found in behavior module"


def test_pipeline_with_missing_data(test_config, tmp_path):
    """Test pipeline handles missing optional data gracefully."""
    rawdata_dir = test_config["raw_dir"]

    # Test with missing pose data
    interim_dir = tmp_path / "interim_empty"
    interim_dir.mkdir(parents=True, exist_ok=True)

    # Should work without pose data
    nwbfile = session.create_nwb_file(rawdata_dir / "metadata.toml")
    assert nwbfile is not None


def test_pipeline_validates_required_paths(test_config):
    """Test that pipeline validates required paths exist."""
    # Test missing metadata.toml
    with pytest.raises(FileNotFoundError):
        session.create_nwb_file(Path("nonexistent") / "metadata.toml")


def test_object_instance_sharing():
    """Test that type tables and data tables share instances correctly.

    This is a critical test to prevent the ReferenceTargetNotBuiltError
    that occurred in the original example_1.py.
    """
    from w2t_bkin.bpod import parse_bpod

    fixtures_root = Path(__file__).parent.parent / "fixtures"
    rawdata_dir = fixtures_root / "data" / "raw" / "Session-000001"

    # Parse Bpod data
    bpod_data = parse_bpod(
        rawdata_dir,
        pattern="Bpod/*.mat",
        order="name_asc",
        continuous_time=False,
    )

    # Extract type tables once
    state_types = behavior.extract_state_types(bpod_data)
    event_types = behavior.extract_event_types(bpod_data)
    action_types = behavior.extract_action_types(bpod_data)

    # Extract data tables using the same type tables
    states1, _ = behavior.extract_states(bpod_data, state_types, None)
    events1, _ = behavior.extract_events(bpod_data, event_types, None)
    actions1, _ = behavior.extract_actions(bpod_data, action_types, None)

    # Extract again - should create different instances
    states2, _ = behavior.extract_states(bpod_data, state_types, None)
    events2, _ = behavior.extract_events(bpod_data, event_types, None)
    actions2, _ = behavior.extract_actions(bpod_data, action_types, None)

    # Verify instances are different (new calls create new objects)
    assert states1 is not states2
    assert events1 is not events2
    assert actions1 is not actions2

    # But the type tables they reference should be the same
    # (This is what prevents the reference error)
    assert states1.state_type.table is state_types
    assert events1.event_type.table is event_types
    assert actions1.action_type.table is action_types


def test_simplified_api_instance_consistency():
    """Test that the simplified extract_behavioral_data API ensures instance consistency.

    This test validates that the new simplified API properly shares instances
    between Task, TaskRecording, and TrialsTable.
    """
    from w2t_bkin.bpod import parse_bpod

    fixtures_root = Path(__file__).parent.parent / "fixtures"
    rawdata_dir = fixtures_root / "data" / "raw" / "Session-000001"

    # Parse Bpod data
    bpod_data = parse_bpod(
        rawdata_dir,
        pattern="Bpod/*.mat",
        order="name_asc",
        continuous_time=False,
    )

    # Use simplified API
    task, recording, trials = behavior.extract_behavioral_data(bpod_data, trial_offsets=None)

    # Verify all components exist
    assert task is not None
    assert recording is not None
    assert trials is not None

    # Verify instance consistency between TaskRecording and TrialsTable
    # The TrialsTable should reference the EXACT same instances as TaskRecording
    assert trials._states_table is recording.states
    assert trials._events_table is recording.events
    assert trials._action_table is recording.actions

    # Verify type tables are shared
    assert recording.states.state_type.table is task.state_types
    assert recording.events.event_type.table is task.event_types
    assert recording.actions.action_type.table is task.action_types
