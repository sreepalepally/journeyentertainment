# Prompt — Step 4.3 Arc Planning

## Trigger
After the outline is locked. (System enforces lock — you simply receive the locked outline.)

## You receive
- `locked_outline`: the full locked outline output (incl. `length.episode_count`, the hard total).

## Task
Split the series into arcs and write a one-line summary, hook, and turning point for every single
episode from 1 to `length.episode_count`.

Hard rules:
- `episodes` must contain exactly `length.episode_count` entries, numbered 1..N with no gaps or
  duplicates.
- `arcs[].episode_range` entries must be contiguous and non-overlapping, and together cover every
  episode exactly once.
- You may NOT change the total episode count. If you believe the count doesn't fit the story, say so
  in a normal text field is not allowed — there is no such field; just do your best to fit the story to
  the locked count, since changing it requires the user to go back and unlock the outline (system/user
  action, not yours).
- Each arc should ladder up toward `core_conflict` from the outline.

## Output
Return JSON matching `schemas/03_arc_planning.schema.json`.

## Eval
- `episodes` length exactly equals the locked count.
- Ranges contiguous, non-overlapping, full coverage.
- Every episode has a summary, hook, and turning point.
- Arcs are visibly in service of the core conflict, not generic filler.
