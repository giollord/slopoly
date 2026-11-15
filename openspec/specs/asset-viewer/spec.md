# asset-viewer Specification

## Purpose
The 3D viewer that shows asset builds and scene models in the studio. It covers the camera, diagnostic overlays
(wireframe, grid, axes, normals) and the palette variant preview.

## Requirements

### Requirement: Orbit viewer for builds and scenes
The view window SHALL show builds and scenes in the same 3D viewer. The user SHALL be able to orbit, pan and zoom, and
to reset the camera so the whole model is framed. The model SHALL be lit so that its exported normals and baked vertex
shade are visible.

#### Scenario: Frame the cart
- **WHEN** the user opens the cart in the view window, zooms in, and clicks reset view
- **THEN** the camera frames the whole cart again

#### Scenario: Scene uses the same viewer
- **WHEN** the user opens a built scene in the view window
- **THEN** its model is shown in the same viewer, with the same controls and overlays as for a build

### Requirement: Wireframe overlay
The viewer SHALL offer a wireframe toggle that draws every triangle edge of the model over its shaded surface.

#### Scenario: See the triangles
- **WHEN** the user turns on wireframe for the cart
- **THEN** every triangle edge of the cart is drawn over the shaded model, and turning it off removes the lines

### Requirement: Grid and origin axes
The viewer SHALL offer a ground grid on the y = 0 plane with 1-metre cells, and an axes overlay at the origin: x red,
y green, z blue. Both SHALL be toggled separately.

#### Scenario: Check grounding
- **WHEN** the user turns on the grid and the axes for a cart build
- **THEN** a 1-metre grid is drawn at y = 0 and coloured axes meet at the origin, so the user can see whether the cart
  stands on the ground and where its pivot is

### Requirement: Normals overlay
The viewer SHALL offer a normals toggle that draws each vertex normal of the exported model as a short line. The line
length SHALL scale with the model size.

#### Scenario: Spot an inverted face
- **WHEN** a build has a face whose normals point into the model and the user turns on normals
- **THEN** that face's normal lines point inward while the lines of the faces around it point outward

#### Scenario: Smooth versus flat
- **WHEN** the user turns on normals for a smooth-shaded wheel and for a flat-shaded box
- **THEN** the wheel's rim vertices show one shared normal each, and the box corners show one normal per face

### Requirement: Overlay choices persist per viewer
The viewer SHALL remember the user's overlay choices in the user's settings and apply them again when another model
loads or a view window is reopened.

#### Scenario: Switch builds with wireframe on
- **WHEN** the user turns on wireframe, closes the window and opens an older build
- **THEN** the older build loads with wireframe still on

### Requirement: Palette variant preview
The view window SHALL let the user show a build with the main palette or any rendered palette variant, without
reloading the model. Palette cells SHALL stay crisp (nearest sampling).

#### Scenario: Preview a variant
- **WHEN** the user picks the "autumn" variant in the palette choice
- **THEN** the model shows the autumn colours with the same shading, and clearing the choice shows the main palette
