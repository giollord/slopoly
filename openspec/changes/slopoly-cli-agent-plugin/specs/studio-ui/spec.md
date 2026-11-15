# Spec Delta

## REMOVED Requirements

### Requirement: Concept page
**Reason**: The studio UI is removed.
**Migration**: Image metadata is in the YAML file beside each image. Revisions are requested from the agent, and
picking happens in the pick window.

### Requirement: Asset management
**Reason**: The studio UI is removed.
**Migration**: Use `slopoly asset new`, `slopoly rm` and `slopoly status`, or edit `asset.yaml`.

### Requirement: Manual asset editing and navigation
**Reason**: The studio UI is removed.
**Migration**: Edit `asset.yaml`, `manifest.yaml` and `program.py` directly and run `slopoly build`.

### Requirement: Concept management by kind
**Reason**: The studio UI is removed.
**Migration**: Use `slopoly gen` and `slopoly pick`. Images are grouped by folder (anchors, heroes, views).

### Requirement: Build comparison on the asset page
**Reason**: The asset page is removed.
**Migration**: The view window shows the comparison images and object scores (see interaction-windows).

### Requirement: Asset page layout
**Reason**: The asset page is removed.
**Migration**: None.

### Requirement: Reference hero on the asset page
**Reason**: The asset page is removed.
**Migration**: `slopoly status` names each variant's reference hero, and `slopoly pick` changes it.

### Requirement: Paged history lists
**Reason**: There are no UI lists.
**Migration**: `slopoly jobs` and the build folders replace the lists.

### Requirement: Long chats load in steps
**Reason**: Chats are removed.
**Migration**: None.

### Requirement: Chat drawer on every page
**Reason**: Chats are removed.
**Migration**: Use your agent's own interface.
