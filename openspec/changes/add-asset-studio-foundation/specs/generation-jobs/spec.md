# Spec Delta

## Purpose

Runs every slow operation (image generation, segmentation, geometry builds) as a tracked background job. Workers claim jobs over outbound connections, so a worker can later run on another machine than the API.

## ADDED Requirements

### Requirement: Job submission and state
Jobs SHALL have a kind, inputs, a target pack or asset and a state. The state is one of queued, running, succeeded, failed or cancelled, and SHALL be visible in the UI as it changes.

#### Scenario: Job lifecycle
- **WHEN** a turnaround job is submitted
- **THEN** it shows as queued, then running with progress, then succeeded with links to its outputs

### Requirement: Outbound worker claim
Workers SHALL obtain jobs by calling the API. The API SHALL never open connections to workers. A worker SHALL claim only job kinds it declares.

#### Scenario: Matching kind
- **GIVEN** a geometry worker that declares the build kind
- **WHEN** both an image job and a build job are queued
- **THEN** the geometry worker claims only the build job

### Requirement: Leases and recovery
A claimed job SHALL hold a lease that the worker renews while working. If the lease expires, the job SHALL return to the queue.

#### Scenario: Worker dies mid-job
- **WHEN** the worker running a job stops without reporting
- **THEN** after the lease expires the job is queued again and another or restarted worker can claim it

### Requirement: Cancel and retry
The user and the agent SHALL be able to cancel a queued or running job and retry a failed or cancelled one. A worker SHALL stop work on a cancelled job and discard its result.

#### Scenario: Cancel running generation
- **WHEN** the user cancels a running image job
- **THEN** the job becomes cancelled, the worker interrupts the generation, and no output is attached

### Requirement: Failure reporting
A failed job SHALL record a human-readable error, and the agent SHALL be able to read it.

#### Scenario: Workflow error
- **WHEN** ComfyUI rejects a workflow because a model file is missing
- **THEN** the job fails with an error naming the missing model

### Requirement: One GPU job at a time
GPU-using jobs SHALL run one at a time on the local machine.

#### Scenario: Two image jobs
- **WHEN** two image jobs are queued
- **THEN** the second starts only after the first finishes
