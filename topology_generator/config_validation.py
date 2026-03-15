from __future__ import annotations

from collections.abc import Sequence

from topology_generator.config_identifiers import (
    GPU_NODES_LAYER_NAME,
    MULTI_FABRIC_GROUP_PLACEMENT,
    SUPPORTED_LINK_POLICIES,
    build_fabric_qualified_node_id,
    build_global_node_id,
    build_group_label_node_id,
    build_grouped_node_id,
    normalize_identifier,
)
from topology_generator.config_types import (
    FabricConfig,
    GroupConfig,
    GroupingConfig,
    InvalidTopologyConfig,
    LayerConfig,
    LinkConfig,
    TopologyConfig,
)


def validate_topology_config(config: TopologyConfig) -> None:
    if len(config.groups) > 1:
        raise InvalidTopologyConfig(
            "Only one repeated group definition is supported in v1."
        )

    _validate_name_uniqueness(config.groups, "Group")
    _validate_reserved_names(config)

    if config.is_multi_fabric:
        _validate_multi_fabric_semantics(config)
        return

    _validate_name_uniqueness(config.layers, "Layer")
    _validate_layer_placements(config, config.layers, "layers")
    _validate_expanded_node_id_uniqueness(config, config.layers)
    _validate_links(config, config.layers, config.links, "links")


def _validate_reserved_names(config: TopologyConfig) -> None:
    for group in config.groups:
        if normalize_identifier(group.name) == "global":
            raise InvalidTopologyConfig(
                f"groups[{group.index}].name uses reserved placement name 'global'."
            )


def _validate_multi_fabric_semantics(config: TopologyConfig) -> None:
    if config.gpu_nodes is None:
        raise InvalidTopologyConfig(
            "gpu_nodes is required when using multi-fabric configuration."
        )
    if not config.fabrics:
        raise InvalidTopologyConfig(
            "fabrics must contain at least one fabric in multi-fabric mode."
        )
    _validate_fabric_name_uniqueness(config.fabrics)
    if config.groupings:
        _validate_grouping_name_uniqueness(config.groupings)
        _validate_grouping_reserved_names(config)
        _validate_grouping_sizes(config)
    elif any(fabric.grouping is not None for fabric in config.fabrics):
        raise InvalidTopologyConfig(
            "fabrics[*].grouping requires at least one declared grouping."
        )
    _validate_gpu_nodes_fabric_mappings(config)

    for fabric in config.fabrics:
        if fabric.grouping is None:
            if any(layer.placement != "global" for layer in fabric.layers):
                raise InvalidTopologyConfig(
                    f"fabrics[{fabric.index}].grouping is required when a fabric "
                    "contains grouped layers."
                )
        else:
            try:
                config.grouping(fabric.grouping)
            except KeyError as exc:
                raise InvalidTopologyConfig(
                    f"fabrics[{fabric.index}].grouping references unknown grouping "
                    f"{fabric.grouping!r}."
                ) from exc

        if (
            fabric.grouping is None
            and config.gpu_nodes_layer_for_fabric(fabric.name).placement != "global"
        ):
            raise InvalidTopologyConfig(
                f"fabrics[{fabric.index}] resolved an invalid shared endpoint placement."
            )

        _validate_name_uniqueness(
            fabric.layers,
            f"Fabric {fabric.name!r} layer",
        )
        for layer in fabric.layers:
            if normalize_identifier(layer.name) == GPU_NODES_LAYER_NAME:
                raise InvalidTopologyConfig(
                    f"fabrics[{fabric.index}].layers[{layer.index - 1}].name "
                    f"must not redefine {GPU_NODES_LAYER_NAME!r}."
                )

        _validate_layer_placements(
            config,
            fabric.layers,
            f"fabrics[{fabric.index}].layers",
            is_multi_fabric_layers=True,
        )
        effective_layers = (config.gpu_nodes_layer_for_fabric(fabric.name), *fabric.layers)
        _validate_expanded_node_id_uniqueness(
            config,
            effective_layers,
            fabric_name=fabric.name,
            grouping_name=fabric.grouping,
        )
        _validate_links(
            config,
            effective_layers,
            fabric.links,
            f"fabrics[{fabric.index}].links",
        )


def _validate_grouping_reserved_names(config: TopologyConfig) -> None:
    reserved_names = {"global", MULTI_FABRIC_GROUP_PLACEMENT, GPU_NODES_LAYER_NAME}
    for grouping in config.groupings:
        normalized_name = normalize_identifier(grouping.name)
        if normalized_name in reserved_names:
            raise InvalidTopologyConfig(
                "groupings names must not use reserved placement names "
                f"{sorted(reserved_names)!r}."
            )


def _validate_grouping_sizes(config: TopologyConfig) -> None:
    assert config.gpu_nodes is not None
    members_per_group_values = [grouping.members_per_group for grouping in config.groupings]
    if len(members_per_group_values) != len(set(members_per_group_values)):
        raise InvalidTopologyConfig(
            "groupings members_per_group values must be unique."
        )

    for grouping in config.groupings:
        if config.gpu_nodes.total_nodes % grouping.members_per_group != 0:
            raise InvalidTopologyConfig(
                f"groupings[{grouping.index}].members_per_group must divide "
                "gpu_nodes.total_nodes exactly."
            )

    sorted_groupings = sorted(
        config.groupings,
        key=lambda item: item.members_per_group,
        reverse=True,
    )
    for larger, smaller in zip(sorted_groupings[:-1], sorted_groupings[1:]):
        if larger.members_per_group % smaller.members_per_group != 0:
            raise InvalidTopologyConfig(
                "groupings must form a clean nesting chain by divisibility."
            )


def _validate_gpu_nodes_fabric_mappings(config: TopologyConfig) -> None:
    assert config.gpu_nodes is not None
    port_layout_names = config.gpu_nodes.fabric_names
    normalized_port_layout_names = {
        normalize_identifier(name): name for name in port_layout_names
    }
    normalized_fabric_names = {
        normalize_identifier(fabric.name): fabric.name for fabric in config.fabrics
    }

    missing = sorted(
        name
        for normalized_name, name in normalized_fabric_names.items()
        if normalized_name not in normalized_port_layout_names
    )
    extra = sorted(
        name
        for normalized_name, name in normalized_port_layout_names.items()
        if normalized_name not in normalized_fabric_names
    )
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing fabric_port_layouts for {missing!r}")
        if extra:
            details.append(f"unexpected fabric_port_layouts entries {extra!r}")
        raise InvalidTopologyConfig(
            "gpu_nodes.fabric_port_layouts must match fabrics by name after "
            f"normalization: {', '.join(details)}."
        )


def _validate_layer_placements(
    config: TopologyConfig,
    layers: Sequence[LayerConfig],
    path_prefix: str,
    is_multi_fabric_layers: bool = False,
) -> None:
    if is_multi_fabric_layers:
        available_placements = {"global", MULTI_FABRIC_GROUP_PLACEMENT}
    else:
        group_names = [group.name for group in config.groups]
        available_placements = {"global", *group_names}

    for layer in layers:
        if layer.placement not in available_placements:
            if is_multi_fabric_layers:
                raise InvalidTopologyConfig(
                    f"{_layer_path(path_prefix, layer, True)}.placement must be "
                    "'global' or 'group' in multi-fabric mode; use "
                    "'placement: group' for grouping-relative layers."
                )
            raise InvalidTopologyConfig(
                f"{_layer_path(path_prefix, layer, False)}.placement must be "
                "'global' or one of the declared groups: "
                f"{sorted(name for name in available_placements if name != 'global')!r}."
            )


def _validate_links(
    config: TopologyConfig,
    layers: Sequence[LayerConfig],
    links: Sequence[LinkConfig],
    path_prefix: str,
) -> None:
    layer_name_to_index = {layer.name: layer.index for layer in layers}
    seen_layer_pairs: set[tuple[str, str]] = set()

    for link in links:
        layer_pair = (link.from_layer, link.to_layer)
        if layer_pair in seen_layer_pairs:
            raise InvalidTopologyConfig(
                "Each adjacent layer pair may only be linked once: "
                f"{link.from_layer!r} -> {link.to_layer!r}."
            )
        seen_layer_pairs.add(layer_pair)

        if link.from_layer not in layer_name_to_index:
            raise InvalidTopologyConfig(
                f"{path_prefix}[{link.index}].from references unknown layer "
                f"{link.from_layer!r}."
            )
        if link.to_layer not in layer_name_to_index:
            raise InvalidTopologyConfig(
                f"{path_prefix}[{link.index}].to references unknown layer "
                f"{link.to_layer!r}."
            )

        lower_index = layer_name_to_index[link.from_layer]
        upper_index = layer_name_to_index[link.to_layer]
        if upper_index != lower_index + 1:
            raise InvalidTopologyConfig(
                "Links are only allowed between adjacent layers in order: "
                f"{path_prefix}[{link.index}] connects {link.from_layer!r} to "
                f"{link.to_layer!r}."
            )

        lower_layer = next(layer for layer in layers if layer.index == lower_index)
        upper_layer = next(layer for layer in layers if layer.index == upper_index)
        _validate_link_policy(link, lower_layer, upper_layer, path_prefix)
        _validate_link_bandwidth_support(link, lower_layer, upper_layer, path_prefix)


def _validate_link_policy(
    link: LinkConfig,
    lower_layer: LayerConfig,
    upper_layer: LayerConfig,
    path_prefix: str,
) -> None:
    if link.policy == "within_group_full_mesh":
        if lower_layer.placement == "global" or upper_layer.placement == "global":
            raise InvalidTopologyConfig(
                "within_group_full_mesh requires both layers to use the same "
                f"non-global placement: {path_prefix}[{link.index}]."
            )
        if lower_layer.placement != upper_layer.placement:
            raise InvalidTopologyConfig(
                "within_group_full_mesh requires both layers to share the same "
                f"placement: {path_prefix}[{link.index}]."
            )
        return

    if link.policy == "group_to_global_full_mesh":
        if lower_layer.placement == "global" or upper_layer.placement != "global":
            raise InvalidTopologyConfig(
                "group_to_global_full_mesh requires a grouped source layer and a "
                f"global target layer: {path_prefix}[{link.index}]."
            )
        return

    if link.policy == "global_to_global_full_mesh":
        if lower_layer.placement != "global" or upper_layer.placement != "global":
            raise InvalidTopologyConfig(
                "global_to_global_full_mesh requires both layers to use global "
                f"placement: {path_prefix}[{link.index}]."
            )
        return

    raise InvalidTopologyConfig(
        f"{path_prefix}[{link.index}].policy must be one of "
        f"{sorted(SUPPORTED_LINK_POLICIES)!r}."
    )


def _validate_link_bandwidth_support(
    link: LinkConfig,
    lower_layer: LayerConfig,
    upper_layer: LayerConfig,
    path_prefix: str,
) -> None:
    for layer in (lower_layer, upper_layer):
        if layer.lane_units_for_bandwidth(link.cable_bandwidth_gb) is None:
            raise InvalidTopologyConfig(
                f"{path_prefix}[{link.index}].cable_bandwidth_gb "
                f"{link.cable_bandwidth_gb:g} GB/s is not supported by layer "
                f"{layer.name!r}; supported port bandwidths are "
                f"{list(layer.supported_port_bandwidths_gb)!r}."
            )


def _validate_expanded_node_id_uniqueness(
    config: TopologyConfig,
    layers: Sequence[LayerConfig],
    fabric_name: str | None = None,
    grouping_name: str | None = None,
) -> None:
    seen_node_ids: dict[str, str] = {}
    group = config.group()
    single_fabric_group_indexes = range(1, group.count + 1) if group else ()
    multi_fabric_group_indexes = (
        range(1, config.grouping_count(grouping_name) + 1)
        if grouping_name is not None
        else range(0)
    )

    for layer in layers:
        if layer.placement == "global":
            node_ids = tuple(
                build_global_node_id(layer.name, ordinal)
                for ordinal in range(1, layer.nodes_per_group + 1)
            )
        elif fabric_name is None:
            node_ids = tuple(
                build_grouped_node_id(layer.placement, group_index, layer.name, ordinal)
                for group_index in single_fabric_group_indexes
                for ordinal in range(1, layer.nodes_per_group + 1)
            )
        else:
            assert grouping_name is not None
            node_ids_list: list[str] = []
            for group_index in multi_fabric_group_indexes:
                if layer.name == GPU_NODES_LAYER_NAME:
                    for local_ordinal in range(1, layer.nodes_per_group + 1):
                        physical_ordinal = config.physical_node_ordinal(
                            grouping_name,
                            group_index,
                            local_ordinal,
                        )
                        node_ids_list.append(
                            build_fabric_qualified_node_id(
                                fabric_name,
                                build_global_node_id(layer.name, physical_ordinal),
                            )
                        )
                    continue

                group_label = config.group_label_for_group(grouping_name, group_index)
                for ordinal in range(1, layer.nodes_per_group + 1):
                    node_ids_list.append(
                        build_fabric_qualified_node_id(
                            fabric_name,
                            build_group_label_node_id(group_label, layer.name, ordinal),
                        )
                    )
            node_ids = tuple(node_ids_list)

        for node_id in node_ids:
            existing_layer = seen_node_ids.get(node_id)
            if existing_layer is not None:
                raise InvalidTopologyConfig(
                    "Expanded node IDs must be unique after normalization; "
                    f"layers {existing_layer!r} and {layer.name!r} both produce "
                    f"{node_id!r}."
                )
            seen_node_ids[node_id] = layer.name


def _validate_name_uniqueness(
    items: Sequence[GroupConfig] | Sequence[LayerConfig],
    label: str,
) -> None:
    _validate_identifier_uniqueness([item.name for item in items], f"{label} names")


def _validate_grouping_name_uniqueness(items: Sequence[GroupingConfig]) -> None:
    _validate_identifier_uniqueness([item.name for item in items], "Grouping names")


def _validate_fabric_name_uniqueness(items: Sequence[FabricConfig]) -> None:
    _validate_identifier_uniqueness([item.name for item in items], "Fabric names")


def _validate_identifier_uniqueness(names: Sequence[str], label: str) -> None:
    if len(names) != len(set(names)):
        raise InvalidTopologyConfig(f"{label} must be unique.")

    normalized_names = [normalize_identifier(name) for name in names]
    if any(not normalized_name for normalized_name in normalized_names):
        raise InvalidTopologyConfig(
            f"{label} must contain at least one alphanumeric character."
        )
    if len(normalized_names) != len(set(normalized_names)):
        raise InvalidTopologyConfig(
            f"{label} must remain unique after identifier normalization."
        )


def _layer_path(path_prefix: str, layer: LayerConfig, is_multi_fabric: bool) -> str:
    if not is_multi_fabric:
        return f"{path_prefix}[{layer.index}]"
    return f"{path_prefix}[{layer.index - 1}]"
