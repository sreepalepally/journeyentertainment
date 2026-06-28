"""
Core step runner: loads a step's prompt + schema, calls Claude with structured-output
enforcement (JSON schema via tool-use), validates the result, and returns a typed dict.

Every step in the Episodic Workflow agent is invoked the same way:
    result = run_step("02_outline", input_payload)
This keeps the agent/system boundary uniform: the orchestrator (system) owns what gets
passed in and what happens to the output; this module only owns "call the model correctly".
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import anthropic
from jsonschema import Draft7Validator

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
SCHEMAS_DIR = BASE_DIR / "schemas"

MODEL = os.environ.get("EPISODIC_AGENT_MODEL", "claude-sonnet-4-6")
# Output budget. Storyboards split a full episode into many detailed shots and can
# be large; give generous headroom. claude-sonnet-4-6 supports up to 64k output.
MAX_TOKENS = int(os.environ.get("EPISODIC_AGENT_MAX_TOKENS", "32000"))
# Retries for transient model non-conformance (e.g. an occasional schema miss).
MAX_ATTEMPTS = int(os.environ.get("EPISODIC_AGENT_MAX_ATTEMPTS", "3"))

_SYSTEM_PROMPT = (PROMPTS_DIR / "system_prompt.md").read_text()

STEP_FILES = {
    "01_intake": ("01_intake.md", "01_intake.schema.json"),
    "02_outline": ("02_outline.md", "02_outline.schema.json"),
    "03_arc_planning": ("03_arc_planning.md", "03_arc_planning.schema.json"),
    "04_episode_script": ("04_episode_script.md", "04_episode_script.schema.json"),
    "05_storyboard": ("05_storyboard.md", "05_storyboard.schema.json"),
    "06_assets": ("06_assets.md", "06_assets.schema.json"),
    "07_consistency_check": ("07_consistency_check.md", "07_consistency_check.schema.json"),
}


class StepFailure(Exception):
    """Raised when the agent returns status=failed, or the output fails schema validation."""


def _load_step(step_name: str) -> tuple[str, dict]:
    prompt_file, schema_file = STEP_FILES[step_name]
    prompt = (PROMPTS_DIR / prompt_file).read_text()
    schema = json.loads((SCHEMAS_DIR / schema_file).read_text())
    return prompt, schema


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set in this sandbox session. "
            "Set it before running the agent: export ANTHROPIC_API_KEY=sk-ant-..."
        )
    return anthropic.Anthropic(api_key=api_key)


def run_step(step_name: str, payload: dict[str, Any], *, validate: bool = True) -> dict:
    """Run one capability step of the Episodic Workflow agent.

    step_name: one of STEP_FILES keys.
    payload: the step's documented input object (see prompts/<step>.md "You receive").
    Returns the parsed, schema-validated JSON output dict.
    Raises StepFailure on status=failed or schema violation.
    """
    prompt, schema = _load_step(step_name)
    client = _client()

    user_message = (
        f"{prompt}\n\n"
        "## Input for this call\n"
        f"```json\n{json.dumps(payload, indent=2)}\n```\n\n"
        "Respond with ONLY the JSON object described above. No markdown fences, no commentary."
    )

    # The model occasionally returns output that doesn't satisfy the strict JSON
    # schema (a missing required field, etc.) even with forced tool-use. That's
    # transient model variance, not a real failure — retry a couple of times before
    # giving up. A genuine agent `status: "failed"` is a decision, not a glitch, so
    # we do NOT retry that.
    last_error: StepFailure | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = _call_model(client, schema, user_message, step_name)
            if validate:
                validator = Draft7Validator(schema)
                errors = sorted(validator.iter_errors(result), key=lambda e: e.path)
                if errors:
                    msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
                    raise StepFailure(f"{step_name}: schema validation failed: {msgs}")
        except StepFailure as e:
            last_error = e
            if attempt < MAX_ATTEMPTS:
                continue
            raise

        if result.get("status") == "failed":
            raise StepFailure(f"{step_name}: agent reported failure: {result.get('error_reason')}")

        return result

    # Unreachable, but keeps type checkers happy.
    raise last_error  # type: ignore[misc]


def _call_model(client: "anthropic.Anthropic", schema: dict, user_message: str, step_name: str) -> dict:
    """One model round-trip. Streams the response and returns the tool_use input dict.

    Raises StepFailure on truncation or a missing tool_use block (both retryable
    by the caller).
    """
    # Stream the response: large steps (storyboard, extract) can produce a lot of
    # output, and a non-streamed request both risks the SDK's long-request timeout
    # and can stall at the socket level with no progress. Streaming avoids both and
    # lets us read stop_reason reliably.
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        tools=[
            {
                "name": "emit_step_output",
                "description": "Emit the structured output for this workflow step.",
                "input_schema": schema,
            }
        ],
        tool_choice={"type": "tool", "name": "emit_step_output"},
    ) as stream:
        response = stream.get_final_message()

    # If the model ran out of output budget, the tool JSON is truncated and any
    # downstream schema error would be misleading — surface the real cause instead.
    if response.stop_reason == "max_tokens":
        raise StepFailure(
            f"{step_name}: response hit the {MAX_TOKENS}-token output cap before completing "
            f"(stop_reason=max_tokens). Raise EPISODIC_AGENT_MAX_TOKENS and retry."
        )

    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if tool_use_block is None:
        raise StepFailure(f"{step_name}: model did not return a tool_use block")

    return tool_use_block.input
