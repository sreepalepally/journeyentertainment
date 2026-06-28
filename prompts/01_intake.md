# Prompt — Step 4.1 Intake & Questionnaire

## Trigger
Unstructured or mixed input that needs classification or semantic inference. The system has already
run deterministic presence checks on structured fields; you are called regardless of that result to
classify, infer, detect conflicts, and build a questionnaire for what's still missing.

## You receive
- `raw_input`: the user's free-text idea / prompt / uploaded material (string).
- `uploaded_script_excerpt` (optional): text of an uploaded script, if any.
- `system_presence_check`: object listing which of the required structured fields the system already
  found explicitly stated, and their values.

Required fields (system checks presence; you do the rest): genre, target_audience, target_market,
visual_style, total_episode_count, approx_episode_duration, core_hook.

## Task
1. Classify `input_type`: idea | reference | full_script | partial_script | mixed.
2. Decide `input_sufficiency_status`: sufficient | missing_info | conflicting.
3. For every required field NOT already found by the system presence check, try to infer it from the
   free text. If you can infer it confidently, put it in `inferred_fields`. If it's present but
   ambiguous, put the field name in `ambiguous_fields`. If genuinely absent, it needs a questionnaire
   item.
4. Detect contradictions between stated facts (e.g. "realistic urban drama" + "high-magic worldview")
   and list them in `conflict_flags`.
5. Build `questionnaire_items` only for fields that are still missing after inference — never ask about
   a field already present in `system_presence_check` or successfully inferred.
6. `ai_decided_fields` starts empty here — it gets populated later when the user actually picks "let AI
   decide" in the questionnaire UI. Leave it as `[]` in this step's output.

## Output
Return JSON matching `schemas/01_intake.schema.json`.

## Eval (you will be checked against this)
- Type & sufficiency judgment must be defensible from the text.
- Every required field not in the presence check is inferred, flagged ambiguous, or asked about — none
  silently dropped.
- No questionnaire item for a field already present or already inferred.
