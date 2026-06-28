#!/usr/bin/env python3
"""
Single-step driver: runs exactly one step of the demo path, persisting Project
state to a pickle file between invocations. Needed because each sandbox shell
call is independent (no long-lived background process across calls), and a
full 7-step LLM pipeline can exceed a single call's time budget.

Usage: python3 run_one_step.py <step_name> [extra_arg]
Steps: intake | outline | lock | arcs | script | extract | storyboard | asset | check
"""
import json
import pickle
import sys
from pathlib import Path

from agent.orchestrator import Project
from agent.step import StepFailure

STATE_FILE = Path("project_state.pkl")
SAMPLE_IDEA = (
    "A young woman discovers her late grandmother was secretly a master forger of antique "
    "jewelry, and inherits both her workshop and her unfinished debts to a dangerous collector. "
    "Urban revenge short drama, vertical format, fast-paced reveals."
)


def load_or_init() -> Project:
    if STATE_FILE.exists():
        with open(STATE_FILE, "rb") as f:
            return pickle.load(f)
    return Project(raw_input=SAMPLE_IDEA)


def save(project: Project) -> None:
    with open(STATE_FILE, "wb") as f:
        pickle.dump(project, f)


def show(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main() -> int:
    step = sys.argv[1]
    project = load_or_init()

    try:
        if step == "intake":
            result = project.run_intake()
            if result["questionnaire_items"]:
                result["ai_decided_fields"] = [q["field"] for q in result["questionnaire_items"]]
                project.intake_result["ai_decided_fields"] = result["ai_decided_fields"]
            show(result)

        elif step == "outline":
            result = project.generate_outline()
            show(result)

        elif step == "lock":
            locked_id = project.lock_outline()
            print(json.dumps({"locked_outline_version_id": locked_id, "auto_created_assets": list(project.assets.keys())}, indent=2))

        elif step == "arcs":
            result = project.generate_arc_plan()
            show(result)

        elif step == "script":
            ep_num = project.arc_plan["episodes"][0]["episode_number"]
            result = project.generate_episode_script(ep_num, mode="generate")
            show(result)

        elif step == "extract":
            ep_num = project.arc_plan["episodes"][0]["episode_number"]
            result = project.generate_episode_script(ep_num, mode="extract")
            show(result)

        elif step == "storyboard":
            ep_num = project.arc_plan["episodes"][0]["episode_number"]
            result = project.generate_storyboard(ep_num)
            show(result)

        elif step == "asset":
            asset_id = next(iter(project.assets))
            result = project.generate_asset_prompt(asset_id)
            show(result)

        elif step == "check":
            ep_num = project.arc_plan["episodes"][0]["episode_number"]
            episode_id = f"ep_{ep_num:03d}"
            result = project.run_consistency_check(
                object_type="episode_script",
                object_id=episode_id,
                current_snapshot=project.episodes[episode_id]["episode_script"],
                prior_snapshot=None,
            )
            show(result)

        elif step == "summary":
            print(json.dumps({
                "episodes": list(project.episodes.keys()),
                "storyboards": list(project.storyboards.keys()),
                "assets": list(project.assets.keys()),
                "check_runs": len(project.check_runs),
            }, indent=2))

        else:
            print(f"Unknown step: {step}", file=sys.stderr)
            return 2

        save(project)
        return 0

    except StepFailure as e:
        print(f"[STEP FAILURE] {e}", file=sys.stderr)
        save(project)
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        save(project)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
