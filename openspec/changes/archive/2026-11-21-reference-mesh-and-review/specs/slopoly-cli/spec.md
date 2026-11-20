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

## ADDED Requirements

### Requirement: Workspace written by a newer version
The CLI SHALL record in the workspace the newest version that used it. When a file has fields the running CLI doesn't
know and the workspace was used by a newer version, the error SHALL have code `version_mismatch`, name both versions
and hint to upgrade, instead of asking to fix the fields.

#### Scenario: Old CLI
- **WHEN** a workspace last used by 0.2.1 is read by an older CLI that doesn't know a field of `views.yaml`
- **THEN** the older CLI fails with `version_mismatch` and a hint to install the newer version
