# surface-palette Specification

## Purpose
Colours a pack's low-poly assets through one shared palette texture. The palette's role-named entries can be recoloured freely, and palette variants restyle every asset of the pack without touching geometry.

## Requirements

### Requirement: Main palette per pack
Each pack SHALL have exactly one main palette. Its entries are solid colours or two-colour gradients, and each SHALL have a unique role name within the pack.

#### Scenario: Add a gradient entry
- **WHEN** an entry "roof" is added as a gradient from dark red to orange
- **THEN** the main palette lists "roof" as a gradient with both colours

#### Scenario: Duplicate role
- **WHEN** an entry is added with a role name that already exists in the pack
- **THEN** it is rejected

### Requirement: Role names describe usage by default
Entry names SHALL describe where a colour is used (for example "wall base", "wall accent", "leaf 1"). A colour name (for example "leaf green") is allowed only when that colour is meant to stay the same in every palette. The agent SHALL follow this rule, and the UI SHALL show it as guidance when entries are created.

#### Scenario: Agent names measured colours
- **WHEN** the agent creates entries from the cart's measured colours
- **THEN** the entries are named by use, such as "cart wood", "cart wood dark" and "cart metal", not "brown" or "grey"

#### Scenario: Intrinsic colour
- **WHEN** a colour must be the same regardless of palette, such as the green of leaves
- **THEN** the agent may name the entry by its colour, such as "leaf green"

### Requirement: Stable texture slots
Each entry SHALL occupy a fixed slot in the palette texture: a solid cell or a gradient strip. Adding, editing or recolouring entries SHALL NOT move existing entries' slots. An entry used by any build SHALL NOT be deletable.

#### Scenario: Add entry keeps layout
- **WHEN** a new entry is added to a palette whose entries are already used by builds
- **THEN** the existing builds' UVs still point at the same colours

#### Scenario: Delete used entry
- **WHEN** the user tries to delete an entry tagged on a built asset
- **THEN** deletion is refused with the list of assets that use it

### Requirement: Recolour without rebuilding
Changing an entry's colours SHALL re-render the palette texture and refresh the pack's current exported models with the new texture, without re-running part programs.

#### Scenario: Change wall base
- **WHEN** the user changes "wall base" from beige to red
- **THEN** the palette texture and the pack's current models show red walls after the refresh, and no build job runs

### Requirement: Colour measurement from masks
The system SHALL measure, for each part mask of a picked turnaround, its main colours with their coverage share. The agent SHALL receive these as numbers.

#### Scenario: Cart colours
- **WHEN** colours are measured for the cart's masks
- **THEN** each part lists up to a few colours as hex values with coverage fractions, without image data

### Requirement: Material tags and UVs
Parts and face groups in a part program SHALL be taggable with a main-palette role. A gradient tag SHALL name the axis along which the gradient runs. Builds SHALL assign UVs so that each face takes its role's solid colour or its position along the gradient, and SHALL export one shared material with the palette texture.

#### Scenario: Solid and gradient faces
- **WHEN** the cart bed is tagged "cart wood" and a roof is tagged "roof" with gradient along Y
- **THEN** the exported bed faces sample only the "cart wood" cell and the roof's lower vertices sample the gradient's start and upper vertices its end

#### Scenario: Unknown role
- **WHEN** a program tags a part with a role not in the main palette
- **THEN** the build fails naming the unknown role

### Requirement: Palette variants
A pack SHALL support named palette variants. Each variant has the same roles and slots as the main palette, with its own colours, and SHALL render its own texture with the identical layout. Variants SHALL be creatable by hand or by the agent on request.

#### Scenario: Agent generates a variant
- **WHEN** the user asks for an "autumn" variant
- **THEN** a variant "autumn" is created with a colour for every main-palette role and its texture is rendered

#### Scenario: New role added
- **WHEN** a role is added to the main palette
- **THEN** every variant gets that role with the main palette's colour until it is changed

### Requirement: Variants never drive generation
Image generation, colour measurement, silhouette and colour scoring, and the agent's modelling work SHALL use only the main palette. Variants SHALL affect only previews and exports.

#### Scenario: Building with a variant selected in the UI
- **WHEN** the user previews the "autumn" variant and the agent submits a new program
- **THEN** the build is coloured and scored with the main palette

### Requirement: Variant preview and export
The UI SHALL let the user switch a model's displayed palette between the main palette and any variant without rebuilding. Exports SHALL embed the main palette texture and include each variant's texture as a separate image file.

#### Scenario: Preview autumn
- **WHEN** the user selects "autumn" in the 3D viewer
- **THEN** the displayed model is recoloured with the autumn texture immediately

### Requirement: Colour likeness check
Each build SHALL report, per part and view, the difference between the part's main-palette colour and the colour measured in its mask.

#### Scenario: Wrong role tagged
- **WHEN** a wheel measured as brown is tagged with a green role
- **THEN** the build report flags the wheel's colour difference as high
