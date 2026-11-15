# Spec Delta

## ADDED Requirements

### Requirement: Replacing a variant's reference
`slopoly variant reference <pack>/<asset>:<variant> <hero>` SHALL make a hero of the asset the variant's reference,
keeping its manifest, program and builds. The old reference SHALL be rejected as when a pick replaces it. A hero pick
started with `--for <variant>` SHALL suggest that variant's name for the picked hero, so confirming replaces its
reference rather than creating a new variant.

#### Scenario: Revise then replace
- **WHEN** the default locomotive has reference hero 3 and builds 1 to 9, and the agent runs `slopoly gen revise`
  on hero 3, then `slopoly pick orcish/locomotive --heroes --for default`, and the user picks hero 6
- **THEN** hero 6 becomes the default variant's reference, builds 1 to 9 and the program stay, hero 3 is rejected,
  and no new variant is created

#### Scenario: Command
- **WHEN** the agent runs `slopoly variant reference orcish/locomotive:default heroes/hero_006.png`
- **THEN** hero 6 becomes the default variant's reference, and the variant keeps its program and builds
