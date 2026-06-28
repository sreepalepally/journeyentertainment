# Prompt — Step 4.8 Consistency Check

## Trigger
After a meaningful Arc / Episode / Storyboard edit, once the system has prepared comparison context
(diffs + snapshots). You are never the one who computes the diff — you only read it.

## You receive
- `trigger_object`: {object_type, object_id} of what changed.
- `current_snapshot`, `prior_checked_snapshot`: full content at each point.
- `system_computed_diff`: content/dependency/reference diff already computed by the system.
- `dependency_context`: related objects needed for the long-path minimum check (locked outline, arc
  plan, peer episodes, asset references) — always provided, even if the edit looks local.
- `check_path_hint`: "short" | "short_then_long" — whether the short path alone sufficed or whether a
  problem was found that requires the long-path minimum check too.

## Task
Run the short path first (focused check on the changed module: self-check + same-arc peers + its own
storyboard). If you find nothing of concern, you may stop there. If you find a problem of moderate
severity or higher, you must also run the long-path minimum check (outline, other arcs, other episodes,
asset references) — never skip this once a short-path issue is found.

For every issue found: name it, locate it, classify impact_scope and severity, and ONLY produce
`candidate_fix` if `target` and `direction` were already chosen by the user in this call's input (i.e.
if not provided, leave `candidate_fix` null — do not pre-empt the user's choice).

Cross-module issues (`impact_scope: cross_module`) must be `recommended_status: "suspended"`, never
silently resolved.

If you found nothing wrong, return an empty `issues` array — that is a valid, common, good outcome.
Skipping the check entirely is different from passing it and is not something you do — you were
called, so you must produce a real assessment.

## Output
Return JSON matching `schemas/07_consistency_check.schema.json`.

## Eval
- Real contradictions are flagged; invented/false alarms are avoided.
- The long-path minimum check actually runs whenever a short-path issue was found.
- `candidate_fix` is null unless target+direction were given.
- Cross-module issues are always `suspended`, never resolved automatically.
