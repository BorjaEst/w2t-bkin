# Decision Log - Prefect-Friendly Refactoring

## Overview

This document records all major decisions made during the refactoring planning and implementation. Each decision includes context, alternatives considered, rationale, and expected impact.

---

## Decision 1 - December 5, 2025

**Decision**: Rename `tasks/` to `preprocessing/` instead of other alternatives

**Context**:

- Current `tasks/` directory contains `PipelineTask`, `DLCPoseTask`, `SLEAPPoseTask`
- These are preprocessing framework classes, NOT Prefect `@task` decorated functions
- User confusion between framework tasks and Prefect tasks likely
- Need clear separation of concerns

**Options**:

1. Keep `tasks/`, add namespace like `from w2t_bkin.tasks.pipeline import PipelineTask`
2. Rename to `preprocessing/`
3. Rename to `pipeline_tasks/`
4. Rename to `framework/`

**Rationale**:

- Option 2 (`preprocessing/`) chosen because:
  - Clear, descriptive name matches actual purpose
  - Prevents confusion with Prefect `@task` decorator
  - Short, easy to type
  - Follows common Python naming conventions
- Option 1 rejected: Still causes confusion, longer imports
- Option 3 rejected: Too verbose, still has "tasks" in name
- Option 4 rejected: Too generic, unclear purpose

**Impact**:

- Positive: Eliminates naming confusion
- Negative: Requires updating all imports (mitigated with compatibility layer)
- Risk: Low - mechanical change, test suite will catch errors

**Review**: Reassess if user feedback indicates confusion with new name

---

## Decision 2 - December 5, 2025

**Decision**: Rename `orchestration/` to `prefect/` for clarity

**Context**:

- Current `orchestration/` contains mix of Prefect and multiprocessing code
- Not immediately obvious that this module is Prefect-specific
- Future maintainers may add non-Prefect orchestration to this module

**Options**:

1. Keep `orchestration/`, reorganize internally
2. Rename to `prefect/`
3. Rename to `workflows/`
4. Create `prefect/` and keep `orchestration/` for non-Prefect code

**Rationale**:

- Option 2 (`prefect/`) chosen because:
  - Crystal clear that code in this module uses Prefect
  - Follows convention seen in other projects
  - Shorter than alternatives
  - Makes imports explicit: `from w2t_bkin.prefect import batch_process_sessions`
- Option 1 rejected: Doesn't solve clarity issue
- Option 3 rejected: Too generic, many kinds of workflows
- Option 4 rejected: Unnecessary complexity, no current need for non-Prefect orchestration

**Impact**:

- Positive: Clear module purpose, easier onboarding
- Negative: Import changes required
- Risk: Low - mechanical change

**Review**: If non-Prefect orchestration needed in future, create separate module

---

## Decision 3 - December 5, 2025

**Decision**: Implement dual execution modes (monolithic vs phase-level) instead of replacing monolithic

**Context**:

- Current code processes entire session as one black-box task
- Phase functions already exist in `core/pipeline/phases/`
- Phase-level execution provides better observability but adds overhead
- Production users may prioritize speed over observability

**Options**:

1. Replace monolithic with phase-level only
2. Keep only monolithic, don't expose phases
3. **Implement both, user chooses via parameter**
4. Implement both, auto-select based on environment

**Rationale**:

- Option 3 (dual mode with parameter) chosen because:
  - Gives users choice based on their needs
  - Production can use fast monolithic mode
  - Development/debugging can use observable phase mode
  - Simple `use_phases=True/False` parameter
  - Both modes use same underlying phase functions
  - Easy to test both modes for equivalence
- Option 1 rejected: Forces performance penalty on all users
- Option 2 rejected: Loses observability benefits, wastes existing phase structure
- Option 4 rejected: Too magical, users should explicitly choose

**Impact**:

- Positive: Best of both worlds, user flexibility
- Negative: Slightly more code to maintain (2 flow definitions)
- Risk: Low - both modes use same phase functions

**Review**: After 6 months, assess usage patterns - if everyone uses one mode, consider removing the other in v3.0

---

## Decision 4 - December 5, 2025

**Decision**: Maintain backward compatibility layer in v2.x, remove in v3.0

**Context**:

- Renaming modules breaks existing user code
- Users may have scripts, notebooks, deployments using old imports
- Want to avoid forcing immediate updates
- But also want to encourage migration to cleaner API

**Options**:

1. **Compatibility layer with deprecation warnings (v2.x), remove in v3.0**
2. Break immediately, provide migration script
3. Keep compatibility layer forever
4. Version-gated compatibility (remove after date)

**Rationale**:

- Option 1 chosen because:
  - Industry standard approach (Python stdlib, major libraries)
  - Gives users time to migrate (6-12 months)
  - Deprecation warnings nudge toward new API
  - Clean break in major version (v3.0) is acceptable
  - Simple implementation via `__getattr__`
- Option 2 rejected: Too disruptive, poor user experience
- Option 3 rejected: Technical debt forever, confusing dual API
- Option 4 rejected: Date-based breaks are unpredictable

**Impact**:

- Positive: Smooth migration, happy users
- Negative: Maintain two import paths temporarily
- Risk: Low - compatibility layer is simple

**Review**: Set v3.0 target date 12 months after v2.0 release

---

## Decision 5 - December 5, 2025

**Decision**: Split `prefect/flows.py` into multiple modules (tasks, flows, deployments) instead of keeping monolithic file

**Context**:

- Current `orchestration/flows.py` is 354 lines with mixed concerns
- Contains flow definitions, task definitions, deployment code, multiprocessing code
- Difficult to navigate and maintain
- Prefect best practices recommend separation

**Options**:

1. Keep everything in `flows.py`
2. **Split into tasks.py, flows.py, deployments.py, infrastructure.py**
3. Split into flows.py and deployments.py only
4. Create subdirectory: `prefect/flows/`, `prefect/tasks/`, etc.

**Rationale**:

- Option 2 (4-file split) chosen because:
  - Clear separation of concerns
  - Each file <300 lines
  - Easy to find specific code
  - Follows Prefect documentation examples
  - Tasks separate from flows makes dependencies clear
  - Deployments separate enables version control of configs
- Option 1 rejected: Maintains current problems
- Option 3 rejected: Tasks still mixed with flows
- Option 4 rejected: Over-engineering for current code size

**Impact**:

- Positive: Better organization, easier maintenance
- Negative: More files (but not excessive)
- Risk: Low - clear module boundaries

**Review**: If any file exceeds 300 lines, consider further splitting

---

## Decision 6 - December 5, 2025

**Decision**: Wrap phase functions with `@task` decorator instead of modifying phase functions directly

**Context**:

- Phase functions exist in `core/pipeline/phases/` as pure functions
- Need to expose as Prefect tasks for phase-level execution
- Want to keep core logic separate from Prefect concerns
- Phase functions used by both Prefect and non-Prefect code paths

**Options**:

1. **Create thin `@task` wrappers in `prefect/tasks.py`**
2. Add `@task` decorator directly to phase functions
3. Subclass phase functions for Prefect
4. Create Prefect-specific phase implementations

**Rationale**:

- Option 1 (thin wrappers) chosen because:
  - Keeps core logic pure, framework-agnostic
  - Phase functions remain testable without Prefect
  - Easy to configure Prefect-specific settings (retries, tags)
  - Can add Prefect-specific logic in wrapper if needed
  - Clear separation: `core/` is business logic, `prefect/` is orchestration
- Option 2 rejected: Couples core logic to Prefect
- Option 3 rejected: Over-engineering, adds complexity
- Option 4 rejected: Code duplication

**Impact**:

- Positive: Clean architecture, maintainable
- Negative: Tiny amount of boilerplate (7 wrapper functions)
- Risk: Negligible - wrappers are 3-5 lines each

**Review**: If wrappers become complex (>10 lines), reconsider architecture

---

## Decision 7 - December 5, 2025

**Decision**: Configure different retry policies per phase based on failure characteristics

**Context**:

- Different phases have different failure modes
- Some phases more likely to fail transiently (file I/O, network)
- Some phases expensive to retry (GPU inference)
- Prefect allows per-task retry configuration

**Options**:

1. Same retry policy for all phases
2. **Different retry policies per phase based on characteristics**
3. No retries, fail fast
4. Aggressive retries for all

**Rationale**:

- Option 2 (per-phase policies) chosen because:
  - initialization: 1 retry (config loading usually deterministic)
  - discovery: 2 retries (file system can be transiently unavailable)
  - preprocessing: 2 retries, longer delay (GPU can be temporarily busy)
  - ingestion: 1 retry (data loading usually deterministic)
  - synchronization: 2 retries (computational, might hit memory limits)
  - assembly: 1 retry (usually succeeds if data is present)
  - finalization: 1 retry (file write can transiently fail)
- Option 1 rejected: Misses optimization opportunities
- Option 3 rejected: Too fragile for production
- Option 4 rejected: Wastes time on deterministic failures

**Impact**:

- Positive: Robust, optimized for each phase
- Negative: More configuration
- Risk: Low - can tune based on real-world data

**Review**: Monitor failure patterns in production, adjust retry policies

---

## Decision 8 - December 5, 2025

**Decision**: Use `PipelineContext` dataclass for passing state between tasks instead of individual parameters

**Context**:

- Phase functions need config, NWBFile, metadata, session info
- Could pass as separate parameters or as context object
- `PipelineContext` already exists in codebase
- Prefect can serialize/deserialize dataclasses

**Options**:

1. Pass individual parameters to each task
2. **Pass `PipelineContext` object through task chain**
3. Use Prefect context/state management
4. Global state (module-level)

**Rationale**:

- Option 2 (`PipelineContext`) chosen because:
  - Already exists and used by phase functions
  - Clean, type-safe interface
  - Easy to add fields without changing signatures
  - Explicit about what data flows between phases
  - Serializable by Prefect
  - Matches existing code patterns
- Option 1 rejected: 5+ parameters per task, unwieldy
- Option 3 rejected: Prefect context is for metadata, not business data
- Option 4 rejected: Testing nightmare, not thread-safe

**Impact**:

- Positive: Clean, maintainable, type-safe
- Negative: Entire context serialized between tasks (small overhead)
- Risk: Low - proven pattern in existing code

**Review**: Monitor serialization overhead, optimize if needed

---

## Decision 9 - December 5, 2025

**Decision**: Deploy both `batch-processing` (monolithic) and `batch-processing-debug` (phase) deployments

**Context**:

- Dual execution modes available
- Production users want speed
- Debug users want observability
- Prefect allows multiple deployments of same flow

**Options**:

1. Deploy only monolithic
2. Deploy only phase-level
3. **Deploy both with different names and parameters**
4. Deploy one, users override parameters

**Rationale**:

- Option 3 (both deployments) chosen because:
  - Clear naming: `-debug` suffix indicates purpose
  - Pre-configured for different use cases
  - Users don't need to remember parameters
  - Can configure different work queues/pools
  - Easy to document: "Use X for production, Y for debugging"
- Option 1 rejected: Loses observability benefits
- Option 2 rejected: Slower for production
- Option 4 rejected: Requires users to remember magic parameters

**Impact**:

- Positive: Clear, easy to use
- Negative: Two deployment definitions (minimal overhead)
- Risk: Low - just configuration

**Review**: After 3 months, check which deployment is used more

---

## Decision 10 - December 5, 2025

**Decision**: Complete refactoring in 5 incremental phases instead of big-bang approach

**Context**:

- Large refactoring with multiple changes
- Risk of breaking changes
- Need to maintain working codebase
- Want to get feedback early

**Options**:

1. Big-bang: implement everything at once
2. **Incremental: 5 phases with testing between each**
3. Feature flags: implement in parallel branches
4. Parallel: old and new code coexist

**Rationale**:

- Option 2 (5 phases) chosen because:
  - Phase 1: Rename (low risk, establishes foundation)
  - Phase 2: Split modules (medium risk, architecture change)
  - Phase 3: Add phase tasks (high value, new features)
  - Phase 4: Update deployments (production integration)
  - Phase 5: Documentation (user enablement)
  - Can test after each phase
  - Can get feedback and adjust
  - Can stop/pivot if issues discovered
  - Each phase takes 2-6 hours, manageable
- Option 1 rejected: Too risky, hard to debug
- Option 3 rejected: Complex, delays integration
- Option 4 rejected: Confusing, maintenance burden

**Impact**:

- Positive: Lower risk, early feedback, easier debugging
- Negative: Takes longer than big-bang (but safer)
- Risk: Low - incremental is proven approach

**Review**: After each phase, assess and adjust plan if needed

---

## Summary Statistics

**Total Decisions**: 10  
**Date Range**: December 5, 2025  
**Major Categories**:

- Naming/Organization: 5 decisions
- Architecture/Design: 3 decisions
- Process/Timeline: 2 decisions

**Risk Assessment**:

- Low Risk: 9 decisions
- Medium Risk: 1 decision
- High Risk: 0 decisions

**Expected Impact**:

- High Positive: 8 decisions
- Medium Positive: 2 decisions
- Low/Negative: 0 decisions

---

## Future Decisions

### Pending

None currently - planning complete

### Deferred to Implementation

1. Exact retry delay values (may tune based on testing)
2. Work pool/queue configuration (may vary by deployment environment)
3. Logging verbosity levels (will set based on user feedback)
4. Performance optimization thresholds (need baseline metrics first)

### Post-Merge Decisions

1. v3.0 timeline (after 6-12 months of v2.x usage)
2. Removal of compatibility layer (part of v3.0 planning)
3. Additional deployment variants (based on usage patterns)

---

## Review Schedule

- **After Phase 1**: Assess naming choices based on team feedback
- **After Phase 3**: Evaluate performance overhead, may adjust retry policies
- **After Phase 5**: Review all decisions based on complete implementation
- **After 3 months in production**: Usage analysis, consider adjustments
- **Before v3.0**: Review deprecation/removal decisions
