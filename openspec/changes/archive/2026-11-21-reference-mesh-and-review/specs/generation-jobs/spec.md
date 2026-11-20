# Spec Delta

## MODIFIED Requirements

### Requirement: Cancel and retry
The user and the agent SHALL be able to cancel a queued or running job with `slopoly cancel <id>` and retry a failed
or cancelled job of any kind with `slopoly retry <id>`. Cancelling SHALL stop the job's process, remove its pending
work from ComfyUI, and attach no output. Retrying SHALL start a new job with the same inputs.

#### Scenario: Cancel running generation
- **WHEN** the user cancels a running image job
- **THEN** the job becomes cancelled, ComfyUI stops or drops its prompt, and no image is added to the pack

#### Scenario: Cancel before start
- **WHEN** the user cancels a job that is still waiting in ComfyUI's queue
- **THEN** the job becomes cancelled and ComfyUI never runs it

#### Scenario: Retry a failed job
- **WHEN** the agent retries a views job that failed because a model was missing, after fetching the model
- **THEN** a new job with the same inputs runs and its id is returned

#### Scenario: Retry a segmentation
- **WHEN** the agent retries a failed segment job
- **THEN** a new segment job with the same inputs starts

## ADDED Requirements

### Requirement: Job files survive concurrent readers
Writing a job file SHALL NOT fail because another process is reading it at that moment. On Windows, a replace that is
denied SHALL be retried briefly before the job fails.

#### Scenario: Waiting while the job writes
- **WHEN** `slopoly wait` polls a segment job's file while the job writes its progress
- **THEN** the job keeps running and finishes normally
