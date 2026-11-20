# Spec Delta

## ADDED Requirements

### Requirement: Agent plans part shapes
The agent's instructions SHALL require a shape plan in the manifest for every part of an asset with more than about
eight parts, and for every distinctive part of smaller ones, before the first build. A plan describes the part's
shape character: plan shape, profile, bends, where its ends are, and what it touches. It also gives the construction
steps in modelling operations and the checks.

#### Scenario: Steam pipe
- **WHEN** the agent plans a steam pipe that narrows and flares
- **THEN** its manifest entry describes the pipe's profile and gives steps such as a cylinder, one end scaled down,
  extruded and flared out, before `program.py` is written

### Requirement: Agent checks plans against close-ups
Before the first build, the agent SHALL look at a `look` close-up of each distinctive part's reference region. It SHALL
correct a plan that disagrees with the close-up. After a build, it SHALL compare the part with the same close-up.
The user SHALL NOT be asked to approve plans; they correct them through review notes.

#### Scenario: Bone ends
- **WHEN** the close-up of the ribs shows the knobbed ends at the top beside the spine
- **THEN** the rib plan places the ends at the top, and the agent checks the built ribs from the same camera

### Requirement: Agent works through review notes
After a build worth showing, the agent SHALL open a review (see review-notes) and wait for the notes. It SHALL treat
each note's comment as authoritative and its part hits as hints. It SHALL address the notes in order, setting each
note's status with a reason. A note it cannot fix SHALL be set to `wontfix` and explained to the user.

#### Scenario: Hit on a neighbour
- **WHEN** a note says "cowcatcher should be a V" and its hits list the cowcatcher at 80 % and the deck at 20 %
- **THEN** the agent changes the cowcatcher and leaves the deck as it is

### Requirement: Stop criterion with user notes
Before any user review, the agent SHALL stop at the silhouette bar: the build is validated, the mean object IoU is at
least 0.8 and no view's IoU is below 0.7. After a review, it SHALL stop only when the build is validated, the variant
has no open notes, and every IoU drop since the review is explained in its report. A drop caused by a change the user
asked for SHALL count as explained.

#### Scenario: Longer cowcatcher lowers IoU
- **WHEN** the user's note makes the agent lengthen the cowcatcher and the side IoU drops from 0.77 to 0.71
- **THEN** the agent reports the drop as caused by note 1, and the drop does not keep it iterating
