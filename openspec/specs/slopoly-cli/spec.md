# slopoly-cli Specification

## Purpose
The `slopoly` command that agents and users run to scaffold, check, generate, build, export and manage Slopoly
workspace content, with output an agent can parse without viewing images.

## Requirements

### Requirement: Installable command
The CLI SHALL be installable from this repository with `uv tool install`, which provides a `slopoly` command on the
PATH. `slopoly --version` SHALL print the CLI version, which SHALL equal the version of the plugin in the same
repository commit.

#### Scenario: Install from the repository
- **WHEN** a user runs `uv tool install git+<repo-url>` on a machine with uv
- **THEN** `slopoly --version` prints the version stated in the repository's package and plugin manifests

### Requirement: Machine-readable output
Every command SHALL print its result to stdout as one JSON document. Results SHALL refer to images, masks and models
by workspace-relative file paths and SHALL carry numbers (sizes, bounds, scores), never image data.

#### Scenario: Build result
- **WHEN** the agent runs a build
- **THEN** stdout is a JSON document with the build number, validation result, scores and the paths of the model,
  renders and comparison images

### Requirement: Structured errors
A failing command SHALL exit with a non-zero status and print a JSON error with a message, a stable error code and,
where one exists, a hint naming the command or edit that fixes it.

#### Scenario: No anchor picked
- **WHEN** the agent asks for hero images of an asset whose pack has no picked style anchor
- **THEN** the command exits non-zero with code `no_picked_anchor` and a hint to run `slopoly pick` on the pack's
  anchors

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

### Requirement: Scaffolding commands
The CLI SHALL create a workspace, packs, assets, variants and scenes with their starting files, so the agent does
not hand-write their structure. Creating something whose name already exists SHALL fail without changing files.

#### Scenario: New asset
- **WHEN** the agent runs `slopoly asset new gnome-village/cart --description "wooden hand cart"`
- **THEN** the cart's asset file and its default variant's folder and files exist, and the command prints their paths

#### Scenario: Name taken
- **WHEN** the agent creates a pack whose folder already exists
- **THEN** the command fails with code `exists` and changes nothing

### Requirement: Workspace validation
`slopoly check [<target>]` SHALL validate the workspace files against their schemas and cross-references (parents in
manifests, palette roles, picked references, current builds), and SHALL report every problem with file, field and
message. Every command that reads a file SHALL fail with the same report when that file is invalid.

#### Scenario: Hand-edited manifest
- **WHEN** the agent writes a manifest whose part names an unknown parent and runs `slopoly check gnome-village/cart`
- **THEN** the result lists the manifest file, the part and the unknown parent, and exits non-zero

### Requirement: Status overview
`slopoly status [<target>]` SHALL report packs, assets and variants with their statuses, picked references, current
builds and open jobs.

#### Scenario: Resume in a new agent session
- **WHEN** an agent starts a new session in a repository with a workspace and runs `slopoly status`
- **THEN** it learns each asset's status, which variants have a reference hero and a current build, and which jobs
  are still running or waiting for the user

### Requirement: Workspace written by a newer version
The CLI SHALL record in the workspace the newest version that used it. When a file has fields the running CLI doesn't
know and the workspace was used by a newer version, the error SHALL have code `version_mismatch`, name both versions
and hint to upgrade, instead of asking to fix the fields.

#### Scenario: Old CLI
- **WHEN** a workspace last used by 0.2.1 is read by an older CLI that doesn't know a field of `views.yaml`
- **THEN** the older CLI fails with `version_mismatch` and a hint to install the newer version
