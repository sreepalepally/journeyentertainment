#!/usr/bin/env python3
"""
CLI demo runner — exercises the §3 Agent Intervention Demo Path from
03-two-week-mvp-requirements.md end to end:

  1. user idea -> 2. intake classification -> 4. outline generation -> 5. lock
  -> 6. arc planning -> 7/8. episode script generation -> 9. extraction
  -> 10. storyboard split -> 11. asset prompts -> 15/16. consistency check

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python demo.py "your series idea here"

If no idea is given, a sample short-drama idea is used.
"""
from __future__ import annotations

import json
import sys

from agent.orchestrator import Project
from agent.step import StepFailure

SAMPLE_IDEA = (
    "A young woman discovers her late grandmother was secretly a master forger of antique "
    "jewelry, and inherits both her workshop and her unfinished debts to a dangerous collector. "
    "Urban revenge short drama, vertical format, fast-paced reveals."
)


def banner(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def show(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main() -> int:
    idea = " ".join(sys.argv[1:]) or SAMPLE_IDEA
    project = Project(raw_input=idea)

    try:
        banner("STEP 1 — Intake & Questionnaire (agent classifies)")
        intake = project.run_intake()
        show(intake)

        # Simulate the user answering any questionnaire items, or letting AI decide.
        answers = {}
        if intake["questionnaire_items"]:
            print("\n(demo: auto-answering questionnaire with 'let AI decide' for all items)")
            intake["ai_decided_fields"] = [q["field"] for q in intake["questionnaire_items"]]

        banner("STEP 2 — Script Outline (agent generates)")
        outline = project.generate_outline(questionnaire_answers=answers)
        show(outline)

        banner("STEP 3 — Lock Outline (system) + auto-create character assets")
        locked_id = project.lock_outline()
        print(f"Locked outline version: {locked_id}")
        print(f"Auto-created assets: {list(project.assets.keys())}")

        banner("STEP 4 — Arc Planning (agent generates, system validates episode count)")
        arc_plan = project.generate_arc_plan()
        show(arc_plan)

        first_ep = arc_plan["episodes"][0]["episode_number"]

        banner(f"STEP 5 — Episode {first_ep} Script Generation (agent)")
        ep_result = project.generate_episode_script(first_ep, mode="generate")
        print(ep_result["episode_script"][:1200] + ("..." if len(ep_result["episode_script"]) > 1200 else ""))

        banner(f"STEP 6 — Episode {first_ep} Derived-Field Extraction (agent)")
        extract_result = project.generate_episode_script(first_ep, mode="extract")
        show(extract_result["derived"])

        banner(f"STEP 7 — Storyboard Split for Episode {first_ep} (agent + system asset binding)")
        storyboard = project.generate_storyboard(first_ep)
        show(storyboard)

        banner("STEP 8 — Asset Prompt Generation (agent, prompt-only)")
        first_asset_id = next(iter(project.assets))
        asset_prompt = project.generate_asset_prompt(first_asset_id)
        show(asset_prompt)

        banner("STEP 9 — Consistency Check on Episode Script (agent judgment, system diff)")
        episode_id = f"ep_{first_ep:03d}"
        check = project.run_consistency_check(
            object_type="episode_script",
            object_id=episode_id,
            current_snapshot=project.episodes[episode_id]["episode_script"],
            prior_snapshot=None,
        )
        show(check)

        banner("DEMO COMPLETE")
        print(f"Episodes generated: {list(project.episodes.keys())}")
        print(f"Storyboards: {list(project.storyboards.keys())}")
        print(f"Assets: {len(project.assets)} ({list(project.assets.keys())})")
        print(f"Consistency check runs: {len(project.check_runs)}")
        return 0

    except StepFailure as e:
        print(f"\n[STEP FAILURE] {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"\n[RUNTIME ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
