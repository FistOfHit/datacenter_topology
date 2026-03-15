from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from topology_generator.config_identifiers import (
    DEFAULT_SINGLE_FABRIC_NAME,
    GPU_NODES_LAYER_NAME,
    build_fabric_qualified_node_id,
    build_global_node_id,
    build_group_label_node_id,
    build_grouped_node_id,
)
from topology_generator.config_types import (
    LayerConfig,
    PortLayoutConfig,
    TopologyConfig,
    ensure_topology_config,
)


@dataclass(frozen=True)
class ExpandedNode:
    node_id: str
    graph_node_id: str
    layer_index: int
    layer_name: str
    placement: str
    group_name: str | None
    group_index: int | None
    group_label: str | None
    node_ordinal: int
    physical_node_ordinal: int
    port_layout: PortLayoutConfig
    fabric_name: str | None
    is_shared_gpu_node: bool = False

    @property
    def total_lane_units(self) -> int:
        return self.port_layout.total_lane_units

    @property
    def base_lane_bandwidth_gb(self) -> float:
        return self.port_layout.base_lane_bandwidth_gb

    @property
    def supported_port_bandwidths_gb(self) -> tuple[float, ...]:
        return self.port_layout.supported_port_bandwidths_gb

    def lane_units_for_bandwidth(self, bandwidth_gb: float) -> int | None:
        return self.port_layout.lane_units_for_bandwidth(bandwidth_gb)


@dataclass(frozen=True)
class ExpandedLinkBundle:
    source_node_id: str
    target_node_id: str
    source_graph_node_id: str
    target_graph_node_id: str
    fabric_name: str | None
    num_cables: int
    cable_bandwidth_gb: float
    source_lane_units_per_cable: int
    target_lane_units_per_cable: int


@dataclass(frozen=True)
class ExpandedTopology:
    config: TopologyConfig
    nodes: tuple[ExpandedNode, ...]
    links: tuple[ExpandedLinkBundle, ...]


def expand_topology(config: TopologyConfig | dict[str, object]) -> ExpandedTopology:
    topology_config = ensure_topology_config(config)
    single_group = topology_config.group()
    single_group_indexes: tuple[int, ...] = (
        tuple(range(1, single_group.count + 1)) if single_group else ()
    )

    expanded_nodes: list[ExpandedNode] = []
    layer_nodes: dict[tuple[str, str], list[ExpandedNode]] = defaultdict(list)
    group_layer_nodes: dict[tuple[str, str, int], list[ExpandedNode]] = defaultdict(list)
    seen_node_ids: set[str] = set()

    for fabric in topology_config.iter_fabrics():
        fabric_key = _fabric_key(fabric.name)
        for layer in fabric.layers:
            if layer.placement == "global":
                for ordinal in range(1, layer.nodes_per_group + 1):
                    node = _build_expanded_node(
                        topology_config=topology_config,
                        layer=layer,
                        fabric_name=fabric.name,
                        grouping_name=fabric.grouping_name,
                        group_index=None,
                        node_ordinal=ordinal,
                    )
                    _append_expanded_node(
                        expanded_nodes,
                        layer_nodes[(fabric_key, layer.name)],
                        seen_node_ids,
                        node,
                    )
                continue

            group_indexes = tuple(fabric.group_indexes())
            if fabric.name is None:
                group_indexes = single_group_indexes

            for group_index in group_indexes:
                for ordinal in range(1, layer.nodes_per_group + 1):
                    node = _build_expanded_node(
                        topology_config=topology_config,
                        layer=layer,
                        fabric_name=fabric.name,
                        grouping_name=fabric.grouping_name,
                        group_index=group_index,
                        node_ordinal=ordinal,
                    )
                    _append_expanded_node(
                        expanded_nodes,
                        layer_nodes[(fabric_key, layer.name)],
                        seen_node_ids,
                        node,
                    )
                    group_layer_nodes[(fabric_key, layer.name, group_index)].append(node)

    expanded_links: list[ExpandedLinkBundle] = []
    for fabric in topology_config.iter_fabrics():
        fabric_key = _fabric_key(fabric.name)
        group_indexes = tuple(fabric.group_indexes())
        if fabric.name is None:
            group_indexes = single_group_indexes

        for link in fabric.links:
            if link.cables_per_pair == 0:
                continue

            lower_layer = fabric.layer(link.from_layer)
            upper_layer = fabric.layer(link.to_layer)
            source_lane_units_per_cable = lower_layer.lane_units_for_bandwidth(
                link.cable_bandwidth_gb
            )
            target_lane_units_per_cable = upper_layer.lane_units_for_bandwidth(
                link.cable_bandwidth_gb
            )
            if source_lane_units_per_cable is None or target_lane_units_per_cable is None:
                raise ValueError(
                    f"Unsupported cable bandwidth {link.cable_bandwidth_gb:g} GB/s for "
                    f"link {link.from_layer!r} -> {link.to_layer!r}."
                )

            if link.policy == "within_group_full_mesh":
                for group_index in group_indexes:
                    expanded_links.extend(
                        _full_mesh_link_bundles(
                            group_layer_nodes[(fabric_key, lower_layer.name, group_index)],
                            group_layer_nodes[(fabric_key, upper_layer.name, group_index)],
                            fabric.name,
                            link.cables_per_pair,
                            link.cable_bandwidth_gb,
                            source_lane_units_per_cable,
                            target_lane_units_per_cable,
                        )
                    )
                continue

            if link.policy == "group_to_global_full_mesh":
                global_nodes = layer_nodes[(fabric_key, upper_layer.name)]
                for group_index in group_indexes:
                    expanded_links.extend(
                        _full_mesh_link_bundles(
                            group_layer_nodes[(fabric_key, lower_layer.name, group_index)],
                            global_nodes,
                            fabric.name,
                            link.cables_per_pair,
                            link.cable_bandwidth_gb,
                            source_lane_units_per_cable,
                            target_lane_units_per_cable,
                        )
                    )
                continue

            expanded_links.extend(
                _full_mesh_link_bundles(
                    layer_nodes[(fabric_key, lower_layer.name)],
                    layer_nodes[(fabric_key, upper_layer.name)],
                    fabric.name,
                    link.cables_per_pair,
                    link.cable_bandwidth_gb,
                    source_lane_units_per_cable,
                    target_lane_units_per_cable,
                )
            )

    return ExpandedTopology(
        config=topology_config,
        nodes=tuple(expanded_nodes),
        links=tuple(expanded_links),
    )


def _fabric_key(fabric_name: str | None) -> str:
    return fabric_name or DEFAULT_SINGLE_FABRIC_NAME


def _build_expanded_node(
    topology_config: TopologyConfig,
    layer: LayerConfig,
    fabric_name: str | None,
    grouping_name: str | None,
    group_index: int | None,
    node_ordinal: int,
) -> ExpandedNode:
    is_shared_gpu_node = fabric_name is not None and layer.name == GPU_NODES_LAYER_NAME

    if group_index is None:
        graph_node_id = build_global_node_id(layer.name, node_ordinal)
        group_name = None
        group_label = None
        physical_node_ordinal = node_ordinal
    elif fabric_name is None:
        graph_node_id = build_grouped_node_id(
            layer.placement,
            group_index,
            layer.name,
            node_ordinal,
        )
        group_name = layer.placement
        group_label = f"{group_name}_{group_index}"
        physical_node_ordinal = node_ordinal
    else:
        assert grouping_name is not None
        group_name = grouping_name
        group_label = topology_config.group_label_for_group(grouping_name, group_index)
        if is_shared_gpu_node:
            physical_node_ordinal = topology_config.physical_node_ordinal(
                grouping_name,
                group_index,
                node_ordinal,
            )
            graph_node_id = build_global_node_id(layer.name, physical_node_ordinal)
        else:
            physical_node_ordinal = node_ordinal
            graph_node_id = build_group_label_node_id(group_label, layer.name, node_ordinal)

    if is_shared_gpu_node:
        assert fabric_name is not None
        node_id = build_fabric_qualified_node_id(fabric_name, graph_node_id)
    elif fabric_name is None:
        node_id = graph_node_id
    else:
        graph_node_id = build_fabric_qualified_node_id(fabric_name, graph_node_id)
        node_id = graph_node_id

    return ExpandedNode(
        node_id=node_id,
        graph_node_id=graph_node_id,
        layer_index=layer.index,
        layer_name=layer.name,
        placement=layer.placement,
        group_name=group_name,
        group_index=group_index,
        group_label=group_label,
        node_ordinal=node_ordinal,
        physical_node_ordinal=physical_node_ordinal,
        port_layout=layer.port_layout,
        fabric_name=fabric_name,
        is_shared_gpu_node=is_shared_gpu_node,
    )


def _append_expanded_node(
    expanded_nodes: list[ExpandedNode],
    layer_node_list: list[ExpandedNode],
    seen_node_ids: set[str],
    node: ExpandedNode,
) -> None:
    if node.node_id in seen_node_ids:
        raise ValueError(f"Expanded node ID collision detected for {node.node_id!r}.")
    seen_node_ids.add(node.node_id)
    expanded_nodes.append(node)
    layer_node_list.append(node)


def _full_mesh_link_bundles(
    source_nodes: list[ExpandedNode],
    target_nodes: list[ExpandedNode],
    fabric_name: str | None,
    num_cables: int,
    cable_bandwidth_gb: float,
    source_lane_units_per_cable: int,
    target_lane_units_per_cable: int,
) -> list[ExpandedLinkBundle]:
    return [
        ExpandedLinkBundle(
            source_node_id=source.node_id,
            target_node_id=target.node_id,
            source_graph_node_id=source.graph_node_id,
            target_graph_node_id=target.graph_node_id,
            fabric_name=fabric_name,
            num_cables=num_cables,
            cable_bandwidth_gb=cable_bandwidth_gb,
            source_lane_units_per_cable=source_lane_units_per_cable,
            target_lane_units_per_cable=target_lane_units_per_cable,
        )
        for source in source_nodes
        for target in target_nodes
    ]
