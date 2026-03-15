# Diagram Visual Refresh Plan

This document is a forward-looking proposal, not current shipped behavior.

- Use [architecture.md](architecture.md) for the current renderer structure.
- Use [configuration.md](configuration.md) and the test suite for the current
  supported behavior.

## Summary

This document captures the agreed future visual updates for rendered topology
diagrams. The scope is intentionally limited to presentation changes in the
renderer; it does not change the CLI, graph generation, config schema, Excel
export, or output filenames.

Requested changes:

- add a legend entry for the per-node uplink/downlink aggregate bandwidth arrows
- move the per-node uplink/downlink arrows and labels slightly closer to the
  leftmost visible nodes
- increase title size
- change multi-fabric titles from `Network Topology (<fabric>)` to
  `<fabric> topology`

## Implementation Plan

### Legend updates

- Add a dedicated legend entry for the per-node aggregate bandwidth arrows in
  `topology_generator/render_drawing.py`.
- Represent the legend glyph as an uplink arrow symbol/downlink arrow symbol in
  a single legend entry.
- Use the exact label:
  `per node agg uplink/downlink BW`
- Keep the existing legend entries for cable count and link bandwidth colors.
- Place the new legend item with the other explanatory legend keys rather than
  treating it as a link-bandwidth color entry.

### Per-node aggregate arrow placement

- Adjust the geometry used for per-node aggregate bandwidth indicators so the
  arrow-and-text cluster sits slightly closer to the leftmost visible nodes.
- Apply the change through the existing left-side aggregate indicator offsets in
  `NodeBoxGeometry`, not by introducing a separate layout path.
- Update the matching left-extent geometry so plot bounds and grouped container
  bounds remain consistent with the new indicator position.
- Preserve current semantics:
  - indicators remain attached only to the leftmost visible node in each layer
  - arrow direction and text formatting remain unchanged
  - right-side layer bandwidth arrows are unaffected

### Title formatting and size

- Keep the single-fabric title as `Network Topology`.
- Change multi-fabric titles from `Network Topology (<fabric>)` to
  `<fabric> topology`.
- Use the raw fabric name in the visible title text.
- Keep output filenames unchanged and still normalized through the existing
  fabric output name logic.
- Increase the rendered title font size through an explicit constant in the
  render modules rather than relying on Matplotlib defaults.

## Proposed Concrete Changes

- In `topology_generator/render_drawing.py`, extract legend assembly into a small
  helper so the new aggregate-bandwidth legend item is defined in one place.
- Add a proxy legend handle for the per-node aggregate arrow entry.
- Tighten the left offset used by the aggregate arrow/text block by updating:
  - `aggregate_x_offset`
  - `aggregate_left_extent`
- Keep `aggregate_text_offset` unchanged unless visual verification shows that
  text spacing against the arrow itself has become cramped.
- Replace the current multi-fabric hard-coded title string construction with a
  small title-formatting helper.
- Replace implicit title sizing with an explicit title font-size constant and
  pass it when drawing the title.

## Tests

Update or add focused coverage in `tests/unit/test_rendering.py`:

- verify the new title formatting for multi-fabric renders
- verify the single-fabric title remains `Network Topology`
- verify the legend includes `per node agg uplink/downlink BW`
- lock the aggregate indicator geometry values that control the new placement

Validation to run when this work is implemented:

- `./.venv/bin/python -m pytest -q`
- `./.venv/bin/python -m ruff check .`

## Assumptions

- “A little closer” should be implemented as a small geometry adjustment, not a
  broader layout redesign.
- The requested title text change applies only to multi-fabric diagrams for now.
- No change is intended to output file naming, config behavior, or rendered
  node/link semantics.
