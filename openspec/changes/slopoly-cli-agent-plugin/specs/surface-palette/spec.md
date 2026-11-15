# Spec Delta

## MODIFIED Requirements

### Requirement: Role names describe usage by default
Entry names SHALL describe where a colour is used (for example "wall base", "wall accent", "leaf 1"). A colour name (for example "leaf green") is allowed only when that colour is meant to stay the same in every palette. The skill SHALL instruct the agent to follow this rule.

#### Scenario: Agent names measured colours
- **WHEN** the agent creates entries from the cart's measured colours
- **THEN** the entries are named by use, such as "cart wood", "cart wood dark" and "cart metal", not "brown" or "grey"

#### Scenario: Intrinsic colour
- **WHEN** a colour must be the same regardless of palette, such as the green of leaves
- **THEN** the agent may name the entry by its colour, such as "leaf green"

### Requirement: Stable texture slots
Each entry SHALL occupy a fixed slot in the palette texture: a solid cell or a gradient strip, assigned by the CLI when
the entry is added. Adding, editing or recolouring entries SHALL NOT move existing entries' slots. An entry used by
any build SHALL NOT be deletable, and `slopoly check` SHALL report hand edits that move or reuse a slot.

#### Scenario: Add entry keeps layout
- **WHEN** a new entry is added to a palette whose entries are already used by builds
- **THEN** the existing builds' UVs still point at the same colours

#### Scenario: Delete used entry
- **WHEN** the agent tries to delete an entry tagged on a built asset
- **THEN** deletion is refused with the list of assets that use it

#### Scenario: Slot moved by hand
- **WHEN** a user edits `palette.yaml` so that two entries share a slot
- **THEN** `slopoly check` reports both entries and the slot

### Requirement: Recolour without rebuilding
Changing an entry's colours SHALL re-render the palette texture and refresh the pack's current builds' models with the
new texture, without re-running part programs.

#### Scenario: Change wall base
- **WHEN** the agent changes "wall base" from beige to red with a palette command
- **THEN** the palette texture and the pack's current models show red walls, and no build is run

### Requirement: Variant preview and export
The view window SHALL let the user switch a model's displayed palette between the main palette and any variant without
rebuilding. Exports SHALL embed the main palette texture and include each variant's texture as a separate image file.

#### Scenario: Preview autumn
- **WHEN** the user selects "autumn" in the view window
- **THEN** the displayed model is recoloured with the autumn texture immediately

### Requirement: Variants never drive generation
Image generation, colour measurement, silhouette and colour scoring, and the agent's modelling work SHALL use only the main palette. Variants SHALL affect only previews and exports.

#### Scenario: Building with a variant selected in the UI
- **WHEN** the user previews the "autumn" variant in a view window and the agent builds a new program
- **THEN** the build is coloured and scored with the main palette
