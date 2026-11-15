# Spec Delta

## MODIFIED Requirements

### Requirement: Shading settings in the UI
A pack's shading mode, hard-edge angle and shade strength SHALL be stored in its `pack.yaml`, where the user and the
agent can read and change them. `slopoly check` SHALL reject invalid values.

#### Scenario: Switch a pack to smooth
- **WHEN** the user sets the Gnome village pack's shading mode to smooth in `pack.yaml` and rebuilds the cart
- **THEN** the new build shades smooth, and `slopoly status gnome-village` shows the setting

#### Scenario: Invalid angle
- **WHEN** `pack.yaml` sets a hard-edge angle of 200 degrees
- **THEN** `slopoly check` reports the field and the allowed range

### Requirement: Shading defects in the build report
The build report SHALL count what the repair fixed: merged vertices, removed faces and flipped faces. It SHALL list, per
part, what it could not fix: open edges, faces that still point inward, and faces bent more than 5 degrees out of
plane, which show a crease in flat shading. The agent (through the build result) and the view window SHALL show these
counts. A build with unfixed defects SHALL still be built and exported.

#### Scenario: Open plane reported
- **WHEN** a part is a single open plane, such as a leaf
- **THEN** the report lists that part's open edges, so the agent can give it thickness

#### Scenario: Twisted quad reported
- **WHEN** a program moves one corner of a flat-shaded box's top face up
- **THEN** the report lists that face as bent out of plane, and the build is still exported

#### Scenario: Clean build
- **WHEN** a build has no defects
- **THEN** the report's shading section shows zero for every unfixed count
