# Commit workflow

Before **any** `git commit`: run the `pre-commit` skill, then wait for the
user's explicit approval. Never commit unprompted.

Commit messages:
- Portuguese, present tense, no accented characters
- Short colon-split headline (no trailing period), blank line, bulleted body
  (~72-column wrap, dashes, mixes technical and player-facing detail)
- **No `Co-Authored-By:` trailer, no "Generated with …" attribution, ever**

Check `git log -3 --format='%B---'` before writing — the style can drift.
