# Worked Examples

These examples are realistic enough to look like actual fabrics while still being stable regression targets for the current dense-adjacency generator.

## Example 1: Two-Tier Leaf-Spine Fabric

Config: [`configs/examples/two_tier_small.yaml`](../configs/examples/two_tier_small.yaml)

Run:

```bash
topology-generator --config configs/examples/two_tier_small.yaml --output-dir output/two_tier_small
```

Expected result:

- 44 nodes total
- 288 graph edges
- 512 rows in `port_mapping.xlsx`

Topology shape:

- 32 compute nodes
- 8 leaf switches
- 4 spine switches
- 1 x 400G cable from each compute node to each leaf
- 8 x 400G cables from each leaf to each spine
- non-blocking across both inter-layer stages

## Example 2: Three-Tier Leaf-Spine-Core Fabric

Config: [`configs/examples/three_tier_small.yaml`](../configs/examples/three_tier_small.yaml)

Run:

```bash
topology-generator --config configs/examples/three_tier_small.yaml --output-dir output/three_tier_small
```

Expected result:

- 62 nodes total
- 424 graph edges
- 832 rows in `port_mapping.xlsx`

Topology shape:

- 48 compute nodes
- 8 leaf switches
- 4 spine switches
- 2 core switches
- 1 x 400G cable from each compute node to each leaf
- 12 x 400G cables from each leaf to each spine
- 8 x 400G cables from each spine to each core
- non-blocking from compute to spine, then intentionally blocking at the core layer

## Example 3: Repository Default Config

Config: [`config.yaml`](../config.yaml)

Run:

```bash
topology-generator --config config.yaml --output-dir output/default_config
```

This default config is a generic four-layer fabric that exercises dense adjacency, condensed rendering, and multi-tier export.
