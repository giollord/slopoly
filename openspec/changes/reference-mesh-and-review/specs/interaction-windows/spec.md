# Spec Delta

## MODIFIED Requirements

### Requirement: View window
`slopoly view <target>` SHALL open a window with the 3D viewer (see asset-viewer) for a variant's current build, a
given build or a scene, and return at once with the window's local address in its result. For a build it SHALL also
show each view's comparison image with its object score, the validation summary and the shading defect counts.

#### Scenario: Look at the cart
- **WHEN** the agent or user runs `slopoly view gnome-village/cart`
- **THEN** a window shows the cart's current build in the 3D viewer, with its comparison images and scores beside it,
  and the command's result includes the window's address

#### Scenario: Live refresh
- **WHEN** a view window shows a variant's current build and a new build becomes current
- **THEN** the window loads the new build without being reopened

### Requirement: Browser fallback
When no native window can be opened, the pick, view and review commands SHALL serve the same page on a local address
bound to the loopback interface, open it in the default browser, and include the address in their result. After a
pick is confirmed or a review is sent, the page SHALL tell the user they can close the tab.

#### Scenario: No GUI backend
- **WHEN** `slopoly pick` runs on a machine where the native window library has no backend
- **THEN** the page opens in the browser, the result includes its local address, and confirming records the choice as
  in the window

#### Scenario: Review in the browser
- **WHEN** `slopoly review` runs without a native window backend
- **THEN** the review page opens in the browser, painting and sending work as in the window, and the job result has
  the notes
