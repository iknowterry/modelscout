#!/usr/bin/env python3
"""ModelScout preferences — the single writer of ~/.claude/modelscout-profile.json.

Usage:
  prefs.py show
  prefs.py mode auto|ask|inform|off
  prefs.py default T1|T2|T3|T4 switch|stay|ask|clear
  prefs.py receipts always|mismatch-only
  prefs.py reset            # clears mode/receipts/defaults, keeps subscriptions

Precedence: a per-tier default wins; otherwise the mode decides
(auto -> switch, ask -> ask, inform -> stay, off -> silent).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

# MODELSCOUT_STATE_DIR moves settings and outcomes elsewhere (the benchmark uses it
# so its runs never touch your real settings or learning).
STATE_DIR = Path(os.environ.get("MODELSCOUT_STATE_DIR") or Path.home() / ".claude")
PROFILE = STATE_DIR / "modelscout-profile.json"
MODES = ("auto", "ask", "inform", "off")
LEGACY_MODES = {"suggest": "ask"}
ACTIONS = ("switch", "stay", "ask")
TIERS = ("T1", "T2", "T3", "T4")
MODE_ACTION = {"auto": "switch", "ask": "ask", "inform": "stay", "off": "off"}
TIER_NAMES = {"T1": "mechanical", "T2": "standard", "T3": "hard reasoning", "T4": "frontier"}


def load():
    try:
        d = json.loads(PROFILE.read_text())
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(d):
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(PROFILE.parent), prefix=".modelscout-")
    with os.fdopen(fd, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, PROFILE)


def effective(d=None):
    d = load() if d is None else d
    mode = d.get("mode", "auto")
    mode = LEGACY_MODES.get(mode, mode)
    if mode not in MODES:
        mode = "auto"
    receipts = d.get("receipts", "always")
    if receipts not in ("always", "mismatch-only"):
        receipts = "always"
    raw = d.get("defaults") if isinstance(d.get("defaults"), dict) else {}
    defaults = {t: raw[t] for t in TIERS if raw.get(t) in ACTIONS}
    return {"mode": mode, "receipts": receipts, "defaults": defaults}


def action_for(tier, eff=None):
    eff = effective() if eff is None else eff
    if eff["mode"] == "off":
        return "off"
    return eff["defaults"].get(tier) or MODE_ACTION[eff["mode"]]


def describe(eff=None):
    eff = effective() if eff is None else eff
    lines = [f"mode: {eff['mode']}   receipts: {eff['receipts']}"]
    for t in TIERS:
        src = "your default" if t in eff["defaults"] else f"from {eff['mode']} mode"
        lines.append(f"  {t} {TIER_NAMES[t]:<15} -> {action_for(t, eff):<6} ({src})")
    return "\n".join(lines)


def set_mode(mode):
    mode = LEGACY_MODES.get(mode, mode)
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}")
    d = load()
    d["mode"] = mode
    save(d)


def set_default(tier, action):
    tier = tier.upper()
    if tier not in TIERS:
        raise ValueError("tier must be T1, T2, T3 or T4")
    d = load()
    defaults = d.get("defaults") if isinstance(d.get("defaults"), dict) else {}
    if action == "clear":
        defaults.pop(tier, None)
    elif action in ACTIONS:
        defaults[tier] = action
    else:
        raise ValueError("action must be switch, stay, ask or clear")
    d["defaults"] = defaults
    save(d)


def set_receipts(value):
    if value not in ("always", "mismatch-only"):
        raise ValueError("receipts must be always or mismatch-only")
    d = load()
    d["receipts"] = value
    save(d)


def set_catalog_auto_refresh(on):
    """Weekly background refresh of the models.dev catalog (Claude Code, Codex,
    Gemini CLI). Off means ModelScout makes no network calls on its own."""
    d = load()
    if on:
        d.pop("catalog_auto_refresh", None)
    else:
        d["catalog_auto_refresh"] = False
    save(d)


def catalog_auto_refresh(d=None):
    return (d if d is not None else load()).get("catalog_auto_refresh") is not False


def reset():
    d = load()
    for k in ("mode", "receipts", "defaults"):
        d.pop(k, None)
    save(d)


def main(argv):
    try:
        if not argv or argv[0] == "show":
            pass
        elif argv[0] == "mode" and len(argv) == 2:
            set_mode(argv[1])
        elif argv[0] == "default" and len(argv) == 3:
            set_default(argv[1], argv[2])
        elif argv[0] == "receipts" and len(argv) == 2:
            set_receipts(argv[1])
        elif argv[0] == "reset":
            reset()
        else:
            print(__doc__.strip())
            return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(describe())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
