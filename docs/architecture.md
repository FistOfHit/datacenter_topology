# Architecture Overview

## Execution Flow

The application is a single CLI pipeline:

1. Parse arguments.
2. Create the output directory and configure logging.
3. Load and validate YAML into `TopologyConfig`.
4. Build a `networkx.Graph` representing the ordered-layer topology.
5. Render the graph to `topology.png`.
6. Flatten graph edges into a port-mapping DataFrame.
7. Write the Excel output.

## Core Modules

### `config_schema.py`

Defines the validated config model:

- `LayerConfig`: per-layer node counts, port capacity, and adjacent-layer link settings.
- `TopologyConfig`: validated ordered layer list with dict-like compatibility.

Validation enforces:

- at least two layers
- positive node counts
- boundary-layer omission rules for non-existent directions
- exact reciprocity between adjacent layers
- cable bandwidth not exceeding either endpoint port speed
- enough physical ports for the dense adjacent-layer cabling pattern

Aggregate bandwidth is no longer configured directly. It is derived from layer sizes and adjacent link settings.

### `topology_generator.py`

Responsible for graph construction.

- Creates nodes for each configured layer.
- Stores `layer_index` and `layer_name` on every node.
- Derives up/down aggregate bandwidth metadata from adjacent-layer definitions.
- Connects adjacent layers in a dense pattern until the derived per-node bandwidth budget is consumed.
- Tracks per-node bandwidth usage and computes a ports-used equivalent value.

### `visualiser.py`

Responsible for diagram generation.

- Positions nodes by `layer_index`.
- Condenses layers with more than two nodes to first/last plus a placeholder label.
- Draws link counts, aggregate bandwidth markers, and fanout annotations.
- Uses deterministic colors for both layers and multi-bandwidth links.

### `port_mapper.py`

Responsible for the Excel cut-sheet data.

- Converts graph edges into one row per cable.
- Normalizes row orientation so lower-index layers appear as sources.
- Writes `port_mapping.xlsx`.

## Testing Strategy

The repo uses behavior-first tests across two-layer and four-layer configs:

- unit tests for config validation, topology invariants, port-map extraction, logging, CLI parsing, and visualization helpers
- integration coverage for the full CLI pipeline, including output creation

Tests constrain public behavior rather than internal call structure.
