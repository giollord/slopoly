"""Development only: compares the reference-mesh generators on the same heroes (task 1.4 of the
reference-mesh-and-review change). For each hero and candidate it runs the workflow on the configured ComfyUI and
records the time, the peak GPU memory (nvidia-smi), the triangle count, and how well the mesh seen from its matched
hero camera agrees with the hero silhouette. It also writes a contact sheet per hero (the hero, then each candidate
from the hero camera and from the side) for judging thin parts by eye.

    uv run python comfyui/benchmark_mesh.py --out <dir> <hero.png> [<hero.png> ...]

Candidates: trellis2 and pixal3d (the shipped reference-mesh workflow) and idol (the shipped idol-mesh workflow: the
Idol splat turned into a mesh with SplatToMesh).
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

from slopoly import meshview as mv
from slopoly import reference as ref
from slopoly.comfy import colors, workflow
from slopoly.comfy.client import ComfyClient


CANDIDATES = {
    "trellis2": lambda: (workflow.load("reference-mesh"), {"trellis2": True, "resolution": 1024}),
    "pixal3d": lambda: (workflow.load("reference-mesh"), {"trellis2": False, "resolution": 1024}),
    "idol": lambda: (workflow.load("idol-mesh"), {}),
}


class PeakMemory(threading.Thread):
    """Polls nvidia-smi for the GPU memory in use; ``peak`` is the highest reading in MiB."""

    def __init__(self):
        super().__init__(daemon=True)
        self.peak, self.running = 0, True

    def run(self):
        while self.running:
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                     capture_output=True, text=True, timeout=5).stdout
                self.peak = max(self.peak, max(int(x) for x in out.split()))
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
            time.sleep(0.5)


def run_candidate(client: ComfyClient, name: str, hero: Path, seed: int) -> dict:
    prompt, values = CANDIDATES[name]()
    image = client.upload(hero.read_bytes(), f"bench_{hero.parent.parent.name}_{hero.name}")
    filled = workflow.fill(prompt, {"image": image, "seed": seed, **values})
    client.http.post("/free", json={"unload_models": True, "free_memory": True})  # each run starts cold
    time.sleep(2)
    memory = PeakMemory()
    memory.start()
    start = time.time()
    try:
        outputs = client.run(filled)
    finally:
        memory.running = False
    seconds = time.time() - start
    named = workflow.outputs(filled)
    files = {named[k]: [client.image(i) for i in o.get("3d", []) + o.get("images", [])]
             for k, o in outputs.items() if k in named}
    return {"seconds": round(seconds, 1), "peak_mib": memory.peak, "mesh": files["mesh"][0],
            "hero_mask": files["hero_mask"][0]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("heroes", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidates", default=",".join(CANDIDATES))
    parser.add_argument("--url", default="http://127.0.0.1:8188")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    client = ComfyClient(args.url, timeout=3600)
    rows = []
    for hero in args.heroes:
        label = f"{hero.parent.parent.name}_{hero.stem}"
        hero_rgb = np.asarray(Image.open(hero).convert("RGB"))
        tiles = [np.asarray(Image.fromarray(hero_rgb).resize((256, 256)))]
        for name in args.candidates.split(","):
            try:
                result = run_candidate(client, name, hero, seed=7)
            except Exception as error:  # a candidate that fails (out of memory...) is a result too
                rows.append({"hero": label, "candidate": name, "error": str(error)[:300]})
                print(json.dumps(rows[-1]), flush=True)
                continue
            (args.out / f"{label}_{name}.glb").write_bytes(result["mesh"])
            mesh = mv.load_glb(result["mesh"])
            hero_mask = colors.mask_array(Image.open(io.BytesIO(result["hero_mask"])))
            found = ref.orient(mesh, hero_rgb, hero_mask)
            placed = mesh.transformed(ref.Placement(yaw=found["yaw"], mirrored=found["mirrored"]).matrix())
            for yaw, pitch in (mv.NAMED["hero"], mv.NAMED["side"]):
                rgb, _ = mv.render(placed, mv.framed(placed.verts, yaw, pitch, (256, 256)))
                tiles.append(rgb)
            rows.append({"hero": label, "candidate": name, "seconds": result["seconds"],
                         "peak_mib": result["peak_mib"], "triangles": int(len(mesh.tris)),
                         "hero_iou": found["hero_iou"], "front": found["how"], "mirrored": found["mirrored"],
                         "symmetry": found["symmetry"]})
            print(json.dumps(rows[-1]), flush=True)
        Image.fromarray(np.concatenate(tiles, 1)).save(args.out / f"{label}_sheet.png")
    (args.out / "results.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
