# Prompt — Step 4.6 Storyboard

## Trigger
User splits a script into shots, or revises existing storyboard content.

## You receive
- `episode_id`, `latest_episode_script` (must exist — system blocks this call otherwise).
- `episode_metadata`: title, summary, hook, turning point.
- `existing_storyboard` (optional): if revising.
- `system_provided_asset_refs`: object mapping asset names mentioned in the script to concrete
  `asset_version_or_variant_id` values the system has already resolved from the user's prior
  selections. May be empty/partial — some references stay unresolved until the user picks a version.

## Task
Split `latest_episode_script` into shot-level entries covering every scene/beat in the script — do not
skip content. For each shot, write shot_size, framing, composition, visual_description, action,
optional dialogue/voiceover and mood, and a `video_prompt` suitable for a text-to-video model.

For `referenced_asset_version_or_variant_ids`: only place IDs that exist in
`system_provided_asset_refs`. If a shot references a character/scene/prop with no resolved ID yet,
leave that shot's array empty rather than inventing an ID — the system will resolve it later when the
user selects.

If revising an existing storyboard, preserve shots that aren't affected by the revision request; only
regenerate what's asked.

## Output
Return JSON matching `schemas/05_storyboard.schema.json`.

## Eval
- Every scene/beat in the script is covered by at least one shot.
- Every shot has framing, duration, and video_prompt.
- `referenced_asset_version_or_variant_ids` only ever contains system-provided IDs — never invented
  IDs.
- A revision preserves unaffected shots rather than regenerating everything.
