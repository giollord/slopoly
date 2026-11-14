# generation-jobs Specification

## Purpose
Runs every slow operation (image generation, segmentation, geometry builds, agent turns) as a tracked background job. Workers receive jobs over outbound connections only, so a worker can later run on another machine than the API.

## Requirements

### Requirement: Job submission and state
Jobs SHALL have a kind, inputs, a target pack or asset and a state. The state is one of queued, running, succeeded, failed or cancelled, and SHALL be visible in the UI as it changes.

#### Scenario: Job lifecycle
- **WHEN** a turnaround job is submitted
- **THEN** it shows as queued, then running with progress, then succeeded with links to its outputs

### Requirement: Outbound worker dispatch
Workers SHALL receive jobs only through connections they open themselves. Neither the API nor the broker SHALL open connections to workers. A worker SHALL receive only the job kinds it subscribes to.

#### Scenario: Matching kind
- **GIVEN** a geometry worker that subscribes to the build kind
- **WHEN** both an image job and a build job are queued
- **THEN** the geometry worker receives only the build job

### Requirement: Redelivery after worker loss
A job whose worker disconnects or stops before reporting a result SHALL be delivered again to a worker of that kind, and the job's attempt count SHALL increase.

#### Scenario: Worker dies mid-job
- **WHEN** the worker running a job stops without reporting
- **THEN** the job returns to queued and another or restarted worker receives it

### Requirement: Cancel and retry
The user and the agent SHALL be able to cancel a queued or running job and retry a failed or cancelled one. A worker SHALL stop work on a cancelled job and discard its result.

#### Scenario: Cancel running generation
- **WHEN** the user cancels a running image job
- **THEN** the job becomes cancelled, the worker interrupts the generation, and no output is attached

#### Scenario: Cancel before start
- **WHEN** the user cancels a queued job
- **THEN** the job becomes cancelled and no worker runs it

### Requirement: Failure reporting
A failed job SHALL record a human-readable error, and the agent SHALL be able to read it.

#### Scenario: Workflow error
- **WHEN** ComfyUI rejects a workflow because a model file is missing
- **THEN** the job fails with an error naming the missing model

### Requirement: One GPU job at a time
GPU-using jobs SHALL run one at a time on the local machine.

#### Scenario: Long job not cut off
- **WHEN** a job runs longer than an hour while its worker stays connected
- **THEN** the job is not redelivered or cancelled because of its duration

#### Scenario: Two image jobs
- **WHEN** two image jobs are queued
- **THEN** the second starts only after the first finishes
