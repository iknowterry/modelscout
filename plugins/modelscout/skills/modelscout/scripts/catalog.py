#!/usr/bin/env python3
"""ModelScout model catalog: one loader, kept fresh without manual steps.

The catalog is models.dev's public api.json: every provider's models, with
prices, release dates and capabilities. ModelScout reads it from up to two
files and merges them per provider and model, the newer file winning:

- ~/.claude/model-catalog.json. On Claude Code, Codex and Gemini CLI the
  SessionStart hook refreshes it in the background when it is more than
  7 days old: one public GET to models.dev, no keys, no other data sent.
- $HERMES_HOME/models_dev_cache.json (default ~/.hermes). Hermes keeps this
  cache fresh itself; ModelScout only reads it, so on Hermes the plugin makes
  no network calls at all.

Usage:
  catalog.py status     # where the catalog comes from and how old it is
  catalog.py refresh    # fetch models.dev now into ~/.claude/model-catalog.json
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

CLAUDE_CATALOG = Path.home() / ".claude" / "model-catalog.json"
ATTEMPT_STAMP = Path.home() / ".claude" / "modelscout-catalog-attempt"
URL = "https://models.dev/api.json"
MAX_AGE_DAYS = 7
RETRY_HOURS = 6  # after a failed or in-flight refresh, wait this long before trying again

_memo = {"key": None, "data": {}}


def hermes_cache():
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "models_dev_cache.json"


def sources():
    """Catalog files that exist, oldest first."""
    found = []
    for p in (CLAUDE_CATALOG, hermes_cache()):
        try:
            if p.is_file():
                found.append((p.stat().st_mtime, p))
        except OSError:
            pass
    return [p for _, p in sorted(found)]


def _read(path):
    try:
        d = json.loads(Path(path).read_text())
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def load():
    """The merged catalog {provider: {..., "models": {id: {...}}}}. Memoised
    per process until a source file changes (the Hermes plugin is long-lived)."""
    files = sources()
    key = tuple((str(p), p.stat().st_mtime) for p in files)
    if key == _memo["key"]:
        return _memo["data"]
    merged = {}
    for p in files:  # oldest first, so the newest file's entries win
        for prov, v in _read(p).items():
            if not isinstance(v, dict):
                continue
            dst = merged.setdefault(prov, {"models": {}})
            dst.update({k: val for k, val in v.items() if k != "models"})
            models = v.get("models")
            if isinstance(models, dict):
                dst["models"].update(models)
    _memo.update(key=key, data=merged)
    return merged


def age_days():
    """Age in days of the newest catalog file, or None if there is none."""
    files = sources()
    if not files:
        return None
    return (time.time() - files[-1].stat().st_mtime) / 86400


def is_stale():
    age = age_days()
    return age is None or age > MAX_AGE_DAYS


def recently_attempted():
    try:
        return time.time() - ATTEMPT_STAMP.stat().st_mtime < RETRY_HOURS * 3600
    except OSError:
        return False


def needs_refresh():
    return is_stale() and not recently_attempted()


def _fetch(timeout):
    """GET models.dev. Python's own HTTPS first; if that fails (python.org builds
    on macOS ship without root certificates), fall back to curl, which uses the
    system trust store."""
    import urllib.request
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "modelscout-catalog"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        import shutil
        import subprocess
        if not shutil.which("curl"):
            raise
        return subprocess.run(["curl", "-fsS", "--max-time", str(timeout), "-A", "modelscout-catalog", URL],
                              capture_output=True, check=True, timeout=timeout + 5).stdout


def refresh(timeout=30):
    """Fetch models.dev into ~/.claude/model-catalog.json, atomically.
    Returns (ok, message). Never raises."""
    try:
        ATTEMPT_STAMP.parent.mkdir(parents=True, exist_ok=True)
        ATTEMPT_STAMP.touch()
        body = _fetch(timeout)
        data = json.loads(body)
        if not isinstance(data, dict) or len(data) < 10:
            return False, "models.dev returned an unexpected catalog; kept the old one"
        fd, tmp = tempfile.mkstemp(dir=str(CLAUDE_CATALOG.parent), prefix=".model-catalog.")
        with os.fdopen(fd, "wb") as f:
            f.write(body)
        os.replace(tmp, CLAUDE_CATALOG)
        n = sum(len((v or {}).get("models") or {}) for v in data.values() if isinstance(v, dict))
        return True, f"catalog refreshed: {len(data)} providers, {n} models"
    except Exception as e:  # noqa: BLE001 - offline, sandboxed or read-only: keep the old catalog
        return False, f"catalog refresh failed ({e.__class__.__name__}); kept the old one"


def status():
    files = sources()
    age = age_days()
    if not files:
        return "catalog: none yet"
    names = ", ".join(str(p).replace(str(Path.home()), "~") for p in reversed(files))
    when = ("just now" if age * 24 < 1 else f"{age * 24:.0f}h ago" if age < 2 else f"{age:.0f} days ago")
    stale = "" if age <= MAX_AGE_DAYS else " (stale)"
    return f"catalog: updated {when}{stale} · from {names}"


def main(argv):
    cmd = argv[0] if argv else "status"
    if cmd == "refresh":
        ok, msg = refresh()
        print(msg)
        return 0 if ok else 1
    print(status())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
