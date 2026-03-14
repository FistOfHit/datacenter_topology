# Worked Examples

These examples exercise the grouped topology model used for scalable-unit and pod-style fabrics.

## Example 1: Two Pods Leaf-Spine Fabric

Config: [`configs/examples/two_tier_small.yaml`](../configs/examples/two_tier_small.yaml)

Run:

```bash
topology-generator --config configs/examples/two_tier_small.yaml --output-dir output/two_tier_small
```

Expected result:

- 28 nodes total
- 96 graph edges
- 96 rows in `port_mapping.xlsx`

Topology shape:

- `pod_1` and `pod_2` each contain 8 compute nodes and 4 leaf switches
- 4 global spine switches are shared above both pods
- compute -> leaf uses `within_group_full_mesh`
- leaf -> spine uses `group_to_global_full_mesh`

Port model:

- compute is `400G` only
- leaf and spine expose both `400G` and `800G` modes from the same lane budget
- this particular example uses only `400G` links

## Example 2: Sixteen Pods with Pod-Local Spine and Shared Core

Config: [`configs/examples/three_tier_small.yaml`](../configs/examples/three_tier_small.yaml)

Run:

```bash
topology-generator --config configs/examples/three_tier_small.yaml --output-dir output/three_tier_small
```

Expected result:

- 1,344 nodes total
- 17,408 graph edges
- 24,576 rows in `port_mapping.xlsx`

Topology shape:

- `pod_1` through `pod_16` each contain 64 compute nodes, 8 leaf switches, and 8 spine switches
- compute -> leaf uses `within_group_full_mesh`
- leaf -> spine uses `within_group_full_mesh` with 8 cables per leaf/spine pair
- 64 global core switches sit above the pod-local spine layer
- spine -> core uses `group_to_global_full_mesh`

Port model:

- leaf, spine, and core each use `128` base lane units
- the same hardware can host either `128 x 400G`, `64 x 800G`, or a mixed allocation

## Example 3: Shared `gpu_nodes` With Pod And Rack Groupings

Config: [`configs/examples/multi_fabric_small.yaml`](../configs/examples/multi_fabric_small.yaml)

Run:

```bash
topology-generator --config configs/examples/multi_fabric_small.yaml --output-dir output/multi_fabric_small
```

Expected result:

- 6 graph nodes total
- 7 graph edges total
- 7 rows in `port_mapping.xlsx`
- `topology_backend.png`, `topology_frontend.png`, and `topology_oob.png`

Topology shape:

- `gpu_nodes` is the shared layer-0 population
- `groupings` declares both `pod = 2` and `rack = 1` for the same shared endpoints
- the backend fabric adds `leaf -> spine`
- the frontend fabric adds `tor`
- the OOB fabric selects the smaller `rack` grouping and adds `mgmt`
- each fabric is isolated for validation, diagrams, and Excel row generation

Port model:

- `gpu_nodes` capacity is declared once under `gpu_nodes.fabric_port_layouts`
- backend, frontend, and OOB each consume their own independent lane budget on the same GPU nodes
- backend and frontend rows export pod labels, while OOB rows export resolved rack labels
- the merged Excel output includes a `fabric` column so rows remain attributable after concatenation

## Example 4: Sixteen-Pod Backend Plus Separate Frontend Fabric

Config: [`configs/examples/multi_fabric_backend_frontend.yaml`](../configs/examples/multi_fabric_backend_frontend.yaml)

Run:

```bash
topology-generator --config configs/examples/multi_fabric_backend_frontend.yaml --output-dir output/multi_fabric_backend_frontend
```

Expected result:

- 1 merged `port_mapping.xlsx`
- `topology_backend.png`
- `topology_frontend.png`
- 27,648 rows in `port_mapping.xlsx`

Topology shape:

- `groupings` defines `pod = 64` across 1024 shared endpoints
- the `backend` fabric is the original three-tier sixteen-pod example:
  `gpu_nodes -> leaf -> spine -> core`
- the `frontend` fabric adds 2 pod-local leaf switches and 8 global spines:
  `gpu_nodes -> leaf -> spine`
- both fabrics reuse the same GPU nodes but remain isolated for validation, diagrams, and cut-sheet generation

Port model:

- `gpu_nodes` exposes `8 x 400G` to `backend`
- `gpu_nodes` exposes `2 x 400G` to `frontend`
- frontend leaves use the same `128 x 400G` lane budget as the backend switching layers
- each frontend leaf receives 64 GPU downlinks and 32 spine uplinks, for 96 total lane units
- each frontend global spine receives 128 total lane units across all pods

## Example 5: Sixteen-Pod Backend And Frontend Plus Rack-Scoped OOB

Config: [`configs/examples/multi_fabric_backend_frontend_oob.yaml`](../configs/examples/multi_fabric_backend_frontend_oob.yaml)

Run:

```bash
topology-generator --config configs/examples/multi_fabric_backend_frontend_oob.yaml --output-dir output/multi_fabric_backend_frontend_oob
```

Expected result:

- 1 merged `port_mapping.xlsx`
- `topology_backend.png`
- `topology_frontend.png`
- `topology_oob.png`
- 31,232 rows in `port_mapping.xlsx`

Topology shape:

- the shared endpoint population remains `1024` GPUs with `pod = 64`
- the added `rack = 8` grouping creates `128` rack-local OOB leaves
- the `backend` fabric stays `gpu_nodes -> leaf -> spine -> core`
- the `frontend` fabric stays `gpu_nodes -> leaf -> spine`
- the new `OOB` fabric is `gpu_nodes -> leaf -> spine` using the smaller `rack` grouping

Port model:

- each GPU exposes `3 x 1G` only to the `OOB` fabric
- each OOB leaf receives `8 * 3 = 24` GPU downlinks and `4 x 1G` uplinks, using `28 / 48` total 1G lanes
- OOB uses `4` global spines at `128 x 1G`
- because current link semantics are full adjacency between adjacent layers, each OOB leaf connects to every OOB spine with `1 x 1G`, for `512` OOB leaf-to-spine rows total
- OOB rows in the merged Excel output use resolved rack labels such as `pod_1_rack_1`
