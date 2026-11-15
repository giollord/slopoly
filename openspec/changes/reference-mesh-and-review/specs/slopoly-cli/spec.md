# Spec Delta

## MODIFIED Requirements

### Requirement: Target addressing
Commands SHALL address content as `<pack>`, `<pack>/<asset>`, `<pack>/<asset>:<variant>` or `<pack>/scenes/<scene>`,
and images by workspace-relative path. A target without a variant SHALL mean the asset's default variant. When a
command gets a target split over several arguments, its error SHALL suggest the joined target.

#### Scenario: Default variant
- **WHEN** the agent runs `slopoly build gnome-village/cart`
- **THEN** the cart's default variant is built

#### Scenario: Unknown target
- **WHEN** a command names an asset that does not exist in the pack
- **THEN** it fails with code `not_found`, naming the pack and listing its assets

#### Scenario: Variant as a separate argument
- **WHEN** the agent runs `slopoly variant default orcish/locomotive variant_2`
- **THEN** the command fails with a JSON error whose hint suggests `slopoly variant default orcish/locomotive:variant_2`
