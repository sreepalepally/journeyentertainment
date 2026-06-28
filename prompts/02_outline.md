# Prompt — Step 4.2 Script Outline

## Trigger
Intake judged sufficient, OR the user explicitly chose to proceed with known gaps.

## You receive
- `intake_context`: the full intake output (input type, inferred fields, etc.).
- `questionnaire_answers`: object of `{field: answer}` for fields the user answered manually.
- `ai_decided_fields`: list of fields the user left to "let AI decide" — you must fill these with a
  concrete, defensible choice the user can review and override.
- `uploaded_script_parse_results` (optional): characters/episodes/gaps already extracted from an
  uploaded script, if any — reuse rather than re-invent.

## Task
Generate the show-level foundation: title, genre, visual style, target market, target audience,
length (episode_count / approx_duration / total_duration), synopsis, core conflict, core hooks, main
characters with full settings, and character relationships.

Rules:
- Every "let AI decide" field must appear in `ai_decided_fields_filled` with the concrete value you
  chose, not left vague.
- Each main character needs a motivation AND a conflict (internal or external) — characters without
  either are incomplete.
- `character_relationships` must only reference character_ids that exist in `main_characters`.
- `visual_image` per character becomes the seed for that character's first asset image prompt later —
  make it concrete (age, appearance, clothing, demeanor), not just a personality description.
- Total `episode_count` is the one number the rest of the pipeline treats as locked once the user locks
  this outline. Pick a number appropriate to the genre/market if not given.

## Output
Return JSON matching `schemas/02_outline.schema.json`.

## Eval
- All required fields present.
- AI-decided fields filled with concrete, reviewable choices.
- Synopsis / core_conflict / core_hooks are coherent with genre + audience + market.
- Every main character has motivation + at least one conflict.
- Relationships reference existing characters only.
