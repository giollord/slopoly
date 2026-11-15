# Spec Delta

## MODIFIED Requirements

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
