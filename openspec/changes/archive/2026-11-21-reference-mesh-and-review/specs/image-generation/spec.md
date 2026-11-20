# Spec Delta

## MODIFIED Requirements

### Requirement: Image model chosen by comparison
The default model for style anchors and heroes SHALL be chosen by a recorded comparison of the candidate local models on the same prompts and references. The comparison covers style match, object correctness, element placement and time per image. A candidate SHALL be an open-weights model released in 2026 or later, in common use, whose licence allows commercial use of its outputs. When the default model's licence limits that use (a revenue limit, required content filtering), the limits SHALL be named in the setup documentation and by `slopoly doctor`, and a fallback model whose licence has no such limits SHALL be selectable with the `images.model` setting.

#### Scenario: Recorded choice
- **WHEN** the comparison is complete
- **THEN** the chosen model, the rejected candidates and the reasons are recorded in the change notes, and the workflow files use the chosen model

#### Scenario: Default with licence limits
- **WHEN** the user runs `slopoly doctor` with the default image model, Krea 2 Turbo
- **THEN** the result names Krea 2's licence limits and the setting that selects the fallback

#### Scenario: Fallback model
- **WHEN** the user sets `images.model` to `z-image-turbo` and runs an anchor or hero job
- **THEN** the job runs on Z-Image Turbo from the style text and prompt alone, records no references, and `slopoly
  doctor` checks and fetches only that model's files for anchors and heroes

### Requirement: Part segmentation
The system SHALL produce, for the view images of a hero and a list of part names, one mask per found part per view, with the mask's bounding box and area. The whole-object mask of each view SHALL come from the view's render silhouette. Parts that are not found SHALL be reported as missing rather than failing the job.

#### Scenario: Cart parts
- **WHEN** segmentation runs on the cart hero's views with parts "wheel, axle, handle, bed"
- **THEN** masks with bounding boxes are stored for each found part and view, and any part not found is listed as missing

#### Scenario: Implausible mask
- **WHEN** a part's mask covers more than half of the object, or several parts get the same box in one view
- **THEN** those masks are kept but flagged `implausible` in the result, with the reason

### Requirement: Style-referenced hero image
The system SHALL generate hero images of one asset: a single three-quarter front view of the whole object, alone on a plain light background, using up to three of the pack's picked style anchors as style references (none with an image model that takes no references). The hero prompt SHALL ask for the whole object in frame and for no smoke, steam, fire, sparks, dust or other particles. A job SHALL produce the requested number of images (1 to 4), each with its seed recorded.

#### Scenario: Cart heroes
- **WHEN** a hero job runs for the asset "wooden cart" with count 2
- **THEN** two hero images of the cart are stored on the asset, undecided, each with its seed

#### Scenario: No picked anchor
- **WHEN** a hero job is requested for an asset of a pack without a picked style anchor
- **THEN** the request is refused with an error asking to pick a style anchor first

#### Scenario: Steam locomotive without smoke
- **WHEN** a hero job runs for a steam locomotive
- **THEN** the prompt sent to the workflow excludes smoke and particles, so the hero shows the locomotive only

## ADDED Requirements

### Requirement: Implausible 3D regions
A part's 3D region that spans most of the object along two or more axes SHALL be flagged implausible, and `look
--region` SHALL refuse it with that reason.

#### Scenario: Rib over the whole locomotive
- **WHEN** the votes give `rib` a region spanning the whole locomotive
- **THEN** the region is flagged implausible, and `look --region rib` fails with a hint to use `--box`

### Requirement: Segmentation within a region
A part MAY be segmented within a box given in a view's pixels or in metres. The system SHALL then run the detector on
that region cropped and enlarged, and map the mask back to the full view. Results SHALL say which parts were
segmented within a region.

#### Scenario: Small spikes
- **WHEN** the agent segments `spike` within the box of the locomotive's roof in the side view
- **THEN** the spike masks are found on the enlarged crop and returned in the full view's pixels, marked as segmented
  within that box

### Requirement: Part regions on the reference mesh
When the hero has a reference mesh, segmentation SHALL also render the mesh from several more directions, segment each
part there, and vote the masks onto the mesh's faces. Each found part SHALL get a 3D region with its bounds in metres
and the share of renders that agree. A part with too little agreement SHALL be reported as uncertain.

#### Scenario: Cowcatcher region
- **WHEN** segmentation runs with the part `cowcatcher` on a hero with a reference mesh
- **THEN** the result gives the cowcatcher's region on the mesh with its bounds in metres and its agreement, and `look
  --region cowcatcher` can use it
