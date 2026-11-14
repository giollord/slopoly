# Geometry worker: Blender as a Python module (bpy) + slopoly_model + manifold3d. CPU only. Build context: repo root.
FROM python:3.13-slim

# Shared libraries the bpy wheel loads even headless.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libgl1 libegl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "bpy==5.3.0" "manifold3d>=3.5,<4" "numpy>=2" "pillow>=11" "scikit-image>=0.25" \
        "pytest>=9.2" "pytest-asyncio>=1.5" "respx>=0.23"

COPY workers/pyproject.toml /opt/slopoly/worker/pyproject.toml
COPY workers/slopoly_worker /opt/slopoly/worker/slopoly_worker
RUN pip install --no-cache-dir /opt/slopoly/worker && pip check

COPY geometry /opt/slopoly/geometry
COPY containers/geometry/geometry_worker.py /opt/slopoly/
ENV PYTHONPATH=/opt/slopoly/geometry:/opt/slopoly PYTHONUNBUFFERED=1
WORKDIR /opt/slopoly
CMD ["python", "geometry_worker.py"]
