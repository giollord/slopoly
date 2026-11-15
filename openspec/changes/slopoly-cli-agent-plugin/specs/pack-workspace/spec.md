# Spec Delta

## Purpose

Defines where Slopoly keeps a project's packs, assets, images, programs and builds: plain files in a `slopoly/`
folder inside the user's own repository, readable and editable by people and agents.

## ADDED Requirements

### Requirement: Workspace inside the user's repository
`slopoly init` SHALL create a workspace folder `slopoly/` in the current directory, marked by a `slopoly.yaml` file.
Commands SHALL find the workspace by walking up from the current directory to the nearest `slopoly/slopoly.yaml`,
or use the folder given by the `SLOPOLY_WORKSPACE` environment variable.

#### Scenario: Run from a subfolder
- **GIVEN** a repository with `slopoly/slopoly.yaml` at its root
- **WHEN** the agent runs `slopoly status` from `src/game/`
- **THEN** the command uses the repository's workspace

#### Scenario: No workspace
- **WHEN** a command runs where no workspace can be found
- **THEN** it fails with code `no_workspace` and a hint to run `slopoly init`

### Requirement: Plain-file storage
All pack content SHALL be stored as files in the workspace: settings and metadata as YAML, style text as Markdown,
images and masks as PNG, part programs as Python, builds as GLB and .blend files with JSON reports. No database
SHALL be used.

#### Scenario: Inspect a pack without the CLI
- **WHEN** the user opens `slopoly/gnome-village/` in a file browser
- **THEN** they find the pack settings, style text, palette, images, manifests, programs and builds as ordinary files

### Requirement: Pack folder layout
A pack folder SHALL hold `pack.yaml`, `style.md`, `palette.yaml`, its style reference images, its style anchors,
an `assets/` folder with one folder per asset, a `scenes/` folder, and a `jobs/` folder. An asset folder SHALL hold
`asset.yaml` and a `variants/` folder with one folder per variant, holding the variant's heroes, views, masks,
manifest, `program.py` and numbered builds.

#### Scenario: Scaffolded pack
- **WHEN** the agent runs `slopoly pack new gnome-village`
- **THEN** `slopoly/gnome-village/` holds `pack.yaml`, `style.md`, `palette.yaml` and empty `anchors/`, `assets/`,
  `scenes/` and `jobs/` folders

### Requirement: Image metadata beside each image
Each generated image SHALL have a YAML file of the same name beside it, recording its kind, prompt, seed, references,
the job that made it and its selection state (picked, rejected or undecided).

#### Scenario: Hero metadata
- **WHEN** a hero job produces `heroes/hero_003.png`
- **THEN** `heroes/hero_003.yaml` records kind hero, the prompt, the seed, the anchors used as references, the job id
  and state undecided

### Requirement: No version control by Slopoly
Slopoly SHALL NOT run git or any other version control command, and SHALL NOT create repositories or submodules.
History beyond the build snapshots is the user's own commits.

#### Scenario: Build in a git repository
- **WHEN** the agent builds an asset in a workspace inside a git repository
- **THEN** the new build files appear as untracked changes and no commit, stage or branch is made

### Requirement: Generated gitignore
Creating a pack SHALL write a `.gitignore` in the pack folder. It SHALL ignore the `jobs/` folder and the binary files
(models, Blender files, renders and comparisons) of every build that is not a variant's current build. Each build's
program and report SHALL stay committable. Slopoly SHALL keep this file current when the current build changes and
SHALL NOT touch lines the user adds outside its marked section.

#### Scenario: Older build ignored
- **GIVEN** the cart's default variant has builds 1 to 6 and build 6 is current
- **WHEN** the user runs `git status`
- **THEN** build 6's model, Blender file and images are listed, builds 1 to 5 show only `program.py` and
  `report.json`, and nothing under `jobs/` is listed

#### Scenario: User lines kept
- **WHEN** the user adds `*.psd` to the pack's `.gitignore` and the current build changes
- **THEN** the `*.psd` line is still there

### Requirement: Machine settings outside the workspace
Machine-specific settings (ComfyUI URL, ComfyUI models folder, Blender path, viewer preferences) SHALL be stored in the
user's configuration directory and SHALL NOT be written to the workspace.

#### Scenario: Shared repository
- **WHEN** two users with different ComfyUI and Blender installs work in clones of the same repository
- **THEN** each uses their own settings, and no workspace file contains either user's paths or URLs
