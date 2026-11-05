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
PREFS = ROOT / "scripts" / "prefs.py"
sys.path.insert(0, str(PREFS.parent))
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
        else:
            m = re.match(r"^(?:default\s+|always\s+)?(t[1-4])\s+(switch|stay|ask|clear)$", c) or \
                re.match(r"^(?:always\s+)?(switch|stay|ask|clear)\s+(?:for\s+)?(t[1-4])$", c)
            if not m:
                return ("ModelScout commands: modelscout: auto | ask | inform | off | status | reset | "
                        "quiet | loud | T1 switch|stay|ask|clear (same for T2–T4)")
            a, b = m.groups()
            tier, action = (a, b) if a.startswith("t") else (b, a)
            prefs.set_default(tier, action)
    except Exception as e:  # noqa: BLE001
        return f"ModelScout: could not save ({e})"
    return "ModelScout settings saved ✓\n" + prefs.describe()


RULES = {
    "switch": """\
switch → DO NOT ask; delegate now. Call the Agent tool with model="<best-fit>"
  and a self-contained brief (goal, exact files/paths, facts it needs from this
  conversation, constraints, what done looks like). Read its result, verify it
  (diff/output), then report. If it is wrong or weak, redo it yourself and say so.
  Large tasks with separable parts: one right-sized subagent per part.
  Up-tier works too: a T3 task on a Haiku/Sonnet session → an "opus" subagent.
  Keep the work here instead (card line 3: "Doing it here — <reason>") only if
  it is a 1–2 tool-call job, destructive/outward-facing (push, deploy, delete,
  send, pay), or needs the user's answers mid-way.""",
    "ask": """\
ask → before working, call AskUserQuestion once (header "ModelScout"), question
  "<Tier> <tier name> task — <why>. Who should do it?", options in this order:
  "Run in a <Best-fit> subagent (Recommended)", "Stay on <current model>",
  "Always use a <Best-fit> subagent for <Tier> tasks", "Always stay for <Tier> tasks".
  For the two "Always" options first run: python3 "{prefs}" default <Tier> switch|stay
  Then act on the choice (subagent = the switch procedure).""",
    "stay": """\
stay → do it here on the current model. Card line 3: "Staying on <current>
  (your <Tier> default — change with /modelscout:prefs)".""",
}


def build_block(prompt, transcript_path, eff):
    tier_hint, basis = guess_tier(prompt)
    model_id = detect_model(transcript_path)
    fam, cls = model_class(model_id)
    if fam:
        current = f"{model_id} ({fam}, T{cls}-class)"
    else:
        current = "unknown — use the model id from your own system prompt"
    actions = {t: prefs.action_for(t, eff) for t in prefs.TIERS}
    action_line = " ".join(f"{t}={a}" for t, a in actions.items())
    used = sorted(set(actions.values()), key=["switch", "ask", "stay"].index)
    rules = "\n".join(RULES[a].replace("{prefs}", str(PREFS)) for a in used)
    receipt = ("If the model FITS, still show line 1 plus \"<Model> fits — doing it here\"."
               if eff["receipts"] == "always" else
               "If the model FITS, show nothing — just do the work.")
    return f"""<modelscout mode="{eff['mode']}" tier-hint="{tier_hint}" hint-basis="{basis}" current-model="{current}" on-mismatch="{action_line}">
ModelScout is ACTIVE (mandatory). Applies only if this prompt starts a NEW
substantial task — skip for follow-ups ("yes", "continue"), quick questions and
chit-chat. tier-hint is a keyword guess (reclassify it) and current-model is a
transcript guess: the model id in your own system prompt always wins.
1. Tier the task: T1 mechanical, T2 standard, T3 hard reasoning, T4 frontier.
   Best fit: T1→haiku, T2→sonnet, T3→opus, T4→{TIER_MODEL['T4']}.
2. Show this card FIRST, in the user's language, max 3 lines:
   🔭 ModelScout · <Tier> <tier name> — <the task in 5–8 words>
      Best fit: <Model> — <why, one clause> · <quota/cost vs current, e.g. "~1/5 of Opus">
      → <what happens next>
   {receipt}
3. On a mismatch, act per on-mismatch for the tier you chose:
{rules}
You cannot switch your own session model; for repeated work of one tier you may
add "tip: pick <Model> in the model menu". Settings: /modelscout:prefs, or the
user types "modelscout: auto|ask|inform|off|T1 stay".
</modelscout>"""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    prompt = (data.get("prompt") or "").strip()

    m = re.match(r"^\s*modelscout\s*:\s*(.*)$", prompt, re.I | re.S)
    if m:
        print(json.dumps({"decision": "block", "reason": handle_command(m.group(1))}, ensure_ascii=False))
        return

    eff = prefs.effective()
    if eff["mode"] == "off" or is_trivial(prompt):
        return
    print(build_block(prompt, data.get("transcript_path"), eff))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
