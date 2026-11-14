## Purpose

Controls how a pack's low-poly assets are shaded: flat or smooth normals with hard edges where they belong, and a baked
greyscale vertex shade that adds depth without breaking the shared palette atlas or its variants.

## ADDED Requirements

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
The user SHALL be able to view and change a pack's shading mode, hard-edge angle and shade strength, and the agent
SHALL be able to read them.

#### Scenario: Switch a pack to smooth
- **WHEN** the user sets the Gnome village pack to smooth on its style tab and rebuilds the cart
- **THEN** the new build shades smooth and the setting is shown on the style tab
