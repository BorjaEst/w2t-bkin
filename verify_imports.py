#!/usr/bin/env python3
"""Verify all module imports work correctly after Phase 2 refactoring."""

import sys

def test_imports():
    """Test that all key modules can be imported."""
    errors = []
    
    # Test main package
    try:
        import w2t_bkin
        print("✓ w2t_bkin")
    except Exception as e:
        errors.append(f"✗ w2t_bkin: {e}")
    
    # Test renamed bpod module
    try:
        from w2t_bkin import bpod
        print("✓ w2t_bkin.bpod")
    except Exception as e:
        errors.append(f"✗ w2t_bkin.bpod: {e}")
    
    try:
        from w2t_bkin.bpod import parse_bpod, merge_bpod_sessions
        print("✓ w2t_bkin.bpod (functions)")
    except Exception as e:
        errors.append(f"✗ w2t_bkin.bpod (functions): {e}")
    
    # Test new behavior module
    try:
        from w2t_bkin import behavior
        print("✓ w2t_bkin.behavior")
    except Exception as e:
        errors.append(f"✗ w2t_bkin.behavior: {e}")
    
    try:
        from w2t_bkin.behavior import (
            extract_state_types,
            extract_states,
            extract_event_types,
            extract_events,
            extract_action_types,
            extract_actions,
            build_trials_table,
            build_task_recording,
            extract_task_arguments,
            build_task,
        )
        print("✓ w2t_bkin.behavior functions")
    except Exception as e:
        errors.append(f"✗ w2t_bkin.behavior functions: {e}")
    
    # Test ndx-structured-behavior
    try:
        from ndx_structured_behavior import (
            Task,
            TaskSchema,
            TrialsTable,
            TaskRecording,
        )
        print("✓ ndx_structured_behavior")
    except Exception as e:
        errors.append(f"✗ ndx_structured_behavior: {e}")
    
    # Test other key modules
    try:
        from w2t_bkin import pose, nwb, pipeline, sync
        print("✓ w2t_bkin.pose, nwb, pipeline, sync")
    except Exception as e:
        errors.append(f"✗ Other modules: {e}")
    
    # Test ndx-pose
    try:
        from ndx_pose import PoseEstimation, Skeleton
        print("✓ ndx_pose")
    except Exception as e:
        errors.append(f"✗ ndx_pose: {e}")
    
    if errors:
        print("\n❌ IMPORT ERRORS:")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print("\n✅ All imports successful!")
        return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
