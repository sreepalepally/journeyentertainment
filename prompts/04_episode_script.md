# Prompt — Step 4.4/4.5 Episode Script Generation, Revision, Extraction

This is one capability reached from two entry points: batch generation from Overview (§4.4) and
on-demand from the Episode Detail page (§4.5). The prompt is the same either way.

## Trigger
- Generate: the system requests a script for an episode that has none yet (batch or on-demand).
- Revise: user requests a revision of an existing `episode_script`.
- Extract: derived fields need (re)extracting from the current `episode_script` (e.g. after an edit).

Exactly one of these three modes runs per call — pass `mode` in the input.

## You receive
- `mode`: "generate" | "revise" | "extract"
- `locked_outline`: full locked outline.
- `arc_plan`: full arc plan.
- `episode_summary`: this episode's entry from the arc plan (number, title, one-line summary, hook,
  turning point, ending direction).
- `neighbor_summaries`: one-line summaries of the previous and next episode, for continuity.
- `existing_episode_script` (only for revise/extract): the current canonical text.
- `revision_instruction` (only for revise): the user's natural-language change request.
- `imported_style_notes` (optional): if this episode's script was originally imported from an uploaded
  script, notes on its format (scene heading style, dialogue markers, action density) to preserve when
  generating neighboring missing episodes.

## Task by mode

**generate**: Write the full `episode_script` realizing the summary, hook, and turning point, staying
continuous with the neighbor summaries and consistent with the locked outline. Do not contradict
established character motivations or the core conflict.

**revise**: Produce `ai_revision_candidate` — a full replacement text reflecting the instruction. Do
NOT touch `episode_script` itself; it stays as the prior canonical value until the user applies the
candidate.

**extract**: Do not regenerate the script. Read `existing_episode_script` and produce only `derived`:
scene_list (with characters/locations actually present in the text — never invented), key_plot_points,
episode_ending, referenced_asset_candidates, continuity_notes. Leave `episode_script` absent in the
output for this mode.

## Output
Return JSON matching `schemas/04_episode_script.schema.json`. Only populate the fields relevant to the
active `mode`; leave the others absent rather than null.

## Eval
- generate: realizes summary/hook/turning point; continuous with neighbors and arc; no contradiction
  with locked outline; exactly one script produced.
- revise: is a candidate only, never overwrites episode_script in the output.
- extract: every scene in scene_list has characters/locations that actually appear in the text — no
  invented entities.
