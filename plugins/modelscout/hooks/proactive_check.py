#!/usr/bin/env python3
"""ModelScout — UserPromptSubmit hook (Claude Code).

On every new, substantial prompt it injects a compact, self-contained block
telling the model to show a ModelScout card (task tier, best-fit model, why)
and then act per the user's preference: route the task to a right-sized
subagent, ask with a popup, or stay. "modelscout: ..." settings commands are
handled here directly and never reach the model.

Must never block or break the user's prompt: every failure path exits 0.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "modelscout" / "scripts"
PREFS = SCRIPTS / "prefs.py"
SAVINGS = SCRIPTS / "savings.py"
sys.path.insert(0, str(SCRIPTS))
import prefs  # noqa: E402

ACK = {
    "yes", "y", "yep", "yeah", "ok", "okay", "k", "sure", "go", "go on", "go ahead",
    "continue", "proceed", "next", "thanks", "thank you", "thx", "ty", "cool", "nice",
    "great", "perfect", "done", "lgtm", "yes please", "do it", "sounds good", "no",
    "stop", "wait", "hi", "hello", "hey",
    "ใช่", "ได้", "ได้เลย", "โอเค", "โอเคครับ", "โอเคค่ะ", "ต่อ", "ต่อเลย", "ทำเลย",
    "ขอบคุณ", "ขอบคุณครับ", "ขอบคุณค่ะ", "ดี", "เยี่ยม", "ไม่", "หยุด",
}

T4 = re.compile(r"\b(prove|proof|formal(ly)? verif\w*|novel research|research[- ]grade|"
                r"state[- ]of[- ]the[- ]art|from scratch\b.*\b(compiler|engine|kernel|os)\b)", re.I)
T3 = re.compile(r"(\b(architect\w*|system design|design (a|the|our) \w+ system|debug\w*|root cause|"
                r"race condition|deadlock|memory leak|refactor\w*|migrat\w*|security|vulnerab\w*|"
                r"performance|optimi[sz]\w*|why (does|is|did|do)|strategy|trade-?offs?|algorithm\w*|"
                r"concurren\w*|scalab\w*|investigat\w*|diagnos\w*|redesign|rewrite)\b)|"
                r"ออกแบบ|บั๊ก|ดีบัก|วิเคราะห์|กลยุทธ์|สถาปัตยกรรม", re.I)
T1 = re.compile(r"(\b(rename|typos?|spelling|reformat|format(ting)?|lint|prettier|sort|alphabeti\w*|"
                r"translate|convert|bump|changelog|commit|boilerplate|docstrings?|comments?|"
                r"regex|csv|grep|list (all|the)|find (all|every)|fix (the )?imports?|"
                r"update (the )?version|summari[sz]e)\b)|แปล|คำผิด|จัดรูปแบบ|สรุป", re.I)

FAMILIES = (("haiku", "Haiku", 1), ("sonnet", "Sonnet", 2), ("opus", "Opus", 3),
            ("fable", "Fable", 4), ("mythos", "Mythos", 4))
TIER_MODEL = {"T1": "haiku", "T2": "sonnet", "T3": "opus", "T4": "fable (if available, else opus)"}


def is_trivial(prompt):
    p = re.sub(r"[\s!.?,~]+$", "", prompt.strip().lower())
    if not p or p.startswith("<") or p.startswith("/"):
        return True
    if p in ACK:
        return True
    if T4.search(p) or T3.search(p) or T1.search(p):
        return False
    return len(p) < 12 and not re.search(r"\b(fix|add|make|write|build|create)\b", p)


def guess_tier(prompt):
    for tier, rx in (("T4", T4), ("T3", T3)):
        m = rx.search(prompt)
        if m:
            return tier, m.group(0).strip()
    m = T1.search(prompt)
    if m and len(prompt) < 400:
        return "T1", m.group(0).strip()
    return "T2", "no strong keywords"


def detect_model(transcript_path):
    """Latest model from the transcript tail: an assistant record's model, or a
    newer `/model` command record ("Set model to `x`")."""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 262144))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except Exception:
        return None
    for line in reversed(lines):
        if '"model"' not in line and "Set model to" not in line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("isSidechain"):
            continue
        msg = d.get("message") if isinstance(d.get("message"), dict) else {}
        if d.get("type") == "assistant" and msg.get("model") and msg["model"] != "<synthetic>":
            return msg["model"]
        content = msg.get("content")
        if d.get("type") == "user" and isinstance(content, str) and "Set model to" in content:
            m = re.search(r"Set model to\s+[`*]*([^`*<\n]+)", content)
            if m:
                return m.group(1).strip()
    return None


def model_class(model_id):
    low = (model_id or "").lower()
    for key, name, cls in FAMILIES:
        if key in low:
            return name, cls
    return None, None


def handle_command(cmd):
    c = cmd.strip().lower()
    c = re.sub(r"\s+mode$", "", c)
    try:
        if c in ("", "status", "show", "prefs", "settings"):
            pass
        elif c in prefs.MODES or c in prefs.LEGACY_MODES or c == "on":
            prefs.set_mode("auto" if c == "on" else c)
        elif c in ("quiet", "quiet receipts", "receipts mismatch-only"):
            prefs.set_receipts("mismatch-only")
        elif c in ("loud", "loud receipts", "receipts always", "receipts on"):
            prefs.set_receipts("always")
        elif c == "reset":
            prefs.reset()
        elif c in ("savings", "saved", "report"):
            import subprocess
            r = subprocess.run([sys.executable, str(SAVINGS)], capture_output=True, text=True, timeout=20)
            return r.stdout.strip() or "ModelScout: no savings data yet."
        else:
            m = re.match(r"^(?:default\s+|always\s+)?(t[1-4])\s+(switch|stay|ask|clear)$", c) or \
                re.match(r"^(?:always\s+)?(switch|stay|ask|clear)\s+(?:for\s+)?(t[1-4])$", c)
            if not m:
                return ("ModelScout commands: modelscout: auto | ask | inform | off | status | savings | reset | "
                        "quiet | loud | T1 switch|stay|ask|clear (same for T2–T4)")
            a, b = m.groups()
            tier, action = (a, b) if a.startswith("t") else (b, a)
            prefs.set_default(tier, action)
    except Exception as e:  # noqa: BLE001
        return f"ModelScout: could not save ({e})"
    return "ModelScout settings saved ✓\n" + prefs.describe()


RULES_CLAUDE = {
    "switch": """\
switch → DO NOT ask; delegate now. Call the Agent tool with model="<best-fit>",
  a description starting "ModelScout: " (savings tracking reads it), and a
  self-contained brief (goal, exact files/paths, facts it needs from this
  conversation, constraints, what done looks like). Verify its result
  (diff/output) before reporting; if it is weak, redo it yourself and say so.
  Separable parts: one right-sized subagent per part. Up-tier works too
  (T3 task on a Haiku/Sonnet session → an "opus" subagent).
  Keep the work here (card line 3: "Doing it here — <reason>") only for a
  1–2 tool-call job, destructive/outward-facing steps (push, deploy, delete,
  send, pay), or work that needs the user's answers mid-way.""",
    "ask": """\
ask → before working, call AskUserQuestion once (header "ModelScout"), question
  "<Tier> <tier name> task — <why>. Who should do it?", options in order:
  "Run in a <Best-fit> subagent (Recommended)", "Stay on <current model>",
  "Always use a <Best-fit> subagent for <Tier> tasks", "Always stay for <Tier> tasks".
  For an "Always" option first run: python3 "{prefs}" default <Tier> switch|stay
  Then act on the choice (subagent = the switch procedure).""",
    "stay": """\
stay → do it here. Card line 3: "Staying on <current> (your <Tier> default)".""",
}

RULES_OTHER = {
    "switch": """\
switch → if this host lets you start a subagent on a chosen model, delegate the
  task to the best-fit model with a self-contained brief and verify the result.
  Otherwise give the exact command to switch (e.g. "/model <id>") on card line 3
  and continue on the current model without waiting.""",
    "ask": """\
ask → end the card with: "Reply 1 = switch to <Best-fit>, 2 = stay, 3 = always
  switch for <Tier>, 4 = always stay for <Tier>" and wait for the answer. For 3/4
  run: python3 "{prefs}" default <Tier> switch|stay""",
    "stay": """\
stay → do it here. Card line 3: "Staying on <current> (your <Tier> default)".""",
}


def load_json(path):
    try:
        return json.loads(Path(path).expanduser().read_text())
    except Exception:
        return {}


def provider_picks(host):
    """Best-fit model per tier for non-Claude hosts, from inventory or catalog price bands."""
    prov = {"codex": ("openai", "openai"), "gemini": ("gemini", "google")}.get(host)
    if not prov:
        return None
    inv = load_json("~/.claude/model-inventory.json").get("providers", {}).get(prov[0], {}).get("models")
    models = []
    if isinstance(inv, list):
        models = [(m.get("id"), (m.get("cost_per_1m") or m.get("cost") or {}).get("output"),
                   m.get("release_date") or "") for m in inv if isinstance(m, dict)]
    elif isinstance(inv, dict):
        models = [(k, (v.get("cost") or {}).get("output"), v.get("release_date") or "") for k, v in inv.items()]
    if not models:
        cat = load_json("~/.claude/model-catalog.json").get(prov[1], {}).get("models", {})
        models = [(k, (v.get("cost") or {}).get("output"), v.get("release_date") or "")
                  for k, v in cat.items() if v.get("tool_call")]
    junk = re.compile(r"customtools|image|tts|embed|audio|live|realtime|search|transcribe|codex-mini|-pro-\\d|-\\d{4}$", re.I)
    models = [(i, o, r) for i, o, r in models
              if i and isinstance(o, (int, float)) and o > 0 and not junk.search(i)]
    if not models:
        return None
    newest = max(r for _, _, r in models)
    try:
        months = int(newest[:4]) * 12 + int(newest[5:7]) - 1 - 12
        floor = f"{months // 12}-{months % 12 + 1:02d}"
        recent = [m for m in models if m[2] >= floor] or models
    except Exception:
        recent = models
    by_new = lambda m: (m[2], m[1])
    picks = {}
    for t, (lo, hi) in {"T1": (0, 5), "T2": (5, 20), "T3": (20, 1e9)}.items():
        inband = [m for m in recent if lo < m[1] <= hi or (lo == 0 and m[1] <= hi)]
        if inband:
            picks[t] = max(inband, key=by_new)[0]
    top = max(recent, key=lambda m: (m[1], m[2]))
    picks.setdefault("T3", top[0])
    picks["T4"] = top[0]
    return picks


def build_block(prompt, transcript_path, eff, host):
    tier_hint, basis = guess_tier(prompt)
    model_id = detect_model(transcript_path) if host == "claude" else None
    fam, cls = model_class(model_id)
    current = (f"{model_id} ({fam}, T{cls}-class)" if fam
               else "unknown — use the model id from your own system prompt")
    actions = {t: prefs.action_for(t, eff) for t in prefs.TIERS}
    action_line = " ".join(f"{t}={a}" for t, a in actions.items())
    used = sorted(set(actions.values()), key=["switch", "ask", "stay"].index)
    table = RULES_CLAUDE if host == "claude" else RULES_OTHER
    rules = "\n".join(table[a].replace("{prefs}", str(PREFS)) for a in used)
    if host == "claude":
        fit = f"T1→haiku, T2→sonnet, T3→opus, T4→{TIER_MODEL['T4']}"
        settings = "/modelscout:prefs, or the user types"
        own = ("You cannot switch your own session model; for repeated work of one tier "
               "you may add \"tip: pick <Model> in the model menu\".")
    else:
        picks = provider_picks(host)
        fit = (", ".join(f"{t}→{m}" for t, m in sorted(picks.items())) + " (price-band picks; "
               "prefer models the user actually has)") if picks else \
            "the cheapest model the user has whose price band fits the tier (see the modelscout skill)"
        settings = "the user types"
        own = ""
    receipt = ("If the model FITS, show one quote line: > `🔭 ModelScout` **<Tier> <tier name>** · `<Model>` fits — doing it here"
               if eff["receipts"] == "always" else
               "If the model FITS, show nothing — just do the work.")
    return f"""<modelscout host="{host}" mode="{eff['mode']}" tier-hint="{tier_hint}" hint-basis="{basis}" current-model="{current}" on-mismatch="{action_line}">
ModelScout is ACTIVE (mandatory). Applies only if this prompt starts a NEW
substantial task — skip for follow-ups ("yes", "continue"), quick questions and
chit-chat. tier-hint is a keyword guess (reclassify it) and current-model is a
guess: the model id in your own system prompt always wins.
1. Tier the task: T1 mechanical, T2 standard, T3 hard reasoning, T4 frontier.
   Best fit: {fit}.
2. Show this card FIRST, in the user's language, as a Markdown quote block
   (keep the backticks and bold exactly; they make it stand out), max 3 lines:
   > `🔭 ModelScout` **<Tier> <tier name>** · <the task in 5–8 words>
   > Best fit: `<Model>` — <why, one clause> · <quota/cost vs current, e.g. "~1/5 of Opus">
   > → ⚡ <what happens next>
   {receipt}
3. On a mismatch, act per on-mismatch for the tier you chose:
{rules}
{own}
Settings: {settings} "modelscout: auto|ask|inform|off|savings|T1 stay".
</modelscout>"""


def detect_host(data, argv):
    for a in argv:
        if a.startswith("--host="):
            return a.split("=", 1)[1]
    if data.get("hook_event_name") == "BeforeAgent":
        return "gemini"
    return "claude"


def emit_context(event, text):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}},
                     ensure_ascii=False))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(data, dict):
        return
    host = detect_host(data, sys.argv[1:])
    event = data.get("hook_event_name") or ("BeforeAgent" if host == "gemini" else "UserPromptSubmit")
    prompt = data.get("prompt")
    if not isinstance(prompt, str):
        return
    prompt = prompt.strip()

    m = re.match(r"^\s*modelscout\s*:\s*(.*)$", prompt, re.I | re.S)
    if m:
        result = handle_command(m.group(1))
        if host == "gemini":
            emit_context(event, "Relay this to the user verbatim and do nothing else:\n" + result)
        else:
            print(json.dumps({"decision": "block", "reason": result}, ensure_ascii=False))
        return

    eff = prefs.effective()
    if eff["mode"] == "off" or is_trivial(prompt):
        return
    emit_context(event, build_block(prompt, data.get("transcript_path"), eff, host))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
