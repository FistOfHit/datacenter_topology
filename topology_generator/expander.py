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
    normalize_identifier,
)
from topology_generator.config_types import (
    LayerConfig,
    PortPoolConfig,
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
    placement_scope: str | None
    scope_names: tuple[str, ...]
    scope_indexes: tuple[int, ...]
    scope_labels: tuple[str, ...]
    scope_key: tuple[tuple[str, int], ...]
    group_name: str | None
    group_index: int | None
    group_label: str | None
    node_ordinal: int
    physical_node_ordinal: int
    port_pools: tuple[PortPoolConfig, ...]
    fabric_name: str | None
    is_shared_gpu_node: bool = False

    @property
    def supported_port_bandwidths_gb(self) -> tuple[float, ...]:
        seen_bandwidths: list[float] = []
        for port_pool in self.port_pools:
            for bandwidth_gb in port_pool.supported_port_bandwidths_gb:
                if bandwidth_gb in seen_bandwidths:
                    continue
                seen_bandwidths.append(bandwidth_gb)
        return tuple(seen_bandwidths)

    def port_pool(self, pool_name: str) -> PortPoolConfig:
        for port_pool in self.port_pools:
            if port_pool.name == pool_name:
                return port_pool
        normalized_pool_name = normalize_identifier(pool_name)
        for port_pool in self.port_pools:
            if normalize_identifier(port_pool.name) == normalized_pool_name:
                return port_pool
        raise KeyError(pool_name)

    def port_pool_offset(self, pool_name: str) -> int:
        offset = 0
        for port_pool in self.port_pools:
            if port_pool.name == pool_name:
                return offset
            offset += port_pool.total_lane_units

        normalized_pool_name = normalize_identifier(pool_name)
        offset = 0
        for port_pool in self.port_pools:
            if normalize_identifier(port_pool.name) == normalized_pool_name:
                return offset
            offset += port_pool.total_lane_units
        raise KeyError(pool_name)

    def lane_units_for_pool_bandwidth(
        self,
        pool_name: str,
        bandwidth_gb: float,
    ) -> int | None:
        try:
            return self.port_pool(pool_name).lane_units_for_bandwidth(bandwidth_gb)
        except KeyError:
            return None


@dataclass(frozen=True)
class ExpandedLinkBundle:
    source_node_id: str
    target_node_id: str
    source_graph_node_id: str
    target_graph_node_id: str
    fabric_name: str | None
    port_pool: str
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
    scope_layer_nodes: dict[
        tuple[str, str, tuple[tuple[str, int], ...]],
        list[ExpandedNode],
    ] = defaultdict(list)
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

            if fabric.name is None:
                group_indexes = single_group_indexes
            else:
                group_indexes = tuple(
                    range(1, topology_config.scope_instance_count(layer.placement) + 1)
                )

            for group_index in group_indexes:
                for ordinal in range(1, layer.nodes_per_group + 1):
                    node = _build_expanded_node(
                        topology_config=topology_config,
                        layer=layer,
                        fabric_name=fabric.name,
                        group_index=group_index,
                        node_ordinal=ordinal,
                    )
                    _append_expanded_node(
                        expanded_nodes,
                        layer_nodes[(fabric_key, layer.name)],
                        seen_node_ids,
                        node,
                    )
                    scope_layer_nodes[(fabric_key, layer.name, node.scope_key)].append(node)

    expanded_links: list[ExpandedLinkBundle] = []
    for fabric in topology_config.iter_fabrics():
        fabric_key = _fabric_key(fabric.name)

        for link in fabric.links:
            if link.cables_per_pair == 0:
                continue

            lower_layer = fabric.layer(link.from_layer)
            upper_layer = fabric.layer(link.to_layer)
            source_lane_units_per_cable = lower_layer.lane_units_for_pool_bandwidth(
                link.port_pool,
                link.cable_bandwidth_gb,
            )
            target_lane_units_per_cable = upper_layer.lane_units_for_pool_bandwidth(
                link.port_pool,
                link.cable_bandwidth_gb,
            )
            if source_lane_units_per_cable is None or target_lane_units_per_cable is None:
                raise ValueError(
                    f"Unsupported cable bandwidth {link.cable_bandwidth_gb:g} GB/s for "
                    f"link {link.from_layer!r} -> {link.to_layer!r} in port pool "
                    f"{link.port_pool!r}."
                )

            if link.policy == "same_scope_full_mesh":
                for scope_key in _scope_keys_for_layer(
                    topology_config,
                    lower_layer,
                    fabric.name,
                    single_group_indexes,
                ):
                    expanded_links.extend(
                        _full_mesh_link_bundles(
                            scope_layer_nodes[(fabric_key, lower_layer.name, scope_key)],
                            scope_layer_nodes[(fabric_key, upper_layer.name, scope_key)],
                            fabric.name,
                            link.port_pool,
                            link.cables_per_pair,
                            link.cable_bandwidth_gb,
                            source_lane_units_per_cable,
                            target_lane_units_per_cable,
                        )
                    )
                continue

            if link.policy == "to_ancestor_full_mesh":
                ancestor_depth = len(
                    topology_config.scope_names_for_scope(upper_layer.placement)
                )
                for scope_key in _scope_keys_for_layer(
                    topology_config,
                    lower_layer,
                    fabric.name,
                    single_group_indexes,
                ):
                    ancestor_scope_key = scope_key[:ancestor_depth]
                    expanded_links.extend(
                        _full_mesh_link_bundles(
                            scope_layer_nodes[(fabric_key, lower_layer.name, scope_key)],
                            scope_layer_nodes[
                                (fabric_key, upper_layer.name, ancestor_scope_key)
                            ],
                            fabric.name,
                            link.port_pool,
                            link.cables_per_pair,
                            link.cable_bandwidth_gb,
                            source_lane_units_per_cable,
                            target_lane_units_per_cable,
                        )
                    )
                continue

            if link.policy == "to_global_full_mesh":
                global_nodes = layer_nodes[(fabric_key, upper_layer.name)]
                for scope_key in _scope_keys_for_layer(
                    topology_config,
                    lower_layer,
                    fabric.name,
                    single_group_indexes,
                ):
                    expanded_links.extend(
                        _full_mesh_link_bundles(
                            scope_layer_nodes[(fabric_key, lower_layer.name, scope_key)],
                            global_nodes,
                            fabric.name,
                            link.port_pool,
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
                    link.port_pool,
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
    group_index: int | None,
    node_ordinal: int,
) -> ExpandedNode:
    is_shared_gpu_node = fabric_name is not None and layer.name == GPU_NODES_LAYER_NAME

    if group_index is None:
        graph_node_id = build_global_node_id(layer.name, node_ordinal)
        placement_scope = None
        scope_names: tuple[str, ...] = ()
        scope_indexes: tuple[int, ...] = ()
        scope_labels: tuple[str, ...] = ()
        scope_key: tuple[tuple[str, int], ...] = ()
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
        placement_scope = layer.placement
        scope_names = (layer.placement,)
        scope_indexes = (group_index,)
        group_label = f"{layer.placement}_{group_index}"
        scope_labels = (group_label,)
        scope_key = ((layer.placement, group_index),)
        group_name = layer.placement
        physical_node_ordinal = node_ordinal
    else:
        group_name = layer.placement
        if is_shared_gpu_node:
            placement_scope = layer.placement
            physical_node_ordinal = topology_config.physical_node_ordinal(
                layer.placement,
                group_index,
                node_ordinal,
            )
            scope_names = topology_config.scope_names_for_scope(layer.placement)
            scope_indexes = topology_config.scope_indexes_for_ordinal(
                layer.placement,
                physical_node_ordinal,
            )
            scope_labels = topology_config.scope_labels_for_ordinal(
                layer.placement,
                physical_node_ordinal,
            )
            scope_key = topology_config.scope_key_for_ordinal(
                layer.placement,
                physical_node_ordinal,
            )
            group_label = scope_labels[-1]
            graph_node_id = build_global_node_id(layer.name, physical_node_ordinal)
        else:
            placement_scope = layer.placement
            physical_node_ordinal = node_ordinal
            scope_start_ordinal = topology_config.physical_node_ordinal(
                layer.placement,
                group_index,
                1,
            )
            scope_names = topology_config.scope_names_for_scope(layer.placement)
            scope_indexes = topology_config.scope_indexes_for_ordinal(
                layer.placement,
                scope_start_ordinal,
            )
            scope_labels = topology_config.scope_labels_for_ordinal(
                layer.placement,
                scope_start_ordinal,
            )
            scope_key = topology_config.scope_key_for_ordinal(
                layer.placement,
                scope_start_ordinal,
            )
            group_label = scope_labels[-1]
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
        placement_scope=placement_scope,
        scope_names=scope_names,
        scope_indexes=scope_indexes,
        scope_labels=scope_labels,
        scope_key=scope_key,
        group_name=group_name,
        group_index=group_index,
        group_label=group_label,
        node_ordinal=node_ordinal,
        physical_node_ordinal=physical_node_ordinal,
        port_pools=layer.port_pools,
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


def _scope_keys_for_layer(
    topology_config: TopologyConfig,
    layer: LayerConfig,
    fabric_name: str | None,
    single_group_indexes: tuple[int, ...],
) -> tuple[tuple[tuple[str, int], ...], ...]:
    if layer.placement == "global":
        return ()
    if fabric_name is None:
        return tuple(((layer.placement, group_index),) for group_index in single_group_indexes)
    return tuple(
        topology_config.scope_key_for_ordinal(
            layer.placement,
            topology_config.physical_node_ordinal(layer.placement, group_index, 1),
        )
        for group_index in range(1, topology_config.scope_instance_count(layer.placement) + 1)
    )


def _full_mesh_link_bundles(
    source_nodes: list[ExpandedNode],
    target_nodes: list[ExpandedNode],
    fabric_name: str | None,
    port_pool: str,
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
            port_pool=port_pool,
            num_cables=num_cables,
            cable_bandwidth_gb=cable_bandwidth_gb,
            source_lane_units_per_cable=source_lane_units_per_cable,
            target_lane_units_per_cable=target_lane_units_per_cable,
        )
        for source in source_nodes
        for target in target_nodes
    ]
