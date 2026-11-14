#!/bin/sh
# Development only: compiles each UI-format source/<name>.json (edited with the `comfy` CLI) into the API-format
# workflows/<name>.json that the comfy worker runs. Needs the container's ComfyUI (default http://127.0.0.1:8288).
# The CLI fills unconnected optional link inputs with their schema default (e.g. SAM3_Detect's `bboxes` box), which
# changes their meaning; such object-valued inputs are dropped so they stay unconnected, as in the UI.
set -e
cd "$(dirname "$0")"
export COMFY_LOCAL_URL="${COMFY_LOCAL_URL:-http://127.0.0.1:8288}"
for source in source/*.json; do
    name=$(basename "$source")
    comfy --json run --workflow "$source" --print-prompt --where local | python -c "
import json, sys
envelope = json.load(sys.stdin)
assert envelope['ok'], envelope['error']
prompt = envelope['data']['prompt']
for node in prompt.values():
    node['inputs'] = {k: v for k, v in node['inputs'].items() if not isinstance(v, dict)}
json.dump(prompt, sys.stdout, indent=1)
" > "workflows/$name"
    echo "workflows/$name"
done
