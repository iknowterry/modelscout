#!/usr/bin/env bash
# ModelScout — SessionStart hook. Announces that ModelScout is active so the
# model (and the user, via the first reply) knows it's watching from prompt one.
set -uo pipefail

profile="${HOME}/.claude/modelscout-profile.json"
mode="suggest"
if [ -s "$profile" ]; then
  mode="$(python3 -c "import json; print(json.load(open('${profile}')).get('mode', 'suggest'))" 2>/dev/null || echo suggest)"
fi
[ "$mode" = "auto" ] || mode="suggest"

inv_note="inventory not built yet — run the modelscout discovery script on first use"
inv="${HOME}/.claude/model-inventory.json"
if [ -s "$inv" ]; then
  inv_note="$(python3 -c "
import json
d = json.load(open('${inv}'))
provs = d.get('providers', {})
n = sum(len(p['models']) for p in provs.values())
if provs:
    print(f\"inventory: {n} models across {len(provs)} provider(s), built {d.get('generated_at', '?')[:10]}\")
else:
    print('no API keys detected — Claude lineup available via app auth; declared subscriptions apply if set')" 2>/dev/null || echo "inventory present")"
fi

cat <<EOF
<modelscout-status>
ModelScout is installed and ACTIVE in this session (mode: ${mode}; ${inv_note}).
In your FIRST reply that involves real work, prepend exactly one line so the
user can see it is running: "🔭 ModelScout active (${mode} mode)". Do not
repeat this announcement afterwards. Per-task behavior follows the
<modelscout-proactive> instruction injected with the first user prompt.
</modelscout-status>
EOF
