## How this file works

- One entry per day under an H2 heading.
- Heading format: `## YYYY-MM-DD – <short title>`.
- Keep it short: plan → work → results → next. Link raw data/notebooks.

### Daily entry template (copy/paste)

```markdown
## YYYY-MM-DD – <short title>

### Plan

- [ ] Task 1
- [ ] Task 2

### Work

- Steps taken, parameters, commands (link scripts/notebooks)

### Results

- Observations, metrics, artifacts (paths/links)

### Next

- [ ] Follow-up 1
- [ ] Follow-up 2
```

---

## 2025-11-04 – Rotation kickoff

### Plan

- [ ] Pre-processing: trim long videos using the same software across all cameras/datasets prior to labeling/training to avoid trimming-induced bias.
- [ ] Standardize output format to NWB for all pipeline files.
- [ ] Trial segmentation (Option 1):
  - [ ] Use DLC features and image-based k-means clustering on video 1 (top–bottom; the only camera with the flash cue) to automatically extract trial start/stop frames.
  - [ ] Export an array of boolean/int flags delimiting trial boundaries for the entire recording session.
- [ ] Tracking strategy:
  - [ ] Use DeepLabCut (DLC) to track whisker movements from the top–bottom camera (video 1).
  - [ ] Use facemap for the other 4 cameras (evaluate SLEAP as an alternative).

### Work

- Project objective: design a pipeline to process rodent behavior video data.
- Recording setup:
  - 5 cameras capturing from different angles.
  - Cameras labeled as videos 1–5; video 1 is the top–bottom view.
  - Mouse whiskers are colored to simplify labeling.
  - Trials are separated using a flashlight cue.
  - Only video 1 contains the flashlight signal that separates trials.
- Trial segmentation approach (Option 1): use DLC-derived features plus image-based k-means clustering on video 1 to auto-detect trial frames and export a per-frame flags array delimiting trial boundaries for the session.
- Cameras monitor the pupils, whiskers, and face of the mouse.

### Results

-

### Next

- [ ]
