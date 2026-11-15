# Spec Delta

## Purpose

Lets users add Slopoly to the coding agent they already use: this repository is a plugin marketplace whose single
skill teaches the agent the asset workflow and drives the `slopoly` CLI.

## ADDED Requirements

### Requirement: Repository is a plugin marketplace
This repository SHALL be addable as a plugin marketplace in Claude Code and in GitHub Copilot CLI, and SHALL offer a
`slopoly` plugin from it. The same repository SHALL hold the CLI source, and the plugin and CLI versions SHALL be
the same.

#### Scenario: Add in Claude Code
- **WHEN** a user adds the repository as a marketplace in Claude Code and installs the `slopoly` plugin
- **THEN** the `slopoly` skill is available in their sessions

#### Scenario: Add in GitHub Copilot CLI
- **WHEN** a user adds the repository as a plugin marketplace in GitHub Copilot CLI and installs the `slopoly` plugin
- **THEN** the `slopoly` skill is available there

### Requirement: One skill with references
The plugin SHALL provide one skill, `slopoly`, whose main file covers the asset workflow and the CLI. It SHALL
point to reference files that the agent loads when needed: the part-program modelling API, the technique and object
notes, palette and shading guidance, and the ComfyUI setup.

#### Scenario: Agent loads the modelling reference
- **WHEN** the agent reaches the part-program step of an asset
- **THEN** the skill tells it which reference file describes the modelling API, and the main skill file does not
  repeat that API

### Requirement: CLI bootstrap
The skill SHALL tell the agent to check `slopoly --version` before its first command. When the command is missing
or reports a different version than the skill requires, the skill SHALL give the `uv tool install` command for the
matching version, and tell the agent to run `slopoly doctor` after installing.

#### Scenario: CLI not installed
- **WHEN** the agent starts the skill on a machine without the `slopoly` command
- **THEN** it installs the matching CLI version with uv, runs `slopoly doctor`, and reports any missing ComfyUI nodes,
  models or Blender libraries to the user

### Requirement: Agent-neutral content
The skill and its references SHALL NOT depend on features of one agent product. They SHALL use only reading files,
running shell commands and viewing image files, which the supported agents all offer.

#### Scenario: Same skill in two agents
- **WHEN** the same pack is worked on in Claude Code one day and in GitHub Copilot CLI the next
- **THEN** both follow the same skill and CLI, and the second agent continues from the workspace files and
  `slopoly status`
