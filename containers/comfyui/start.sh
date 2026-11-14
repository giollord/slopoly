#!/bin/sh
# ComfyUI in the background (also reachable by the developer's `comfy` CLI on the published port), the worker in front.
set -e
cd "$COMFYUI_DIR"
python main.py --listen 0.0.0.0 --port "$COMFYUI_PORT" --disable-auto-launch $COMFYUI_ARGS &
cd /opt/slopoly
exec python comfy_worker.py
