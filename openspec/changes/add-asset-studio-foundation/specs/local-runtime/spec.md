# Spec Delta

## Purpose

Lets one developer start the whole Slopoly stack locally with one command, while keeping machine-specific paths and secrets out of the public repository.

## ADDED Requirements

### Requirement: One-command local start
Running the AppHost SHALL start the API, the web UI, the ComfyUI service, the geometry worker and the design agent, and the web UI SHALL be reachable in a local browser.

#### Scenario: Stack starts
- **WHEN** the developer runs `aspire start` with all required configuration present
- **THEN** every service reaches a healthy or running state and the web UI opens on a local URL

### Requirement: Configurable models folder
The ComfyUI service SHALL read and write models in a host folder chosen by local configuration. Models downloaded in the container SHALL land in that host folder.

#### Scenario: Shared models folder
- **GIVEN** the models-folder setting points to an existing host folder `<models-dir>`
- **WHEN** a model file is downloaded through the ComfyUI service
- **THEN** the file appears under `<models-dir>` on the host and remains after the container is removed

### Requirement: Configurable data folder
SQLite data and generated files SHALL be stored in a host folder chosen by local configuration, defaulting to a git-ignored folder inside the repository.

#### Scenario: Data survives restart
- **WHEN** the stack is stopped and started again
- **THEN** packs, assets, images and builds created earlier are still present

### Requirement: No machine-specific values in the repository
Host paths and secrets SHALL be supplied only through local, uncommitted configuration. Committed files SHALL show placeholders only.

#### Scenario: Missing setting
- **WHEN** a required setting such as the models folder or the agent token is not configured
- **THEN** the developer is prompted for it at start (or the dependent service reports it as missing), and nothing is written into tracked files

#### Scenario: Repository check
- **WHEN** the repository contents are inspected
- **THEN** no absolute host path to the developer's models or data and no agent token appear in tracked files, including specs and docs
