# SLEAP Pose Fixtures

SLEAP typically outputs `.slp` or `.h5` files. For testing, we'll create mock JSON format
that represents the structure we'd parse from SLEAP output.

## Format
```json
{
  "tracks": [...],
  "nodes": ["nose", "left_ear", "right_ear"],
  "frames": [
    {
      "frame_idx": 0,
      "instances": [
        {
          "points": [[x, y], [x, y], ...],
          "scores": [0.95, 0.92, ...]
        }
      ]
    }
  ]
}
```
