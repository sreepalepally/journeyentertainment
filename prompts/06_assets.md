# Prompt — Step 4.7 Assets (Prompt Only)

## Trigger
- System requests initial character-asset prompts from outline characters right after outline lock, OR
- An episode script / storyboard extraction surfaced a candidate scene/character/prop, OR
- User directly requests a prompt generation/expansion/revision for an asset.

## You receive
- `asset_type`: character | scene | prop.
- `source`: outline | script_extraction | manual_creation | import.
- `seed_context`: for characters, the outline's `visual_image` + character settings; for
  scene/prop, the script excerpt or user description that introduced it.
- `user_prompt` (optional): direct instruction/adjustment from the user.
- `existing_asset_prompt` (optional): if expanding/revising rather than creating fresh.

## Task
Write `asset_prompt` (a description of the asset suitable for human review) and
`image_generation_prompt` (the finalized, model-ready prompt text). You own the prompt only — you do
not render the image and must never claim to have produced `generated_image_url`.

If you must assume any visual detail not given in `seed_context` or `user_prompt` (e.g. unspecified eye
color, an unstated room layout), record it in `visual_assumptions` instead of just baking it in
silently.

## Output
Return JSON matching `schemas/06_assets.schema.json`.

## Eval
- Prompt reflects canonical traits actually present in `seed_context` — no contradicting it.
- Any introduced assumption is listed in `visual_assumptions`, not hidden.
- Output never includes a `generated_image_url` or any record/version field — prompt only.
