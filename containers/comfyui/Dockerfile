# ComfyUI (headless) + the Slopoly comfy worker. Build context: repo root.
# Models are not in the image: the host's <models-dir> is bind-mounted at /opt/ComfyUI/models.
# Workflows are bind-mounted from comfyui/workflows at /opt/slopoly/workflows (edit without rebuilding).
FROM pytorch/pytorch:2.14.1-cuda13.2-cudnn9-runtime

ARG COMFY_CLI_VERSION=1.26.0
ARG COMFYUI_VERSION=0.45.3

ENV DO_NOT_TRACK=1 COMFY_NO_TELEMETRY=1 PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgl1 libglib2.0-0 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# This image is the environment: install into the system Python and keep the base image's PyTorch.
RUN rm -f "$(python -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')/EXTERNALLY-MANAGED" \
    && python -c "from importlib.metadata import version as v; print(f'torch=={v(\"torch\")}\ntorchvision=={v(\"torchvision\")}')" > /opt/torch-constraints.txt
ENV PIP_CONSTRAINT=/opt/torch-constraints.txt

RUN pip install --no-cache-dir "comfy-cli==${COMFY_CLI_VERSION}" \
    && comfy --skip-prompt --workspace /opt/ComfyUI install --version "${COMFYUI_VERSION}" \
        --nvidia --skip-torch-or-directml --skip-manager \
    && test -f /opt/ComfyUI/main.py \
    && rm -rf /root/.cache/pip

COPY workers/pyproject.toml /opt/slopoly/worker/pyproject.toml
COPY workers/slopoly_worker /opt/slopoly/worker/slopoly_worker
# The base image's `spin` (an unused dev tool) pins an old click; drop it so `pip check` passes.
RUN pip install --no-cache-dir /opt/slopoly/worker "websockets>=14" "numpy>=1.26" "pillow>=10" \
    && (pip uninstall -y spin || true) \
    && pip check

COPY containers/comfyui/*.py containers/comfyui/start.sh /opt/slopoly/
RUN chmod +x /opt/slopoly/start.sh

ENV COMFYUI_DIR=/opt/ComfyUI SLOPOLY_WORKFLOWS=/opt/slopoly/workflows COMFYUI_PORT=8188 COMFYUI_ARGS="--reserve-vram 3"
WORKDIR /opt/slopoly
EXPOSE 8188
CMD ["/opt/slopoly/start.sh"]
