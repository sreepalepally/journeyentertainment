# Episodic Workflow Agent — MVP

Implements the 8 agent-owned capability contracts from `03-two-week-mvp-requirements.md`
§4 (Intake, Outline, Arc Planning, Episode Script generate/revise/extract, Storyboard,
Assets prompt-only, Consistency Check), with a thin Python "system" layer
(`agent/orchestrator.py`) that enforces the boundaries the spec reserves for the
platform (locking, version IDs, episode-count validation, asset records, diff input,
etc.) so the agent never has to be trusted to self-police those rules.

## Layout

```
schemas/    JSON Schema (draft-07) for each step's output — the typed contract.
prompts/    system_prompt.md (shared boundaries) + one prompt per step.
agent/
  step.py         Calls Claude with forced tool-use so output matches the schema exactly,
                  then validates it with jsonschema and raises StepFailure on any violation.
  orchestrator.py The "system": Project dataclass, presence checks, outline locking,
                  episode-count enforcement, asset record creation, reference binding,
                  diff stubs feeding the consistency-check step.
demo.py            Runs the full 9-step demo path in one process, end to end.
run_one_step.py    Same pipeline but one step per invocation, persisting state to
                   project_state.pkl between runs — use this if you want to inspect
                   each step's raw output before moving to the next.
```

## Setup

```bash
cd episodic_workflow
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run the full demo

```bash
python3 demo.py "your series idea here"
# or with no args, uses a built-in sample idea
python3 demo.py
```

This runs, in order: intake classification → outline generation → outline lock
(system) → arc planning → episode script generation → derived-field extraction →
storyboard split → asset prompt generation → consistency check. Each step's raw
JSON output prints to stdout as it completes.

## Run one step at a time

Useful for inspecting/debugging a single step without re-running the whole chain:

```bash
python3 run_one_step.py intake
python3 run_one_step.py outline
python3 run_one_step.py lock
python3 run_one_step.py arcs
python3 run_one_step.py script
python3 run_one_step.py extract
python3 run_one_step.py storyboard
python3 run_one_step.py asset
python3 run_one_step.py check
```

State persists in `project_state.pkl` in the working directory. Delete it to start
a fresh project. Steps must be run in the order above (each depends on the previous).

## Verifying against the spec's eval criteria

Check generated output against each prompt file's "Eval" section, e.g.:
- `prompts/03_arc_planning.md` — episode numbering must exactly equal
  `range(1, locked_outline.length.episode_count + 1)`, contiguous non-overlapping
  scene ranges per episode. The orchestrator (`generate_arc_plan`) already
  hard-enforces the episode-count check in Python and raises `StepFailure` if violated
  — that's a good first signal something's off in the prompt or model output if it fires.
- `prompts/07_consistency_check.md` — the agent must judge the system-provided diff,
  never compute its own; cross-module issues must come back `status: "suspended"`,
  never auto-resolved.

## Notes

- `episode_script` is the single canonical text field for episode content. All other
  derived fields (scenes, plot points, etc.) come from the `extract` mode and must never
  be used to overwrite it.
- Model defaults to `claude-sonnet-4-6`; override with `EPISODIC_AGENT_MODEL`.
- If you're behind a corporate proxy with TLS interception, you may need to set
  `SSL_CERT_FILE` to your system CA bundle (the `anthropic` SDK uses `certifi` by
  default, which won't trust a corporate MITM cert).
"# journeyentertainment" 
