# Spec Delta

## ADDED Requirements

### Requirement: Detached jobs
Image generation, views, segmentation and pick commands SHALL start a detached background process and return its job
id at once. The job SHALL keep running after the starting command and the agent's shell exit.

#### Scenario: Agent shell times out
- **WHEN** the agent starts a views job and its shell command ends before the job finishes
- **THEN** the job keeps running and its outputs are written to the variant when it finishes

### Requirement: Waiting for a job
`slopoly wait <id> [--timeout <seconds>]` SHALL block until the job finishes or the timeout passes. On finish it SHALL
return the job's final state and result, and on timeout it SHALL return the state `pending` with the job's progress.
Waiting SHALL have no side effects and SHALL be repeatable.

#### Scenario: User takes their time
- **WHEN** the agent waits on a pick job with a 9-minute timeout and the user has not confirmed yet
- **THEN** wait returns `pending`, and a later wait returns the user's choice once they confirm

#### Scenario: Wait on a finished job
- **WHEN** the agent waits on a job that finished an hour ago
- **THEN** wait returns its final state and result at once

### Requirement: Orphaned jobs
A job whose process no longer exists while its state is queued or running SHALL be reported as failed with reason
`orphaned` by `wait`, `jobs` and `status`.

#### Scenario: Machine restarted
- **WHEN** the machine restarts while a views job is running and the agent then runs `slopoly jobs`
- **THEN** the job is listed as failed with reason `orphaned`, and it can be retried

## MODIFIED Requirements

### Requirement: Job submission and state
Jobs SHALL have an id, a kind, inputs, a target pack, asset or variant and a state, recorded in a job file in the
pack's `jobs/` folder. The state is one of queued, running, succeeded, failed or cancelled. `slopoly jobs` SHALL list a
pack's jobs with their states and progress.

#### Scenario: Job lifecycle
- **WHEN** a hero job is started
- **THEN** its job file shows queued, then running with progress, then succeeded with the paths of its output images

### Requirement: Cancel and retry
The user and the agent SHALL be able to cancel a queued or running job with `slopoly cancel <id>` and retry a failed
or cancelled job with `slopoly retry <id>`. Cancelling SHALL stop the job's process, remove its pending work from
ComfyUI, and attach no output. Retrying SHALL start a new job with the same inputs.

#### Scenario: Cancel running generation
- **WHEN** the user cancels a running image job
- **THEN** the job becomes cancelled, ComfyUI stops or drops its prompt, and no image is added to the pack

#### Scenario: Cancel before start
- **WHEN** the user cancels a job that is still waiting in ComfyUI's queue
- **THEN** the job becomes cancelled and ComfyUI never runs it

#### Scenario: Retry a failed job
- **WHEN** the agent retries a views job that failed because a model was missing, after fetching the model
- **THEN** a new job with the same inputs runs and its id is returned

### Requirement: Failure reporting
A failed job SHALL record a human-readable error and a stable error code in its job file, and `wait` and `jobs` SHALL
return them.

#### Scenario: Workflow error
- **WHEN** ComfyUI rejects a workflow because a model file is missing
- **THEN** the job fails with code `missing_model` and an error naming the missing model and `slopoly doctor --fetch`

### Requirement: One GPU job at a time
GPU-using jobs SHALL run one at a time on the configured ComfyUI. Jobs SHALL submit to ComfyUI's own queue and SHALL
NOT be cut off because of how long they run.

#### Scenario: Long job not cut off
- **WHEN** a job runs longer than an hour
- **THEN** it is not cancelled or failed because of its duration

#### Scenario: Two image jobs
- **WHEN** two image jobs are started one after the other
- **THEN** the second one's generation starts only after the first one's finishes

## REMOVED Requirements

### Requirement: Outbound worker dispatch
**Reason**: There are no workers or message broker. Jobs are local processes started by the CLI.
**Migration**: None needed. ComfyUI is reached over its HTTP API.

### Requirement: Redelivery after worker loss
**Reason**: Without a broker, a lost job process cannot be redelivered.
**Migration**: Lost jobs are reported as `orphaned` (see "Orphaned jobs") and can be retried with `slopoly retry`.
