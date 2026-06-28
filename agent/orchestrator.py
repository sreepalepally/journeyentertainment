"""
The Orchestrator = the "system" half of the Episodic Workflow, per
01-series-workflow-onboarding.md and 03-two-week-mvp-requirements.md.

The system owns: presence checks, versioning, lock status, batch orchestration, asset
records/IDs/lineage, reference binding, diff computation, and render/video handoffs.
The agent (agent.step.run_step) owns: generation, extraction, classification, judgment.

This module is a minimal but real implementation of those system-owned boundaries so the
agent's contracts can actually be exercised end-to-end, matching the §3 Agent Intervention
Demo Path.
"""
from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from typing import Any

from .step import run_step, StepFailure

REQUIRED_INTAKE_FIELDS = [
    "genre", "target_audience", "target_market", "visual_style",
    "total_episode_count", "approx_episode_duration", "core_hook",
]

_id_counter = itertools.count(1)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class Project:
    """In-memory stand-in for the platform's Project + version store."""

    raw_input: str
    structured_metadata: dict[str, Any] = field(default_factory=dict)

    intake_result: dict | None = None
    outline_versions: list[dict] = field(default_factory=list)
    locked_outline_version_id: str | None = None
    arc_plan: dict | None = None
    episodes: dict[str, dict] = field(default_factory=dict)  # episode_id -> {script_version..., episode_script, derived}
    storyboards: dict[str, dict] = field(default_factory=dict)  # episode_id -> storyboard
    assets: dict[str, dict] = field(default_factory=dict)  # asset_id -> asset record (system-owned fields)
    check_runs: list[dict] = field(default_factory=list)

    # ---- §5.1 system presence checks ----
    def presence_check(self) -> dict:
        """Deterministic check of which required fields are already explicit in structured_metadata."""
        found = {f: self.structured_metadata[f] for f in REQUIRED_INTAKE_FIELDS if f in self.structured_metadata}
        return {"fields_found": found, "fields_missing": [f for f in REQUIRED_INTAKE_FIELDS if f not in found]}

    # ---- Step 1: Intake & Questionnaire (agent) ----
    def run_intake(self) -> dict:
        presence = self.presence_check()
        payload = {
            "raw_input": self.raw_input,
            "uploaded_script_excerpt": self.structured_metadata.get("uploaded_script_excerpt", ""),
            "system_presence_check": presence,
        }
        result = run_step("01_intake", payload)
        self.intake_result = result
        return result

    # ---- Step 2: Script Outline (agent) + lock (system) ----
    def generate_outline(self, questionnaire_answers: dict | None = None) -> dict:
        if self.intake_result is None:
            raise RuntimeError("Run intake before outline generation.")
        payload = {
            "intake_context": self.intake_result,
            "questionnaire_answers": questionnaire_answers or {},
            "ai_decided_fields": self.intake_result.get("ai_decided_fields", []),
            "uploaded_script_parse_results": self.structured_metadata.get("uploaded_script_parse_results", {}),
        }
        result = run_step("02_outline", payload)
        version_id = _new_id("outline_v")
        self.outline_versions.append({"version_id": version_id, "content": result, "locked": False})
        return result

    def lock_outline(self) -> str:
        """System-owned: marks the latest outline version as the locked baseline,
        auto-creates initial character assets from visual_image (§3.3 of product spec)."""
        if not self.outline_versions:
            raise RuntimeError("No outline version to lock.")
        latest = self.outline_versions[-1]
        latest["locked"] = True
        self.locked_outline_version_id = latest["version_id"]

        outline = latest["content"]
        for char in outline.get("character_settings", []):
            asset_id = _new_id("asset")
            self.assets[asset_id] = {
                "asset_id": asset_id,
                "asset_type": "character",
                "base_asset_name": next(
                    (c["character_name"] for c in outline["main_characters"] if c["character_id"] == char["character_id"]),
                    char["character_id"],
                ),
                "asset_source": "outline",
                "source_content_reference": char["character_id"],
                "seed_visual_image": char.get("visual_image", ""),
                "generated_image_url": None,  # system handoff, not produced here
                "availability_status": "pending_prompt",
            }
        return self.locked_outline_version_id

    def locked_outline(self) -> dict:
        if not self.locked_outline_version_id:
            raise RuntimeError("Outline is not locked yet.")
        return next(v["content"] for v in self.outline_versions if v["version_id"] == self.locked_outline_version_id)

    # ---- Step 3: Arc Planning (agent), trigger only after lock (system rule) ----
    def generate_arc_plan(self) -> dict:
        if not self.locked_outline_version_id:
            raise RuntimeError("Cannot plan arcs before the outline is locked.")
        outline = self.locked_outline()
        result = run_step("03_arc_planning", {"locked_outline": outline})

        # system-owned validation of the hard contract (not just trust the model)
        expected_count = outline["length"]["episode_count"]
        got_numbers = sorted(e["episode_number"] for e in result["episodes"])
        if got_numbers != list(range(1, expected_count + 1)):
            raise StepFailure(
                f"arc_planning: episode numbering {got_numbers} does not match locked count {expected_count}"
            )
        self.arc_plan = result
        return result

    # ---- Step 4: Overview batch / Episode Detail generation (agent), batching (system) ----
    def generate_episode_script(self, episode_number: int, mode: str = "generate", revision_instruction: str | None = None) -> dict:
        if self.arc_plan is None:
            raise RuntimeError("Run arc planning first.")
        ep_summary = next(e for e in self.arc_plan["episodes"] if e["episode_number"] == episode_number)
        episode_id = f"ep_{episode_number:03d}"

        if mode == "generate" and episode_id in self.episodes:
            raise RuntimeError(  # system rule: batch must not overwrite an already-generated script
                f"{episode_id} already generated; use mode='revise' instead."
            )

        all_eps = sorted(self.arc_plan["episodes"], key=lambda e: e["episode_number"])
        idx = next(i for i, e in enumerate(all_eps) if e["episode_number"] == episode_number)
        neighbors = {
            "previous": all_eps[idx - 1]["episode_one_line_summary"] if idx > 0 else None,
            "next": all_eps[idx + 1]["episode_one_line_summary"] if idx + 1 < len(all_eps) else None,
        }

        payload = {
            "mode": mode,
            "locked_outline": self.locked_outline(),
            "arc_plan": self.arc_plan,
            "episode_summary": ep_summary,
            "neighbor_summaries": neighbors,
            "existing_episode_script": self.episodes.get(episode_id, {}).get("episode_script"),
            "revision_instruction": revision_instruction,
        }
        result = run_step("04_episode_script", payload)

        record = self.episodes.setdefault(episode_id, {"episode_id": episode_id, "script_version_id": None})
        if mode == "generate":
            record["episode_script"] = result["episode_script"]
            record["script_version_id"] = _new_id("ep_script_v")
        elif mode == "revise":
            record["ai_revision_candidate"] = result.get("ai_revision_candidate")
        elif mode == "extract":
            record["derived"] = result.get("derived")
        return result

    def apply_revision(self, episode_number: int) -> None:
        """System-owned: user explicitly applies a previously generated candidate."""
        episode_id = f"ep_{episode_number:03d}"
        record = self.episodes[episode_id]
        candidate = record.pop("ai_revision_candidate", None)
        if not candidate:
            raise RuntimeError("No pending revision candidate to apply.")
        record["episode_script"] = candidate
        record["script_version_id"] = _new_id("ep_script_v")

    # ---- Step 5: Storyboard (agent), reference binding (system) ----
    def resolve_asset_refs_for_script(self, episode_id: str) -> dict[str, str]:
        """System-owned reference binding stub: maps known asset base names appearing in the
        script to a concrete (first/default) asset id. Real system would resolve to a specific
        AssetVersion/Variant the user picked; here we default to the asset_id itself."""
        script = self.episodes[episode_id]["episode_script"]
        resolved = {}
        for asset_id, asset in self.assets.items():
            if asset["base_asset_name"] and asset["base_asset_name"] in script:
                resolved[asset["base_asset_name"]] = asset_id
        return resolved

    def generate_storyboard(self, episode_number: int) -> dict:
        episode_id = f"ep_{episode_number:03d}"
        episode = self.episodes.get(episode_id)
        if not episode or not episode.get("episode_script"):
            raise RuntimeError(  # system rule: storyboard cannot be generated before the script exists
                f"{episode_id} has no episode_script yet; generate it before splitting into shots."
            )
        asset_refs = self.resolve_asset_refs_for_script(episode_id)
        payload = {
            "episode_id": episode_id,
            "latest_episode_script": episode["episode_script"],
            "episode_metadata": next(e for e in self.arc_plan["episodes"] if e["episode_number"] == episode_number),
            "existing_storyboard": self.storyboards.get(episode_id),
            "system_provided_asset_refs": asset_refs,
        }
        result = run_step("05_storyboard", payload)
        result["source_episode_script_version_id"] = episode["script_version_id"]
        self.storyboards[episode_id] = result
        return result

    # ---- Step 6: Assets (agent prompt only), render handoff (system, stubbed) ----
    def generate_asset_prompt(self, asset_id: str, user_prompt: str | None = None) -> dict:
        asset = self.assets[asset_id]
        seed_context = {
            "visual_image": asset.get("seed_visual_image", ""),
            "asset_type": asset["asset_type"],
            "base_asset_name": asset["base_asset_name"],
        }
        payload = {
            "asset_type": asset["asset_type"],
            "source": asset["asset_source"],
            "seed_context": seed_context,
            "user_prompt": user_prompt,
            "existing_asset_prompt": asset.get("asset_prompt"),
        }
        result = run_step("06_assets", payload)
        asset["asset_prompt"] = result["asset_prompt"]
        asset["image_generation_prompt"] = result["image_generation_prompt"]
        asset["visual_assumptions"] = result["visual_assumptions"]
        asset["availability_status"] = "prompt_ready"  # render handoff (system) would happen next, out of scope
        return result

    # ---- Step 7: Consistency Check (agent judgment), diff computation (system, stubbed) ----
    def run_consistency_check(self, object_type: str, object_id: str, current_snapshot: Any, prior_snapshot: Any) -> dict:
        # System-owned diff: minimal stub - real system would do structured field diffing.
        system_computed_diff = {
            "changed": current_snapshot != prior_snapshot,
            "object_type": object_type,
            "object_id": object_id,
        }
        payload = {
            "trigger_object": {"object_type": object_type, "object_id": object_id},
            "current_snapshot": current_snapshot,
            "prior_checked_snapshot": prior_snapshot,
            "system_computed_diff": system_computed_diff,
            "dependency_context": {
                "locked_outline": self.locked_outline() if self.locked_outline_version_id else None,
                "arc_plan": self.arc_plan,
            },
            "check_path_hint": "short",
        }
        result = run_step("07_consistency_check", payload)
        status = "passed" if not result["issues"] else "issues_found"
        self.check_runs.append({"object_type": object_type, "object_id": object_id, "status": status, "issues": result["issues"]})
        return result
