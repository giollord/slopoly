# Design

## Context

See proposal.md for the motivation and the session notes it came from. This is the current state the design builds
on:

- **Views.** `gen views` runs the `views` workflow: Idol (TripoSplat) makes a splat and `RenderSplat` renders two
  72-frame orthographic turntables (768 px, fixed zoom). `comfy/views.py` then picks the front frame from silhouette
  symmetry and the hero match, and the side frame as `front + QUARTER_SIGN * quarter`. `QUARTER_SIGN` was calibrated
  on the cart, whose front and back look alike. The locomotive symptoms (side view flipped while the front was right,
  and the reverse at +160°) fit a wrong sign, and don't need a mirrored splat to explain them.
- **Scoring.** `silhouette.py` scales the projected model uniformly to fit the view's silhouette, so a view's scale is
  never in metres. A cropped or smoke-padded silhouette therefore distorts every score.
- **ComfyUI.** The user's ComfyUI has native TRELLIS.2 and Pixal3D nodes, and the gallery template
  `3d_pixal3d_trellis2_image_to_model` wires both behind one switch. It also has `RenderMesh`, `DecimateMesh` and
  `SplatToMesh`.
- **Windows.** Windows are pywebview pages served by `windows/server.py`, with a three.js viewer (`viewer3d.js`). The
  pick window is the model for a window that runs as a job.

## Goals / Non-Goals

**Goals:**

- One 3D reference per hero, in metres, that every later step uses: views, close-ups, segmentation, 3D comparison
  and the review's left pane.
- The user can point at problems directly, and the agent gets notes it can act on and track.
- Fix the session's bugs where they live, not with workarounds in the skill.

**Non-Goals:**

- Using the generated mesh as the asset itself, or retopologising it. It is a reference only. Builds remain part
  programs.
- Texturing the reference. Vertex colours are enough for colour masks and palette measuring.
- Painting or comments inside the passive `view` window. Feedback goes through `review`.
- Multi-image or multi-view input to the mesh generators. That can be a later change.

## Decisions

### 1. Reference mesh workflow derived from the gallery template

The new `reference-mesh` workflow is built with the `comfy` CLI from `3d_pixal3d_trellis2_image_to_model`, stored
under `comfyui/reference/`, and given a recipe like `idol-views.recipe.json`.

```
 in:image -> RemoveBackground(birefnet) -> ImageCropToMask
          -> [in:generator switch] Trellis2Conditioning | Pixal3DConditioning(+MoGe FOV)
          -> structure -> shape -> upsample(in:resolution) -> VaeDecodeShapeTrellis
          -> texture stage -> PaintMesh (vertex colours)
          -> DecimateMesh(in:faces, ~80k) -> MeshToFile3D -> out:mesh (GLB)
 removed: UnwrapMesh, BakeTextureFromVoxel, ApplyTextureToMesh, RenderUVAtlas,
          BakeNormalMap, BakeAmbientOcclusion, PBR previews, Preview3D, notes
```

- Inputs: `image`, `seed`, `generator`, `resolution`, `faces`. Output: `mesh`.
- The texture stage stays only to give vertex colours. If the benchmark shows it costs too much, a flag skips it and
  the views are coloured by sampling the hero instead.
- Alternatives considered:
  - Keeping the Idol splat and fixing only the framing. That leaves no metric scale, no handedness check and no 3D
    regions. Idol stays a benchmark candidate through `SplatToMesh`.
  - Hunyuan3D 2.x. Its licence excludes some territories, so it fails "commercially usable".

### 2. Views rendered in Blender, not in ComfyUI

The CLI downloads the GLB and normalises it in a Blender background run. Normalising means: Y up, scaled to metres,
standing on y = 0, centred, and front towards +Z.

- **Front and handedness.** Render the mesh from the hero's camera direction (three-quarter front-left), and the same
  render mirrored, over a coarse yaw sweep. Score each against the hero's silhouette and colours; the best pair gives
  both the front yaw and whether to mirror. Silhouette mirror symmetry refines the yaw as today. Pixal3D is
  pixel-aligned to the input, so its mesh should come out already oriented; the check still runs.
- **The four views** are orthographic renders of the normalised mesh, flat-lit with vertex colours, framed to the
  bounds plus 5 % margin, at one shared metres-per-pixel. The silhouette masks are exact from the render.
- **Metric scoring.** `silhouette.py` uses the views' known metres-per-pixel instead of fitting the model's scale to
  the silhouette, so size errors become real. The old fit stays as a fallback for views without a scale.
- `comfy/views.py` frame picking and `QUARTER_SIGN` are removed.
- Rationale: Blender is already a host dependency and already renders builds. Rendering the reference with the same
  code and camera conventions as the builds removes a whole class of mismatches. ComfyUI's `RenderMesh` would need
  its own camera conventions.

### 3. Size of the asset

`asset.yaml` gets an optional `size: {axis: z|x|y|longest, metres: 9}`. Without it, the views job estimates the size
from the description and the pack's notes, and marks it `assumed`. The skill tells the agent to state the size when
it creates the asset. Rescaling only reruns the Blender normalisation and the renders.

### 4. `look` close-ups

`slopoly look <target> [--from <dir>|--yaw Y --pitch P] [--region <part>|--box x0,y0,z0,x1,y1,z1] [--zoom F]
[--perspective] [--with-build [n]]` runs in the foreground (a Blender render, a few seconds). It returns the image
paths, the camera and the region's metric bounds. Renders go to the variant's scratch `looks/` folder, which is
git-ignored and capped at the newest 50 images.

### 5. Segmentation

- **Regions:** `--parts "spike@side:0.6,0.0,1.0,0.3"` or `--within <part>`. The CLI crops and enlarges the region
  before uploading it, then pastes the mask back into the view's pixels. No workflow change is needed.
- **Implausible flag:** computed in Python after the workflow runs (area > 50 % of the object, or a box IoU > 0.9
  with another part's mask).
- **3D voting:** when a mesh exists, render 8 more directions (yaw every 45° at 20° pitch), segment each part on
  them, and project the masks onto mesh faces by face-ID renders from Blender. A face belongs to the part chosen by
  most renders where the face is visible. Agreement is that share. Regions are saved as face-index lists next to the
  mesh. This multiplies SAM calls by three, so it runs only for the parts named.

### 6. 3D comparison

Voxelise the build and the normalised reference at a fixed 2 cm cell, or coarser for large objects (target about
128 cells on the longest axis). Report the volume IoU, mean and 90th-percentile surface distance, and connected
components of missing and extra voxels larger than a threshold. Each component gets its bounds and the build parts
within 5 cm. This uses numpy in the build's Blender run. Its components go into the build report next to `detail`,
and the agent reads them the same way.

### 7. Review window

- **Page:** `windows/static/review.html` reuses `viewer3d.js` twice (reference GLB, build GLB) plus an image pane.
  Each pane has a transparent paint canvas on top.
  - Lock copies the build camera onto the reference camera on every change.
  - With the hero image on the left, the build camera is set to yaw -45° and pitch 20°, the hero framing the
    hero prompt asks for.
- **Paint:** the brush is a fixed screen-space width. Strokes are stored as polylines, and a stroke mask is rendered
  from them.
- **Hits:** done in the page with three.js `Raycaster` against the build. Each stroke pixel's weight falls off with
  its distance from the polyline (1 at the centre, 0 at the edge); pixels are sampled on a grid, not all of them.
  - A ray hits only the first surface, which gives the "nearest surface only" rule.
  - Misses count towards `empty`.
  - For the reference mesh, the hit points' bounds give the region in metres. For `empty` strokes on the build, the
    same pixels are cast on the reference instead.
- **Result:** pane screenshots with strokes are posted to the server and saved under the variant's `notes/`. The job
  result holds the notes. The server writes `notes.yaml` (number, build, comment, camera, images, hits, status,
  history).
- `slopoly note <target> <n> <status> --by <build> --reason "..."` updates a note. The next review loads `notes.yaml`
  and shows `addressed` notes as pins. The user can confirm a note (`closed`, kept in history) or reopen it.

### 8. Shape plans

`ManifestPart` gets optional `shape: str`, `steps: list[str]` and `checks: list[str]`. `checks` entries are view names
or `look:<from>`, and `slopoly check` validates them. Whether plans are needed is a rule in the skill, not enforced by
the CLI, because the "complex" threshold is a judgement call.

### 9. Modelling API fixes

- **`join`:** remove duplicate faces (the same vertex set after merging by distance) before building the bmesh. Wrap
  any remaining bmesh `ValueError` as a `ShapeError` naming the shapes.
- **`curve`:** when there are two points and `smooth=False`, subdivide the straight segment into `resolution` spans.
- **`jitter`:** before moving, estimate each vertex's local thickness by casting a ray inward along the negative
  normal, and limit the move to 0.45 × thickness. After moving, run the existing self-intersection check and warn.
- **Contacts:** report the nearest points from a BVH tree query between the two parts.
- **`surface_point(shape, origin, direction)`:** a BVH ray cast that returns `(point, normal)` or raises when the ray
  misses.

### 10. Small CLI fixes

- When typer reports an unexpected extra argument and the command takes a variant target, the hint joins the
  arguments with `:`.
- `slopoly view` returns its address in the result as soon as the server is up.
- `pick --heroes --for <variant>` pre-fills that variant's name for the picked hero.
- `variant reference` reuses the pick code that replaces a reference.

## Risks / Trade-offs

- **[Mesh quality on stylised art]** Thin parts (slats, spikes) may merge or vanish, and the back is a guess.
  → The benchmark measures it. Builds are still checked against the hero-faithful front and side views. The 3D
  comparison lists regions only and doesn't block. The skill tells the agent to trust the front and the hero over the
  mesh's back.
- **[GPU memory and time]** TRELLIS.2 at a resolution of 1536 is heavy.
  → `resolution` is a workflow input, and the benchmark records VRAM and time to set the default. One ComfyUI on the
  GPU at a time, as before.
- **[Licences]** The licences of MoGe 2, Pixal3D and the NAF DINOv3 encoder are not yet checked.
  → A task checks each before it enters `models.yaml`. A candidate that fails is dropped from the template cut.
- **[Ray-cast hits blame neighbours]** → Centre-weighted strokes and a 10 % floor, and the skill tells the agent
  the comment decides.
- **[More SAM calls with 3D voting]** → Only for the named parts, and voting can be turned off.
- **[Metric scoring changes scores]** Old builds' scores aren't comparable with new ones.
  → New views mean new scores anyway. Reports mark which scale was used.

## Migration Plan

1. The version bump marks the break. `slopoly check` reports assets whose views lack a reference mesh, with the hint
   `slopoly gen views <asset>`.
2. Old views keep working with the fit-to-silhouette fallback until they are regenerated. Nothing is deleted
   automatically.
3. If the benchmark keeps Idol as the default, it runs through `SplatToMesh` into the same reference-mesh pipeline, so
   the rest of the change is unaffected.
4. Idol's models and the `views` workflow are removed only after the benchmark picks another default.

## Open Questions

- The exact voxel cell and region threshold for the 3D comparison. They are tuned on the cart and locomotive and
  don't change the report format.
- Whether Pixal3D's pixel alignment makes the handedness sweep unnecessary. The check stays either way, so the answer
  only affects speed.
