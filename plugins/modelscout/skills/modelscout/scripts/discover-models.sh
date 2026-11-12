#!/usr/bin/env bash
# ModelScout — discover-models.sh
# Builds ~/.claude/model-inventory.json: the AI models this machine actually has
# API access to (Anthropic / OpenAI / Gemini / OpenRouter), enriched with pricing,
# limits, and capabilities from the models.dev open catalog.
#
# Usage: bash discover-models.sh [--refresh-catalog]
set -uo pipefail

CLAUDE_DIR="${HOME}/.claude"
CATALOG="${CLAUDE_DIR}/model-catalog.json"
INVENTORY="${CLAUDE_DIR}/model-inventory.json"
umask 077  # temp files (header files holding keys) are owner-only
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$CLAUDE_DIR"

# --- 1. models.dev catalog (pricing, limits, capabilities). Cached 7 days. ---
if [ "${1:-}" = "--refresh-catalog" ] || [ ! -s "$CATALOG" ] || [ -n "$(find "$CATALOG" -mtime +7 2>/dev/null)" ]; then
  echo "Fetching models.dev catalog..." >&2
  # catalog.py validates the JSON and writes atomically; its stdout goes to stderr to keep ours clean.
  python3 "$(dirname "$0")/catalog.py" refresh >&2 \
    || echo "warn: models.dev refresh failed; continuing with the cached or absent catalog" >&2
fi

# Write a secret header to a file with the printf builtin (never appears in the process
# list), so curl can read it via -H @file instead of a visible command-line argument.
hdr() { printf '%s: %s\n' "$2" "$3" > "${TMP}/$1.hdr"; }

# --- 2. live model lists from each provider that has a key configured ---
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  hdr anthropic x-api-key "$ANTHROPIC_API_KEY"
  curl -fsS --max-time 30 "https://api.anthropic.com/v1/models?limit=1000" \
    -H @"${TMP}/anthropic.hdr" \
    -H "anthropic-version: 2023-06-01" \
    -o "${TMP}/anthropic.json" || echo "warn: anthropic /v1/models failed" >&2
fi

if [ -n "${OPENAI_API_KEY:-}" ]; then
  hdr openai Authorization "Bearer ${OPENAI_API_KEY}"
  curl -fsS --max-time 30 "https://api.openai.com/v1/models" \
    -H @"${TMP}/openai.hdr" \
    -o "${TMP}/openai.json" || echo "warn: openai /v1/models failed" >&2
fi

GEMINI_KEY="${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}"
if [ -n "$GEMINI_KEY" ]; then
  hdr gemini x-goog-api-key "$GEMINI_KEY"
  curl -fsS --max-time 30 "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000" \
    -H @"${TMP}/gemini.hdr" \
    -o "${TMP}/gemini.json" || echo "warn: gemini models list failed" >&2
fi

if [ -n "${OPENROUTER_API_KEY:-}" ]; then
  hdr openrouter Authorization "Bearer ${OPENROUTER_API_KEY}"
  # OpenRouter's list is self-describing: pricing (per token) and context come
  # back inline, so these entries need no models.dev join.
  curl -fsS --max-time 30 "https://openrouter.ai/api/v1/models" \
    -H @"${TMP}/openrouter.hdr" \
    -o "${TMP}/openrouter.json" || echo "warn: openrouter /models failed" >&2
fi

# --- 3. merge into a normalized inventory ---
PROFILE="${CLAUDE_DIR}/modelscout-profile.json"
python3 - "$TMP" "$CATALOG" "$INVENTORY" "$PROFILE" <<'PY'
import json, re, sys, datetime, os

tmp, catalog_path, inventory_path, profile_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

catalog = load(catalog_path) or {}

# models.dev is keyed provider -> {"models": {model_id: {...}}}
CATALOG_PROVIDERS = {
    "anthropic": ["anthropic"],
    "openai": ["openai"],
    "gemini": ["google", "google-vertex"],
}

def enrich(provider, model_id):
    for cp in CATALOG_PROVIDERS.get(provider, []):
        models = (catalog.get(cp) or {}).get("models") or {}
        entry = models.get(model_id)
        if entry:
            return {
                "display_name": entry.get("name"),
                "cost_per_1m": entry.get("cost"),          # {input, output, cache_read, cache_write}
                "limit": entry.get("limit"),               # {context, output}
                "reasoning": entry.get("reasoning"),
                "tool_call": entry.get("tool_call"),
                "structured_output": entry.get("structured_output"),
                "modalities": entry.get("modalities"),
                "release_date": entry.get("release_date"),
                "enriched": True,
            }
    return {"enriched": False}

inventory = {
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "note": "Models the configured API keys can access right now. 'enriched' fields come from models.dev (or the provider's own metadata).",
    "providers": {},
}

# Anthropic — every listed model is a chat model.
anth = load(os.path.join(tmp, "anthropic.json"))
if anth is not None:
    models = []
    for m in anth.get("data", []):
        mid = m.get("id")
        if not mid:
            continue
        models.append({"id": mid, **enrich("anthropic", mid)})
    inventory["providers"]["anthropic"] = {"key_present": True, "models": models}

# OpenAI — filter the list down to chat/completions-capable model families.
oai = load(os.path.join(tmp, "openai.json"))
if oai is not None:
    KEEP = re.compile(r"^(gpt|o\d|chatgpt|codex)")
    DROP = re.compile(r"(embed|whisper|tts|audio|realtime|dall-e|image|moderation|transcribe|search)")
    models = []
    for m in oai.get("data", []):
        mid = m.get("id", "")
        if KEEP.match(mid) and not DROP.search(mid):
            models.append({"id": mid, **enrich("openai", mid)})
    models.sort(key=lambda x: x["id"])
    inventory["providers"]["openai"] = {"key_present": True, "models": models}

# Gemini — keep models that support generateContent.
gem = load(os.path.join(tmp, "gemini.json"))
if gem is not None:
    models = []
    for m in gem.get("models", []):
        if "generateContent" not in (m.get("supportedGenerationMethods") or []):
            continue
        mid = m.get("name", "").removeprefix("models/")
        if not mid:
            continue
        entry = {"id": mid, **enrich("gemini", mid)}
        if not entry.get("display_name"):
            entry["display_name"] = m.get("displayName")
        if not entry.get("limit") and m.get("inputTokenLimit"):
            entry["limit"] = {"context": m.get("inputTokenLimit"), "output": m.get("outputTokenLimit")}
        models.append(entry)
    inventory["providers"]["gemini"] = {"key_present": True, "models": models}

# OpenRouter — self-describing: pricing is USD per token (string); convert to per-1M.
oro = load(os.path.join(tmp, "openrouter.json"))
if oro is not None:
    def per_1m(pricing, key):
        try:
            return round(float(pricing.get(key)) * 1_000_000, 4)
        except (TypeError, ValueError):
            return None
    models = []
    for m in oro.get("data", []):
        mid = m.get("id")
        if not mid:
            continue
        pricing = m.get("pricing") or {}
        arch = m.get("architecture") or {}
        params = m.get("supported_parameters") or []
        models.append({
            "id": mid,
            "display_name": m.get("name"),
            "cost_per_1m": {"input": per_1m(pricing, "prompt"), "output": per_1m(pricing, "completion")},
            "limit": {"context": m.get("context_length")},
            "tool_call": "tools" in params,
            "reasoning": "reasoning" in params,
            "modalities": {"input": arch.get("input_modalities"), "output": arch.get("output_modalities")},
            "enriched": True,
        })
    models.sort(key=lambda x: x["id"])
    inventory["providers"]["openrouter"] = {"key_present": True, "models": models}

# Declared subscriptions (no-API-key users): merge from the profile file.
profile = load(profile_path) or {}
declared = profile.get("declared_subscriptions") or []
if declared:
    inventory["declared_subscriptions"] = declared

with open(inventory_path, "w") as f:
    json.dump(inventory, f, indent=2)

# --- summary ---
print(f"Inventory written to {inventory_path}")
if not inventory["providers"]:
    print("No provider API keys found in the environment "
          "(checked ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY/GOOGLE_API_KEY, OPENROUTER_API_KEY).")
    print("That's fine for subscription users — declare what you have in "
          f"{profile_path}")
    print('  e.g. {"declared_subscriptions": ["claude-max", "chatgpt-plus", "gemini-advanced"]}')
    print("Note: inside Claude Code, Anthropic models are always available via the app's own auth.")
if declared:
    print(f"  declared subscriptions: {', '.join(declared)}")
for name, p in inventory["providers"].items():
    enriched = sum(1 for m in p["models"] if m.get("enriched"))
    print(f"  {name}: {len(p['models'])} models ({enriched} enriched with pricing/capabilities)")
PY
