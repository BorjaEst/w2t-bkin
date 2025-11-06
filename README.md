# W2T Body Kinematics — Daily log

This README doubles as a lightweight daily lab notebook for the project. Keep entries short and useful, and link to scripts, notebooks, and data when relevant.

## Base information (editable)

- Objective: design a pipeline to process rodent behavior video data.
- Recording setup:
  - 5 cameras capturing from different angles.
  - Cameras labeled as videos 1–5; video 1 is the top–bottom view.
  - Mouse whiskers are colored to simplify labeling.
  - Trials are separated using a flashlight cue.
  - Only video 1 contains the flashlight signal that separates trials.
- Trial segmentation (current approach):
  - Use DLC-derived features plus image-based k-means clustering on video 1 to auto-detect trial frames.
  - Export a per-frame boolean/int flags array delimiting trial boundaries for the session.
- Tracking strategy (current):
  - Use DeepLabCut (DLC) to track whisker movements from the top–bottom camera (video 1).
  - Use facemap for the other 4 cameras (evaluate SLEAP as an alternative).
- Data standard: NWB for pipeline outputs.

## Current plan (editable)

- [ ] Pre-processing: trim long videos using the same software across all cameras/datasets prior to labeling/training to avoid trimming-induced bias.
- [ ] Standardize output format to NWB for all pipeline files.
- [ ] Trial segmentation automation on video 1 using DLC features + k-means; export trial boundary flags.
- [ ] Tracking: DLC on video 1; facemap on other 4 (evaluate SLEAP alternative).
- [ ] Outline initial contributor docs and project README in `docs/`.

## How to use

- Keep "Base information" and "Current plan" at the top up to date as the project evolves.
- Add one daily note per day under an H2 heading.
- Heading format: `## YYYY-MM-DD – <short title>`.
- Daily notes are concise bullets about what happened; link to assets instead of pasting long outputs (e.g., `notebooks/`, `data/`, `reports/`).

### New entry template

<details>
<summary>Click to copy the template</summary>

```markdown
## YYYY-MM-DD – <short title>

- Note 1 (steps taken, parameters, commands, links)
- Note 2 (observations, metrics, artifacts paths/links)
```

</details>

---

## 2025-11-06 – Defining the project skeleton

- Repository scaffolded based on Cookiecutter Data Science (with changes). GitHub project: `w2t-bkin`.
- Licensing initialized for open science reuse: added `LICENSE` (Apache-2.0).

## 2025-11-04 – Rotation kickoff

- Documented base recording setup and initial segmentation/tracking approach (see top sections).
- Confirmed cameras monitor pupils, whiskers, and face of the mouse.
