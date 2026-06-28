#!/usr/bin/env python3
"""
Web frontend for the Episodic Workflow agent.

A thin Flask layer over agent.orchestrator.Project that exposes each pipeline
step as a JSON endpoint and serves a single-page UI to drive them in order with
live progress. State lives in one in-memory Project per server process (this is a
local single-user tool), recreated whenever you start a new run.

Run:
    set ANTHROPIC_API_KEY (or paste the key into the UI), then:
    python web_app.py
    open http://127.0.0.1:5000
"""
from __future__ import annotations

import os
import traceback

from dotenv import load_dotenv
from flask import Flask, jsonify, request

# Load ANTHROPIC_API_KEY / EPISODIC_AGENT_MODEL from a local .env if present.
load_dotenv()

from agent.orchestrator import Project
from agent.step import StepFailure

app = Flask(__name__)

# Single in-memory project for this server process.
STATE: dict = {"project": None}


def _project() -> Project:
    p = STATE["project"]
    if p is None:
        raise RuntimeError("No active project. Start a new run first.")
    return p


def _first_episode_number(p: Project) -> int:
    if not p.arc_plan:
        raise RuntimeError("Arc plan not generated yet.")
    return p.arc_plan["episodes"][0]["episode_number"]


# ---------------------------------------------------------------- step runners
def step_intake(p: Project) -> dict:
    result = p.run_intake()
    # Mirror the demo: auto-answer the questionnaire with "let AI decide".
    if result.get("questionnaire_items"):
        result["ai_decided_fields"] = [q["field"] for q in result["questionnaire_items"]]
        p.intake_result["ai_decided_fields"] = result["ai_decided_fields"]
    return result


def step_outline(p: Project) -> dict:
    return p.generate_outline()


def step_lock(p: Project) -> dict:
    locked_id = p.lock_outline()
    return {
        "locked_outline_version_id": locked_id,
        "auto_created_assets": [
            {"asset_id": a["asset_id"], "name": a["base_asset_name"]}
            for a in p.assets.values()
        ],
    }


def step_arcs(p: Project) -> dict:
    return p.generate_arc_plan()


def step_script(p: Project) -> dict:
    return p.generate_episode_script(_first_episode_number(p), mode="generate")


def step_extract(p: Project) -> dict:
    return p.generate_episode_script(_first_episode_number(p), mode="extract")


def step_storyboard(p: Project) -> dict:
    return p.generate_storyboard(_first_episode_number(p))


def step_asset(p: Project) -> dict:
    asset_id = next(iter(p.assets))
    return p.generate_asset_prompt(asset_id)


def step_check(p: Project) -> dict:
    ep = _first_episode_number(p)
    episode_id = f"ep_{ep:03d}"
    return p.run_consistency_check(
        object_type="episode_script",
        object_id=episode_id,
        current_snapshot=p.episodes[episode_id]["episode_script"],
        prior_snapshot=None,
    )


STEP_RUNNERS = {
    "intake": step_intake,
    "outline": step_outline,
    "lock": step_lock,
    "arcs": step_arcs,
    "script": step_script,
    "extract": step_extract,
    "storyboard": step_storyboard,
    "asset": step_asset,
    "check": step_check,
}


# ---------------------------------------------------------------------- routes
@app.get("/")
def index():
    return INDEX_HTML


@app.get("/api/status")
def status():
    return jsonify({"api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY"))})


@app.post("/api/new")
def new_run():
    data = request.get_json(force=True) or {}
    idea = (data.get("idea") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
    if not idea:
        return jsonify({"error": "Please enter a series idea."}), 400
    STATE["project"] = Project(raw_input=idea)
    return jsonify({"ok": True, "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY"))})


@app.post("/api/step/<name>")
def run_step_route(name: str):
    runner = STEP_RUNNERS.get(name)
    if runner is None:
        return jsonify({"error": f"Unknown step: {name}"}), 404
    try:
        result = runner(_project())
        return jsonify({"ok": True, "step": name, "result": result})
    except StepFailure as e:
        return jsonify({"ok": False, "step": name, "error": f"Step failure: {e}"}), 502
    except RuntimeError as e:
        return jsonify({"ok": False, "step": name, "error": str(e)}), 400
    except Exception as e:  # surface anything else (e.g. auth/network) to the UI
        traceback.print_exc()
        return jsonify({"ok": False, "step": name, "error": f"{type(e).__name__}: {e}"}), 500


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Episodic Workflow Agent</title>
<style>
  :root {
    --bg:#0e1116; --panel:#161b22; --panel2:#1c232d; --border:#2b3340;
    --text:#e6edf3; --muted:#9aa7b4; --accent:#7c9cff; --accent2:#5a78e0;
    --ok:#3fb950; --run:#d29922; --err:#f85149;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
    font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
  header { padding:22px 28px; border-bottom:1px solid var(--border);
    background:linear-gradient(180deg,#141a22,#0e1116); }
  header h1 { margin:0; font-size:20px; letter-spacing:.2px; }
  header p { margin:4px 0 0; color:var(--muted); font-size:13px; }
  .wrap { max-width:1080px; margin:0 auto; padding:24px 28px 80px; }
  .card { background:var(--panel); border:1px solid var(--border);
    border-radius:12px; padding:18px 20px; margin-bottom:18px; }
  label { display:block; font-size:12px; color:var(--muted); margin-bottom:6px;
    text-transform:uppercase; letter-spacing:.6px; }
  textarea, input[type=text], input[type=password] {
    width:100%; background:var(--panel2); color:var(--text);
    border:1px solid var(--border); border-radius:8px; padding:11px 12px;
    font:inherit; resize:vertical; }
  textarea { min-height:88px; }
  .row { display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin-top:14px; }
  button { cursor:pointer; border:none; border-radius:8px; padding:10px 16px;
    font:inherit; font-weight:600; color:#fff; background:var(--accent2); }
  button:hover { background:var(--accent); }
  button.secondary { background:transparent; color:var(--muted);
    border:1px solid var(--border); font-weight:500; }
  button.secondary:hover { color:var(--text); border-color:var(--accent); background:transparent; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  .linklike { background:none; border:none; color:var(--accent); padding:0;
    font-weight:500; cursor:pointer; font-size:13px; }
  .steps { margin-top:8px; }
  .step { background:var(--panel); border:1px solid var(--border);
    border-radius:12px; margin-bottom:12px; overflow:hidden; }
  .step.active { border-color:var(--accent2); }
  .step-head { display:flex; align-items:center; gap:14px; padding:14px 18px;
    cursor:pointer; }
  .num { width:26px; height:26px; flex:0 0 26px; border-radius:50%;
    background:var(--panel2); border:1px solid var(--border);
    display:grid; place-items:center; font-size:13px; color:var(--muted); }
  .step.done .num { background:var(--ok); color:#04210d; border-color:var(--ok); }
  .step.running .num { background:var(--run); color:#241a02; border-color:var(--run);
    animation:pulse 1s ease-in-out infinite; }
  .step.error .num { background:var(--err); color:#2a0606; border-color:var(--err); }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.45} }
  .step-title { flex:1; font-weight:600; }
  .step-title small { display:block; font-weight:400; color:var(--muted); font-size:12px; }
  .badge { font-size:11px; padding:3px 9px; border-radius:20px; color:var(--muted);
    border:1px solid var(--border); text-transform:uppercase; letter-spacing:.5px; }
  .step.done .badge { color:var(--ok); border-color:var(--ok); }
  .step.running .badge { color:var(--run); border-color:var(--run); }
  .step.error .badge { color:var(--err); border-color:var(--err); }
  .summary { color:var(--muted); font-size:13px; max-width:340px; text-align:right;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .body { display:none; border-top:1px solid var(--border); padding:14px 18px;
    background:#0d1117; }
  .step.open .body { display:block; }
  pre { margin:0; max-height:460px; overflow:auto; font:12.5px/1.55 ui-monospace,
    SFMono-Regular,Consolas,monospace; color:#cdd9e5; white-space:pre-wrap;
    word-break:break-word; }
  .err-text { color:var(--err); }
  .hl { color:var(--accent); }
  .toast { position:fixed; bottom:22px; left:50%; transform:translateX(-50%);
    background:var(--panel2); border:1px solid var(--border); color:var(--text);
    padding:10px 18px; border-radius:10px; opacity:0; transition:opacity .25s;
    pointer-events:none; }
  .toast.show { opacity:1; }
</style>
</head>
<body>
<header>
  <h1>🎬 Episodic Workflow Agent</h1>
  <p>Turn a one-line series idea into outline → arcs → episode script → storyboard → assets → consistency check, powered by Claude.</p>
</header>

<div class="wrap">
  <div class="card">
    <label for="key">Anthropic API key <span id="keyhint" style="text-transform:none;letter-spacing:0"></span></label>
    <input type="password" id="key" placeholder="sk-ant-... (leave blank if set in the server environment)">
    <label for="idea" style="margin-top:16px">Series idea</label>
    <textarea id="idea" placeholder="e.g. A young woman discovers her late grandmother was a master forger..."></textarea>
    <div class="row">
      <button id="run">▶ Run full pipeline</button>
      <button id="reset" class="secondary">Reset</button>
      <button id="sample" class="linklike" type="button">Use sample idea</button>
    </div>
  </div>

  <div class="steps" id="steps"></div>
</div>

<div class="toast" id="toast"></div>

<script>
const SAMPLE = "A young woman discovers her late grandmother was secretly a master forger of antique jewelry, and inherits both her workshop and her unfinished debts to a dangerous collector. Urban revenge short drama, vertical format, fast-paced reveals.";

const STEPS = [
  ["intake","Intake & questionnaire","Agent classifies the idea and flags missing info"],
  ["outline","Script outline","Agent generates title, synopsis, characters"],
  ["lock","Lock outline","System locks outline + auto-creates character assets"],
  ["arcs","Arc planning","Agent plans arcs & episodes (system validates count)"],
  ["script","Episode 1 script","Agent writes the full episode script"],
  ["extract","Derived fields","Agent extracts scenes / props / continuity"],
  ["storyboard","Storyboard split","Agent splits the script into shots"],
  ["asset","Asset prompt","Agent writes an image prompt for a character"],
  ["check","Consistency check","Agent judges a system-provided diff"],
];

const stepsEl = document.getElementById('steps');
const nodes = {};
for (const [id,title,sub] of STEPS) {
  const el = document.createElement('div');
  el.className = 'step';
  el.innerHTML = `
    <div class="step-head">
      <div class="num">${STEPS.findIndex(s=>s[0]===id)+1}</div>
      <div class="step-title">${title}<small>${sub}</small></div>
      <div class="summary"></div>
      <div class="badge">idle</div>
    </div>
    <div class="body"><pre></pre></div>`;
  el.querySelector('.step-head').addEventListener('click', ()=> el.classList.toggle('open'));
  stepsEl.appendChild(el);
  nodes[id] = el;
}

function setState(id, state){ const el=nodes[id];
  el.classList.remove('running','done','error');
  if(state) el.classList.add(state);
  el.querySelector('.badge').textContent = state || 'idle';
}
function setSummary(id, text){ nodes[id].querySelector('.summary').textContent = text||''; }
function setBody(id, obj, isError){
  const pre = nodes[id].querySelector('pre');
  pre.className = isError ? 'err-text' : '';
  pre.textContent = (typeof obj === 'string') ? obj : JSON.stringify(obj, null, 2);
  if(isError) nodes[id].classList.add('open');
}
function summarize(id, r){
  try{
    if(id==='intake') return `${r.input_sufficiency_status} · ${(r.questionnaire_items||[]).length} questions`;
    if(id==='outline') return r.series_title || '';
    if(id==='lock') return `${(r.auto_created_assets||[]).length} assets created`;
    if(id==='arcs') return `${r.episodes.length} episodes, ${(r.arcs||[]).length} arcs`;
    if(id==='script') return `${(r.episode_script||'').length} chars`;
    if(id==='extract') return `${((r.derived||{}).scene_list||[]).length} scenes`;
    if(id==='storyboard') return `${(r.shots||[]).length} shots`;
    if(id==='asset') return r.asset_prompt ? r.asset_prompt.slice(0,60)+'…' : '';
    if(id==='check') return `${r.status} · ${(r.issues||[]).length} issues`;
  }catch(e){}
  return '';
}

let busy = false;
function toast(msg){ const t=document.getElementById('toast'); t.textContent=msg;
  t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2600); }

async function api(path, body){
  const res = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body||{})});
  return {ok: res.ok, data: await res.json()};
}

function resetUI(){
  for(const [id] of STEPS){ setState(id,null); setSummary(id,''); setBody(id,''); nodes[id].classList.remove('open'); }
}

async function runAll(){
  if(busy) return;
  const idea = document.getElementById('idea').value.trim();
  const key = document.getElementById('key').value.trim();
  if(!idea){ toast('Enter a series idea first.'); return; }
  busy = true; document.getElementById('run').disabled = true; resetUI();

  const start = await api('/api/new', {idea, api_key:key});
  if(!start.ok){ toast(start.data.error||'Failed to start'); busy=false; document.getElementById('run').disabled=false; return; }
  refreshKeyHint(start.data.api_key_set);

  for(const [id] of STEPS){
    setState(id,'running');
    const {ok, data} = await api('/api/step/'+id);
    if(ok && data.ok){
      setState(id,'done'); setSummary(id, summarize(id, data.result)); setBody(id, data.result, false);
    } else {
      setState(id,'error'); setSummary(id,'failed');
      setBody(id, (data && data.error) || 'Request failed', true);
      toast('Stopped at "'+id+'". See details below.');
      break;
    }
  }
  busy = false; document.getElementById('run').disabled = false;
}

function refreshKeyHint(isSet){
  document.getElementById('keyhint').textContent = isSet ? '— detected ✓' : '— not set';
  document.getElementById('keyhint').style.color = isSet ? 'var(--ok)' : 'var(--err)';
}

document.getElementById('run').addEventListener('click', runAll);
document.getElementById('sample').addEventListener('click', ()=>{ document.getElementById('idea').value = SAMPLE; });
document.getElementById('reset').addEventListener('click', ()=>{ if(!busy) resetUI(); });

fetch('/api/status').then(r=>r.json()).then(d=>refreshKeyHint(d.api_key_set)).catch(()=>{});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False)
