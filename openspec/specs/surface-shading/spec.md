# surface-shading Specification

## Purpose
Controls how a pack's low-poly assets are shaded: flat or smooth normals with hard edges where they belong, and a baked
greyscale vertex shade that adds depth without breaking the shared palette atlas or its variants.

## Requirements

### Requirement: Pack shading mode
Each pack SHALL have a shading mode, flat or smooth, that applies to every build of its assets.
- **Flat:** every edge is hard.
- **Smooth:** normals are shared across edges, and edges whose faces meet at more than the pack's hard-edge angle stay
  hard.

A new pack SHALL start in flat mode with a hard-edge angle of 60 degrees. Changing the mode or the angle SHALL take
effect from the next build of each asset; existing builds are unchanged.

#### Scenario: Smooth wheel, sharp box
- **WHEN** a pack is set to smooth with a 60-degree hard-edge angle and a part program builds an 8-sided wheel and a
  box
- **THEN** the exported wheel shades round across its rim faces, and the box's corners stay hard

#### Scenario: Flat by default
- **WHEN** an asset of a new pack is built
- **THEN** every face of the exported model is shaded flat

### Requirement: Hard and smooth overrides
A part program SHALL be able to mark selected faces' edges as hard or as smooth, overriding the pack's angle rule, and
a part SHALL be able to override the pack's shading mode.

#### Scenario: Forced hard edge
- **WHEN** a smooth pack's program marks the rim edges of a barrel's lid as hard
- **THEN** the lid edge shades hard while the barrel's side stays smooth

#### Scenario: Smooth part in a flat pack
- **WHEN** a flat pack's program declares one part as smooth
- **THEN** that part's model shades smooth and the other parts stay flat

### Requirement: Boundaries are not hard edges
Vertices split only because of differing palette roles or texture coordinates SHALL keep the same normal on both sides.
In smooth mode such a boundary SHALL NOT show as a hard edge.

#### Scenario: Two roles on a smooth surface
- **WHEN** a smooth part has a face group painted with a different palette role in the middle of a curved surface
- **THEN** the colour changes at the boundary but the shading stays continuous across it

### Requirement: Baked vertex shade
Each build SHALL bake a greyscale shade into the model's standard vertex colour. The shade combines ambient occlusion
and a light darkening of exposed edges (wear). Standard glTF viewers and engines multiply it with the palette texture,
so palette variants keep recolouring the model. Each pack SHALL have a shade strength (0 switches the shade off; new
packs start at a moderate default).

#### Scenario: Occlusion inside the bed
- **WHEN** a hollow cart bed is built with the shade on
- **THEN** the inner corners of the bed are darker than its outer faces in the exported model

#### Scenario: Variant with shade
- **WHEN** the user switches a shaded model's palette to a variant in the viewer
- **THEN** the model shows the variant's colours with the same shading

#### Scenario: Shade off
- **WHEN** a pack's shade strength is 0
- **THEN** builds export without darkening, and their colours match the palette exactly

### Requirement: Shading settings in the UI
A pack's shading mode, hard-edge angle and shade strength SHALL be stored in its `pack.yaml`, where the user and the
agent can read and change them. `slopoly check` SHALL reject invalid values.

#### Scenario: Switch a pack to smooth
- **WHEN** the user sets the Gnome village pack's shading mode to smooth in `pack.yaml` and rebuilds the cart
- **THEN** the new build shades smooth, and `slopoly status gnome-village` shows the setting

#### Scenario: Invalid angle
- **WHEN** `pack.yaml` sets a hard-edge angle of 200 degrees
- **THEN** `slopoly check` reports the field and the allowed range

### Requirement: Normals repaired before export
Before export, every build SHALL repair each part's mesh: merge vertices closer than 0.1 mm, remove zero-area faces,
and make every closed piece's face normals point outward. The repair SHALL keep the shading mode, the hard-edge angle
and the program's hard and smooth edge overrides.

#### Scenario: Inward-facing extrusion
- **WHEN** a part program builds a profile extrusion whose faces wind inward
- **THEN** the exported part's normals point outward and it lights like the parts around it

#### Scenario: Hard edges survive the repair
- **WHEN** a smooth pack's barrel with hard lid edges is repaired
- **THEN** the lid edge still shades hard and the side still shades smooth

#### Scenario: Mirrored part
- **WHEN** a part is mirrored across x
- **THEN** both the part and its mirror image show outward normals in the viewer

### Requirement: Area-weighted smooth normals
In smooth mode, each shared vertex normal SHALL be weighted by the area of the faces around it, so that small bevel
and cap faces do not tilt the normals of large faces.

#### Scenario: Bevelled box in a smooth pack
- **WHEN** a smooth pack builds a box with small bevelled edges below the hard-edge angle
- **THEN** each large face shades evenly up to its bevel, without a dark gradient across the face

### Requirement: Shading defects in the build report
The build report SHALL count what the repair fixed: merged vertices, removed faces and flipped faces. It SHALL list, per
part, what it could not fix: open edges, non-manifold edges and vertices (edges shared by three or more faces or by
none, pieces touching at one vertex), faces that cut through other faces of the same mesh, closed pieces that still
point inward, and faces bent more than 5 degrees out of
plane, which show a crease in flat shading. The agent (through the build result) and the view window SHALL show these
counts. A build with unfixed defects SHALL still be built and exported, but open edges, non-manifold geometry,
self-intersection or inward pieces SHALL fail its validation.

#### Scenario: Open plane reported
- **WHEN** a part is a single open plane, such as a leaf
- **THEN** the report lists that part's open edges, so the agent can give it thickness
- **AND** the build is exported but not validated

#### Scenario: Non-manifold edge reported
- **WHEN** a program adds a face on an edge that two faces of a box already share
- **THEN** the report lists that part's non-manifold edges, and the build is exported but not validated

#### Scenario: Twisted quad reported
- **WHEN** a program moves one corner of a flat-shaded box's top face up
- **THEN** the report lists that face as bent out of plane, and the build is still exported

#### Scenario: Clean build
- **WHEN** a build has no defects
- **THEN** the report's shading section shows zero for every unfixed count

### Requirement: Baked shade toggle in the viewer
The viewer SHALL be able to hide the baked vertex shade, so the user can tell lighting problems caused by normals from
those caused by the shade.

#### Scenario: Blotch from the shade
- **WHEN** a dark patch on the cart disappears when the user hides the baked shade
- **THEN** the patch comes from the baked shade, not from the normals
