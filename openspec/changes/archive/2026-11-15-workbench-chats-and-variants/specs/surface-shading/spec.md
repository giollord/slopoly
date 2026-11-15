## ADDED Requirements

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
part, what it could not fix: open edges, faces that still point inward, and faces bent more than 5 degrees out of
plane, which show a crease in flat shading. The agent and the asset page SHALL see these counts. A build with
unfixed defects SHALL still be built and exported.

#### Scenario: Open plane reported
- **WHEN** a part is a single open plane, such as a leaf
- **THEN** the report lists that part's open edges, so the agent can give it thickness

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
