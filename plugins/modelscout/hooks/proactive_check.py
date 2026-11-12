#!/usr/bin/env python3
"""ModelScout — UserPromptSubmit hook (Claude Code).

On every new, substantial prompt it injects a compact, self-contained block
telling the model to show a ModelScout card (task tier, best-fit model, why)
and then act per the user's preference: route the task to a right-sized
subagent, ask with a popup, or stay. "modelscout: ..." settings commands are
handled here directly and never reach the model.

Must never block or break the user's prompt: every failure path exits 0.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "modelscout" / "scripts"
PREFS = SCRIPTS / "prefs.py"
SAVINGS = SCRIPTS / "savings.py"


def _load(name, path):
    """Load a sibling script by path under a private module name, so the
    plugin never edits sys.path or claims a generic name like `prefs`."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


prefs = _load("modelscout_prefs", PREFS)
catalog = _load("modelscout_catalog", SCRIPTS / "catalog.py")
outcomes = _load("modelscout_outcomes", SCRIPTS / "outcomes.py")


def savings_text(days=30):
    """The measured savings report, computed in-process."""
    return _load("modelscout_savings", SAVINGS).text_report(days=days)

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
                r"concurren\w*|scalab\w*|investigat\w*|diagnos\w*|redesign|rewrite|audit\w*|code review|"
                r"review (this|the|my|our) (pr|code|diff|plugin|design|change\w*|patch|codebase))\b)|"
                r"ออกแบบ|บั๊ก|ดีบัก|วิเคราะห์|กลยุทธ์|สถาปัตยกรรม|ตรวจสอบ|รีวิวโค้ด", re.I)
T1 = re.compile(r"(\b(rename|typos?|spelling|reformat|format(ting)?|lint|prettier|sort|alphabeti\w*|"
                r"translate|convert|bump|changelog|commit|boilerplate|docstrings?|comments?|"
                r"regex|csv|grep|list (all|the)|find (all|every)|fix (the )?imports?|"
                r"update (the )?version|summari[sz]e)\b)|แปล|คำผิด|จัดรูปแบบ|สรุป", re.I)

FAMILIES = (("haiku", "Haiku", 1), ("sonnet", "Sonnet", 2), ("opus", "Opus", 3),
            ("fable", "Fable", 4), ("mythos", "Mythos", 4))
TIER_MODEL = {"T1": "haiku", "T2": "sonnet", "T3": "opus", "T4": "fable (if available, else opus)"}


ACK_LEAD = sorted(ACK, key=len, reverse=True)  # longest first: "go ahead" before "go"
FOLLOWUP_MAX_CHARS = 30
FOLLOWUP_MAX_WORDS = 3


def ack_followup(p):
    """True for a short reply that opens with an acknowledgement plus a brief
    clause ("yes, test it", "ok, go on", "ได้เลย ทดสอบด้วย"). The rest after the
    acknowledgement must be at most 3 words, so "sure, write a poem about cats"
    still counts as a new task."""
    if len(p) > FOLLOWUP_MAX_CHARS:
        return False
    for ack in ACK_LEAD:
        if p.startswith(ack):
            rest = p[len(ack):]
            # whole-word match only: "no" must not match "node", "ไม่" not "ไม่ทำงาน"
            if rest and not re.match(r"[\s,.!?;:~\-–—]", rest):
                continue
            rest = re.sub(r"^[\s,.!?;:~\-–—]+", "", rest)
            return len(rest.split()) <= FOLLOWUP_MAX_WORDS
    return False


SLASH_CMD = re.compile(r"^/[\w:-]+(\s|$)")
HARNESS_TAG = re.compile(r"^</?[a-z]+-[a-z-]+[\s>]")


def is_trivial(prompt):
    p = re.sub(r"[\s!.?,~]+$", "", prompt.strip().lower())
    if not p or SLASH_CMD.match(p) or HARNESS_TAG.match(p):
        return True
    if p in ACK:
        return True
    if T4.search(p) or T3.search(p) or T1.search(p):
        return False
    if ack_followup(p):
        return True
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
        if '"model"' not in line and "<local-command-stdout>Set model to" not in line:
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
        if d.get("type") == "user" and isinstance(content, str) and "<local-command-stdout>Set model to" in content:
            m = re.search(r"<local-command-stdout>Set model to\s+[`*]*([^`*<\n]+)", content)
            if m:
                return m.group(1).strip()
    return None


def model_class(model_id):
    low = (model_id or "").lower()
    for key, name, cls in FAMILIES:
        if key in low:
            return name, cls
    return None, None


CMD_PREFIX = re.compile(r"^\s*modelscout\s*:\s*(.*)$", re.I | re.S)
TIER_CMD = (re.compile(r"^(?:default\s+|always\s+)?(t[1-4])\s+(switch|stay|ask|clear)$"),
            re.compile(r"^(?:always\s+)?(switch|stay|ask|clear)\s+(?:for\s+)?(t[1-4])$"))
SETTING_WORDS = {"", "status", "show", "prefs", "settings", "on", "quiet", "quiet receipts",
                 "receipts mismatch-only", "loud", "loud receipts", "receipts always", "receipts on",
                 "reset", "savings", "saved", "report", "help",
                 "refresh", "update", "refresh catalog", "update catalog", "catalog",
                 "catalog on", "catalog off", "auto-refresh on", "auto-refresh off",
                 "weak", "outcomes", "forget"}


def _norm(cmd):
    return re.sub(r"\s+mode$", "", re.sub(r"[\s.!]+$", "", cmd.strip().lower()))


def parse_command(prompt):
    """The settings command in a "modelscout: <setting>" prompt, or None.

    Only recognised settings count. Anything else, such as a delegated goal
    "ModelScout: rename the field…", is a normal prompt and must run."""
    m = CMD_PREFIX.match(prompt or "")
    if not m:
        return None
    c = _norm(m.group(1))
    if (c in SETTING_WORDS or c in prefs.MODES or c in prefs.LEGACY_MODES
            or any(rx.match(c) for rx in TIER_CMD)):
        return c
    return None


def catalog_command(host=None):
    """Refresh the models.dev catalog now. On Hermes the plugin makes no
    network calls: Hermes keeps its own cache fresh, so just report it."""
    if host == "hermes":
        return ("ModelScout: Hermes keeps the model catalog fresh itself; ModelScout reads it.\n"
                + catalog.status())
    ok, msg = catalog.refresh(timeout=20)
    return f"ModelScout: {msg}\n" + catalog.status()


def handle_command(cmd, host=None):
    c = _norm(cmd)
    try:
        if c in ("", "status", "show", "prefs", "settings"):
            off = "" if host == "hermes" or prefs.catalog_auto_refresh() else " · auto-refresh off"
            return ("ModelScout settings\n" + prefs.describe() + "\n" + catalog.status() + off
                    + "".join("\n" + ln for ln in outcomes.learned_lines()))
        elif c in ("refresh", "update", "refresh catalog", "update catalog", "catalog"):
            return catalog_command(host)
        elif c == "weak":
            r = outcomes.mark_last_weak()
            if r is None:
                return "ModelScout: no routed subagent recorded yet."
            return (f"ModelScout: noted — the last {r.get('tier') or ''} {r.get('model') or 'subagent'} "
                    "result was weak. ModelScout learns from this.")
        elif c == "forget":
            outcomes.forget()
            return "ModelScout: learned adjustments cleared."
        elif c == "outcomes":
            return "ModelScout " + outcomes.summary()
        elif c in ("catalog on", "auto-refresh on", "catalog off", "auto-refresh off"):
            on = c.endswith(" on")
            prefs.set_catalog_auto_refresh(on)
            return ("ModelScout settings saved ✓\nCatalog auto-refresh: "
                    + ("on (weekly, in the background)" if on else "off (refresh with `modelscout: refresh`)"))
        elif c in prefs.MODES or c in prefs.LEGACY_MODES or c == "on":
            prefs.set_mode("auto" if c == "on" else c)
        elif c in ("quiet", "quiet receipts", "receipts mismatch-only"):
            prefs.set_receipts("mismatch-only")
        elif c in ("loud", "loud receipts", "receipts always", "receipts on"):
            prefs.set_receipts("always")
        elif c == "reset":
            prefs.reset()
            outcomes.forget()
        elif c in ("savings", "saved", "report"):
            return savings_text().strip() or "ModelScout: no savings data yet."
        else:
            m = TIER_CMD[0].match(c) or TIER_CMD[1].match(c)
            if not m:
                return ("ModelScout commands: modelscout: auto | ask | inform | off | status | savings | weak | forget | refresh | reset | "
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
  a description starting "ModelScout: <Tier> · " (e.g. "ModelScout: T1 · rename
  user_id"; savings and outcome tracking read it), and a
  self-contained brief (goal, exact files/paths, facts it needs from this
  conversation, constraints, what done looks like). Verify its result
  (diff/output) before reporting; if it is weak, redo it yourself, say so, and
  run: python3 "{outcomes}" weak   (ModelScout learns from it).
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
  task to the best-fit model now with a self-contained brief whose goal starts
  with "ModelScout: <Tier> · " (e.g. "ModelScout: T1 · rename user_id"; savings
  and outcome tracking read it), then verify the result. If it is weak, redo
  it yourself, say so, and if you can run commands run:
  python3 "{outcomes}" weak   (ModelScout learns from it).
  Hermes: call delegate_task and set the task's `option` to the model route
  whose description matches the tier (the routes listed in delegate_task are
  the user's own; their models are the real best-fit choices).
  Keep the work here (card line 3: "Doing it here — <reason>") only for a
  1–2 tool-call job, destructive/outward-facing steps, or work that needs the
  user's answers mid-way. With no way to pick a model, give the exact command
  to switch (e.g. "/model <id>") on card line 3 and continue on the current
  model without waiting.""",
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


PROVIDER_KEYS = {"openai": ("openai", "openai"), "anthropic": ("anthropic", "anthropic"),
                 "gemini": ("gemini", "google")}


def model_provider(model_id):
    """Provider family of a model id such as "gpt-6-sol" or "anthropic/claude-opus-5"."""
    m = (model_id or "").lower().rsplit("/", 1)[-1]
    if re.match(r"(gpt|o\d|chatgpt)", m):
        return "openai"
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gemini"):
        return "gemini"
    return None


SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]-]{0,79}")


def safe_id(s):
    """The model id if it is plain id-shaped text, else None (ids reach the prompt)."""
    return s if isinstance(s, str) and SAFE_ID.fullmatch(s) else None


JUNK = re.compile(r"customtools|image|tts|embed|audio|live|realtime|search|transcribe|codex-mini|"
                  r"-pro-\d|-latest$|-\d{4}$|-\d{8}$|-\d{4}-\d{2}-\d{2}$", re.I)


def usable(models):
    return [(i, o, r) for i, o, r in models
            if safe_id(i) and isinstance(o, (int, float)) and not isinstance(o, bool) and o > 0
            and not JUNK.search(i)]


def _months(date):
    """"2026-11-09" → a month count; 0 when the date is missing or malformed."""
    try:
        return int(date[:4]) * 12 + int(date[5:7])
    except (TypeError, ValueError):
        return 0


def provider_picks(host, host_model=None):
    """Best-fit model per tier for non-Claude hosts, from inventory or catalog price bands.
    Hermes can run any provider, so it uses the current model's provider."""
    key = {"codex": "openai", "gemini": "gemini"}.get(host) or model_provider(host_model)
    prov = PROVIDER_KEYS.get(key)
    if not prov:
        return None
    inv = load_json("~/.claude/model-inventory.json").get("providers", {}).get(prov[0], {}).get("models")
    models = []
    if isinstance(inv, list):
        models = [(m.get("id"), (m.get("cost_per_1m") or m.get("cost") or {}).get("output"),
                   m.get("release_date") or "") for m in inv if isinstance(m, dict)]
    elif isinstance(inv, dict):
        models = [(k, (v.get("cost") or {}).get("output"), v.get("release_date") or "") for k, v in inv.items()]
    models = usable(models)
    if not models:
        cat = catalog.load().get(prov[1], {}).get("models", {})
        models = usable([(k, (v.get("cost") or {}).get("output"), v.get("release_date") or "")
                         for k, v in cat.items() if v.get("tool_call")])
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
    for t, ok in {"T1": lambda o: o <= 5, "T2": lambda o: 5 < o < 20}.items():
        inband = [m for m in recent if ok(m[1])]
        if inband:
            picks[t] = max(inband, key=by_new)[0]
    top = max(recent, key=lambda m: (m[1], m[2]))
    frontier = [m for m in recent if m[1] >= 20]
    t4 = max(frontier, key=by_new) if frontier else top
    # A provider whose current flagship is cheap (no $20+ model in the last 6
    # months): the flagship serves T3 and T4, not an older, pricier model.
    current = [m for m in recent if _months(newest) - _months(m[2]) <= 6]
    if current and t4 not in current:
        frontier, t4 = [], max(current, key=lambda m: (m[1], m[2]))
    below = [m for m in frontier if m[1] < t4[1]]
    picks["T3"] = max(below, key=by_new)[0] if below else t4[0]
    picks["T4"] = t4[0]
    return picks


def learned_bumps(picks, av=None, exact=False, keep=None):
    """Learned routing. `picks` maps tier -> the model it would use (aliases on
    Claude, catalog ids elsewhere). A T1-T3 pick that is avoided for its tier
    takes the next tier's pick (one step, from the original picks, never T4).
    Avoided models that matched no pick get a "use the next stronger route" note,
    limited by `keep(model_id)` to models this host could route to (outcomes are
    shared across hosts, so a Hermes model must not show up in a Claude block).
    Returns (adjusted picks, notes); never raises, and returns the picks unchanged
    on any failure."""
    try:
        av = outcomes.avoided() if av is None else av
        av = [a for a in av if a.get("tier") in ("T1", "T2", "T3") and safe_id(a.get("model"))]
        if not av:
            return picks, []
        hit = lambda p, m: bool(p) and (p == m if exact else p.lower() in m.lower() or m.lower() in p.lower())
        out, bumps, used = dict(picks), [], set()
        for t, nxt in (("T1", "T2"), ("T2", "T3"), ("T3", "T4")):
            p, new = picks.get(t), picks.get(nxt)
            a = next((a for a in av if a["tier"] == t and hit(p, a["model"])), None)
            if a is None or not new or new == p:
                continue
            if not exact and p.lower() in new.lower() and " (" in new:  # "fable (if available, else opus)"
                new = new.split(" (")[0]
            out[t] = new
            used.add(id(a))
            bumps.append(f"{t} → {new}, not {p} ({int(a['weak'])} of {int(a['n'])} recent {t} results on "
                         f"{a['model']} were weak)")
        rest = [f"{a['tier']}: avoid {a['model']}, use the next stronger route ({int(a['weak'])} of "
                f"{int(a['n'])} recent {a['tier']} results on it were weak)" for a in av if id(a) not in used and (keep is None or keep(a["model"]))]
        return out, bumps + rest
    except Exception:  # noqa: BLE001 - learning must never break the block
        return picks, []


def build_block(prompt, transcript_path, eff, host, host_model=None):
    tier_hint, basis = guess_tier(prompt)
    model_id = safe_id(host_model)
    if host == "claude" and not model_id:  # no usable payload model: guess from the transcript
        model_id = safe_id(detect_model(transcript_path))
    fam, cls = model_class(model_id)
    current = (f"{model_id} ({fam}, T{cls}-class)" if fam else model_id if model_id
               else "unknown — use the model id from your own system prompt")
    actions = {t: prefs.action_for(t, eff) for t in prefs.TIERS}
    action_line = " ".join(f"{t}={a}" for t, a in actions.items())
    used = sorted(set(actions.values()), key=["switch", "ask", "stay"].index)
    table = RULES_CLAUDE if host == "claude" else RULES_OTHER
    rules = "\n".join(table[a].replace("{prefs}", str(PREFS)).replace("{outcomes}", str(SCRIPTS / "outcomes.py"))
                      for a in used)
    if host == "claude":
        picks, learned = learned_bumps({"T1": "haiku", "T2": "sonnet", "T3": "opus", "T4": TIER_MODEL["T4"]},
                                       keep=lambda m: model_class(m)[0] is not None)
        fit = ", ".join(f"{t}→{m}" for t, m in picks.items())
        settings = "/modelscout:prefs, or the user types"
        own = ("You cannot switch your own session model; for repeated work of one tier "
               "you may add \"tip: pick <Model> in the model menu\".")
    else:
        picks = provider_picks(host, host_model)
        own_prov = {"codex": "openai", "gemini": "gemini"}.get(host)  # Hermes can route to any provider
        adj, learned = learned_bumps(picks or {}, exact=True,
                                     keep=(lambda m: model_provider(m) == own_prov) if own_prov else None)
        picks = adj if picks else None
        fit = (", ".join(f"{t}→{m}" for t, m in sorted(picks.items())) + " (price-band picks; "
               "prefer models the user actually has)") if picks else \
            "the cheapest model the user has whose price band fits the tier"
        if host == "hermes":
            fit = ("the delegate_task model route (`option`) whose description fits the tier, "
                   "if routes are offered; else " + fit)
        settings = "the user types"
        own = ""
    selfcontained = ("" if host == "claude" else
                     "\nThis block is self-contained: don't load the modelscout skill, read config "
                     "files or run scripts just to show the card or pick a route.")
    final_card = ("" if host == "claude" else
                  "\n   If you call tools before writing any text, put the card at the very top "
                  "of your final reply instead, so the user always sees it.")
    learned_line = f"\n   Learned: {'; '.join(learned)}." if learned else ""
    receipt = ("If the model FITS, show one quote line: > `🔭 ModelScout` **<Tier> <tier name>** · `<Model>` fits — doing it here"
               if eff["receipts"] == "always" else
               "If the model FITS, show nothing — just do the work.")
    return f"""<modelscout host="{host}" mode="{eff['mode']}" tier-hint="{tier_hint}" hint-basis="{basis}" current-model="{current}" on-mismatch="{action_line}">
ModelScout is ACTIVE (mandatory). Applies only if this prompt starts a NEW
substantial task — skip for follow-ups ("yes", "continue"), quick questions and
chit-chat. tier-hint is a keyword guess (reclassify it) and current-model is a
guess: the model id in your own system prompt always wins.
1. Tier the task: T1 mechanical, T2 standard, T3 hard reasoning, T4 frontier.
   Best fit: {fit}.{learned_line}
2. Show this card FIRST, in the user's language, as a Markdown quote block
   (keep the backticks and bold exactly; they make it stand out), max 3 lines:
   > `🔭 ModelScout` **<Tier> <tier name>** · <the task in 5–8 words>
   > Best fit: `<Model>` — <why, one clause> · <quota/cost vs current, e.g. "~1/5 of Opus">
   > → ⚡ <what happens next>
   {receipt}{final_card}
3. On a mismatch, act per on-mismatch for the tier you chose:
{rules}
{own}
Settings: {settings} "modelscout: auto|ask|inform|off|savings|refresh|T1 stay".{selfcontained}
</modelscout>"""


def detect_host(data, argv):
    for a in argv:
        if a.startswith("--host="):
            return a.split("=", 1)[1]
    if data.get("hook_event_name") == "BeforeAgent":
        return "gemini"
    if data.get("hook_event_name") == "pre_llm_call":
        return "hermes"
    return "claude"


def emit_context(event, text):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}},
                     ensure_ascii=False))


def payload_model(data):
    m = data.get("model")
    m = m.get("id") if isinstance(m, dict) else m
    return m if isinstance(m, str) and m.strip() else None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(data, dict):
        return
    host = detect_host(data, sys.argv[1:])
    event = data.get("hook_event_name") or ("BeforeAgent" if host == "gemini" else "UserPromptSubmit")
    extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}
    prompt = data.get("prompt") if host != "hermes" else extra.get("user_message")
    if not isinstance(prompt, str):
        return
    prompt = prompt.strip()

    cmd = parse_command(prompt)
    if cmd is not None:
        result = handle_command(cmd, host)
        if host == "gemini":
            emit_context(event, "Relay this to the user verbatim and do nothing else:\n" + result)
        else:
            print(json.dumps({"decision": "block", "reason": result}, ensure_ascii=False))
        return

    eff = prefs.effective()
    if eff["mode"] == "off" or is_trivial(prompt):
        return
    hm = extra.get("model") if host != "claude" else payload_model(data)
    block = build_block(prompt, data.get("transcript_path"), eff, host, hm)
    if host == "hermes":
        print(json.dumps({"context": block}, ensure_ascii=False))
    else:
        emit_context(event, block)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
