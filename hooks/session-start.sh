#!/usr/bin/env bash
# ModelScout — SessionStart hook. Announces that ModelScout is active so the
# user sees it from the first working reply.
dir="$(cd "$(dirname "$0")/.." && pwd)"
mode="$(python3 -c "
import sys; sys.path.insert(0, '${dir}/scripts')
import prefs; print(prefs.effective()['mode'])" 2>/dev/null || echo auto)"
[ "$mode" = "off" ] && exit 0

inv_note="no API keys detected — Claude lineup available via app auth"
inv="${HOME}/.claude/model-inventory.json"
if [ -s "$inv" ]; then
  inv_note="$(python3 -c "
import json
d = json.load(open('${inv}'))
provs = d.get('providers', {})
n = sum(len(p.get('models', [])) for p in provs.values())
print(f'inventory: {n} models across {len(provs)} provider(s)' if provs else 'no API keys detected — Claude lineup available via app auth')" 2>/dev/null || echo "inventory present")"
fi

cat <<MSG
<modelscout-status>
ModelScout is ACTIVE in this session (mode: ${mode}; ${inv_note}).
In your FIRST reply that involves real work, prepend one line:
"🔭 ModelScout active (${mode} mode)". Do not repeat it afterwards. Per-task
behavior follows the <modelscout> block injected with each new task prompt.
MSG
echo "</modelscout-status>"
exit 0
