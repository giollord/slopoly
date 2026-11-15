# local-runtime Specification

## Purpose
Lets one developer start the whole Slopoly stack locally with one command, while keeping machine-specific paths and secrets out of the public repository.

## Requirements

### Requirement: Configurable models folder
The ComfyUI models folder SHALL be a machine setting chosen by the user. Slopoly SHALL only write into it when the
user runs `slopoly doctor --fetch`, and SHALL never delete files from it.

#### Scenario: Shared models folder
- **GIVEN** the models-folder setting points to an existing host folder `<models-dir>` used by the user's ComfyUI
- **WHEN** a model file is downloaded through `slopoly doctor --fetch`
- **THEN** the file appears under `<models-dir>` and the user's ComfyUI can load it

### Requirement: No machine-specific values in the repository
Host paths, URLs and secrets SHALL be supplied only through the user's configuration directory or environment
variables. Committed files in this repository, and files Slopoly writes to a workspace, SHALL show placeholders only.

#### Scenario: Missing setting
- **WHEN** a required setting such as the ComfyUI URL or the Blender path is not configured and cannot be found
- **THEN** the command that needs it fails with the setting's name and the command that sets it, and nothing is written
  into the workspace

#### Scenario: Repository check
- **WHEN** the repository contents are inspected
- **THEN** no absolute host path to the developer's models, Blender or workspace and no token appear in tracked files,
  including specs and docs

### Requirement: Host tools instead of a service stack
Slopoly SHALL run as the `slopoly` CLI on the host, using uv for its own Python environment, the user's Blender for
builds and a ComfyUI reachable over HTTP for generation. It SHALL NOT need Docker, .NET, Aspire, a message broker or a
database server.

#### Scenario: Clean host
- **GIVEN** a host with uv, Blender and a running ComfyUI with the required nodes and models, and no Docker or .NET
- **WHEN** the user installs the CLI and runs the cart scenario through their agent
- **THEN** the scenario completes

### Requirement: Environment check
`slopoly doctor` SHALL report, as pass or fail with a fix for each: whether ComfyUI is reachable, which nodes used by
the shipped workflows it lacks, which required models it lacks, whether Blender is found and its version is supported,
and whether the libraries the build needs are installed for that Blender.

#### Scenario: Missing node
- **WHEN** the user's ComfyUI lacks a node class that the views workflow uses
- **THEN** doctor fails that check, names the node class and the workflow, and says how to install it

#### Scenario: Blender not found
- **WHEN** no Blender is configured or found in the usual install locations
- **THEN** doctor fails the Blender check with the download page and the command that sets the Blender path

### Requirement: Model download
When the ComfyUI models folder is known, `slopoly doctor --fetch` SHALL download each missing required model from its
listed source into the right subfolder, resuming partial downloads, and print what it fetched. When the folder is not
known, doctor SHALL list each missing model with its subfolder and URL and the command that sets the folder.

#### Scenario: Fetch into a known folder
- **GIVEN** the models folder is configured and `sam3.1_multiplex_fp16.safetensors` is missing
- **WHEN** the user runs `slopoly doctor --fetch`
- **THEN** the file is downloaded into the folder's `checkpoints` subfolder and a later `slopoly doctor` passes that check

#### Scenario: Folder unknown
- **WHEN** the models folder is not configured and models are missing
- **THEN** `slopoly doctor --fetch` downloads nothing and prints each model's subfolder and URL and the command to set the
  folder

### Requirement: Blender libraries
`slopoly doctor --fetch` SHALL install the Python libraries the build needs into a Slopoly-managed folder for the found
Blender's bundled Python, without changing Blender's own installation.

#### Scenario: New Blender version
- **WHEN** the user switches to a newer supported Blender and runs `slopoly doctor --fetch`
- **THEN** the build libraries are installed for that Blender's Python, and builds run with it
