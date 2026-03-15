from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from topology_generator.config_identifiers import (
    LEGACY_LAYER_PORT_KEYS,
    SUPPORTED_LINK_POLICIES,
    bandwidth_decimal,
    normalize_identifier,
)
from topology_generator.config_types import (
    FabricConfig,
    FabricPortLayoutConfig,
    GpuNodesConfig,
    GroupConfig,
    GroupingConfig,
    InvalidTopologyConfig,
    LayerConfig,
    LinkConfig,
    PortLayoutConfig,
    PortModeConfig,
    TopologyConfig,
)


def parse_topology_config(raw_config: Mapping[str, Any] | Any) -> TopologyConfig:
    if raw_config is None:
        raise InvalidTopologyConfig("Configuration must be a non-empty mapping.")
    if not isinstance(raw_config, Mapping):
        raise InvalidTopologyConfig("Configuration must be a mapping.")

    raw_groups = raw_config.get("groups", [])
    groups = _parse_groups(raw_groups)
    has_groupings = "groupings" in raw_config
    has_legacy_shape = "layers" in raw_config or "links" in raw_config
    has_multi_fabric_shape = "gpu_nodes" in raw_config or "fabrics" in raw_config

    if has_legacy_shape and has_multi_fabric_shape:
        raise InvalidTopologyConfig(
            "Configuration cannot mix legacy 'layers'/'links' fields with "
            "multi-fabric 'gpu_nodes'/'fabrics' fields."
        )

    if has_groupings and not has_multi_fabric_shape:
        raise InvalidTopologyConfig(
            "groupings is only supported in multi-fabric configuration."
        )

    if has_multi_fabric_shape:
        if groups:
            raise InvalidTopologyConfig(
                "Multi-fabric configuration must declare top-level 'groupings'; "
                "use 'groupings' instead of 'groups' in multi-fabric mode."
            )
        if not has_groupings:
            raise InvalidTopologyConfig(
                "Multi-fabric configuration must declare top-level 'groupings'."
            )

        config = TopologyConfig(
            groups=groups,
            groupings=_parse_groupings(raw_config.get("groupings", [])),
            layers=(),
            links=(),
            fabrics=_parse_fabrics(raw_config.get("fabrics")),
            gpu_nodes=_parse_gpu_nodes(raw_config.get("gpu_nodes")),
        )
    else:
        raw_layers = raw_config.get("layers")
        if not isinstance(raw_layers, Sequence) or isinstance(raw_layers, (str, bytes)):
            raise InvalidTopologyConfig("layers must be a list of layer mappings.")
        if len(raw_layers) < 2:
            raise InvalidTopologyConfig("Topology must contain at least 2 layers.")

        raw_links = raw_config.get("links")
        if not isinstance(raw_links, Sequence) or isinstance(raw_links, (str, bytes)):
            raise InvalidTopologyConfig("links must be a list of link mappings.")

        config = TopologyConfig(
            groups=groups,
            groupings=(),
            layers=tuple(
                _parse_layer(raw_layer, index, f"layers[{index}]")
                for index, raw_layer in enumerate(raw_layers)
            ),
            links=tuple(
                _parse_link(raw_link, index, f"links[{index}]")
                for index, raw_link in enumerate(raw_links)
            ),
        )

    config._validate_semantics()
    return config


def _parse_groups(raw_groups: Any) -> tuple[GroupConfig, ...]:
    if not isinstance(raw_groups, Sequence) or isinstance(raw_groups, (str, bytes)):
        raise InvalidTopologyConfig("groups must be a list of group mappings.")

    return tuple(
        GroupConfig(
            index=index,
            name=_required_name(raw_group, f"groups[{index}]"),
            count=_require_positive_int(raw_group, "count", f"groups[{index}]"),
        )
        for index, raw_group in enumerate(raw_groups)
    )


def _parse_groupings(raw_groupings: Any) -> tuple[GroupingConfig, ...]:
    if not isinstance(raw_groupings, Sequence) or isinstance(raw_groupings, (str, bytes)):
        raise InvalidTopologyConfig("groupings must be a list of grouping mappings.")
    if not raw_groupings:
        raise InvalidTopologyConfig("groupings must contain at least one grouping.")

    return tuple(
        GroupingConfig(
            index=index,
            name=_required_name(raw_grouping, f"groupings[{index}]"),
            members_per_group=_require_positive_int(
                raw_grouping,
                "members_per_group",
                f"groupings[{index}]",
            ),
        )
        for index, raw_grouping in enumerate(raw_groupings)
    )


def _parse_gpu_nodes(raw_gpu_nodes: Any) -> GpuNodesConfig:
    path = "gpu_nodes"
    if not isinstance(raw_gpu_nodes, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")
    if "nodes_per_group" in raw_gpu_nodes:
        raise InvalidTopologyConfig(
            f"{path}.nodes_per_group is no longer supported; use {path}.total_nodes "
            "and top-level groupings[*].members_per_group instead."
        )

    raw_fabric_port_layouts = raw_gpu_nodes.get("fabric_port_layouts")
    if not isinstance(raw_fabric_port_layouts, Mapping) or not raw_fabric_port_layouts:
        raise InvalidTopologyConfig(f"{path}.fabric_port_layouts must be a non-empty mapping.")

    fabric_port_layout_names = list(raw_fabric_port_layouts)
    if not all(isinstance(name, str) and name.strip() for name in fabric_port_layout_names):
        raise InvalidTopologyConfig(
            f"{path}.fabric_port_layouts keys must be non-empty strings."
        )
    _validate_identifier_uniqueness(
        [str(name).strip() for name in fabric_port_layout_names],
        f"{path}.fabric_port_layouts keys",
    )

    fabric_port_layouts = tuple(
        FabricPortLayoutConfig(
            name=str(fabric_name).strip(),
            port_layout=_parse_port_layout(
                raw_port_layout,
                f"{path}.fabric_port_layouts[{fabric_name!r}]",
            ),
        )
        for fabric_name, raw_port_layout in raw_fabric_port_layouts.items()
    )

    return GpuNodesConfig(
        total_nodes=_require_positive_int(raw_gpu_nodes, "total_nodes", path),
        fabric_port_layouts=fabric_port_layouts,
    )


def _parse_fabrics(raw_fabrics: Any) -> tuple[FabricConfig, ...]:
    if not isinstance(raw_fabrics, Sequence) or isinstance(raw_fabrics, (str, bytes)):
        raise InvalidTopologyConfig("fabrics must be a list of fabric mappings.")

    return tuple(_parse_fabric(raw_fabric, index) for index, raw_fabric in enumerate(raw_fabrics))


def _parse_fabric(raw_fabric: Any, index: int) -> FabricConfig:
    path = f"fabrics[{index}]"
    if not isinstance(raw_fabric, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")

    raw_layers = raw_fabric.get("layers")
    if not isinstance(raw_layers, Sequence) or isinstance(raw_layers, (str, bytes)):
        raise InvalidTopologyConfig(f"{path}.layers must be a list of layer mappings.")
    if len(raw_layers) < 1:
        raise InvalidTopologyConfig(f"{path}.layers must contain at least 1 layer.")

    raw_links = raw_fabric.get("links")
    if not isinstance(raw_links, Sequence) or isinstance(raw_links, (str, bytes)):
        raise InvalidTopologyConfig(f"{path}.links must be a list of link mappings.")

    grouping = raw_fabric.get("grouping")
    if not isinstance(grouping, str) or not grouping.strip():
        raise InvalidTopologyConfig(
            f"{path}.grouping is required in multi-fabric configs; declare a top-level "
            "groupings entry and reference it here."
        )

    return FabricConfig(
        index=index,
        name=_required_name(raw_fabric, path),
        grouping=grouping.strip(),
        layers=tuple(
            _parse_layer(
                raw_layer,
                layer_index + 1,
                f"{path}.layers[{layer_index}]",
            )
            for layer_index, raw_layer in enumerate(raw_layers)
        ),
        links=tuple(
            _parse_link(raw_link, link_index, f"{path}.links[{link_index}]")
            for link_index, raw_link in enumerate(raw_links)
        ),
    )


def _parse_layer(raw_layer: Any, index: int, path: str) -> LayerConfig:
    if not isinstance(raw_layer, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")

    legacy_keys = sorted(LEGACY_LAYER_PORT_KEYS & set(raw_layer))
    if legacy_keys:
        raise InvalidTopologyConfig(
            f"{path} uses legacy port fields {legacy_keys!r}; replace them with a "
            "port_layout block."
        )

    return LayerConfig(
        index=index,
        name=_required_name(raw_layer, path),
        placement=_required_string(raw_layer, "placement", path),
        nodes_per_group=_require_positive_int(raw_layer, "nodes_per_group", path),
        port_layout=_parse_port_layout(raw_layer.get("port_layout"), f"{path}.port_layout"),
    )


def _parse_port_layout(raw_port_layout: Any, path: str) -> PortLayoutConfig:
    if not isinstance(raw_port_layout, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")

    base_lane_bandwidth_gb = _require_positive_number(
        raw_port_layout,
        "base_lane_bandwidth_gb",
        path,
    )
    total_lane_units = _require_positive_int(raw_port_layout, "total_lane_units", path)
    raw_supported_modes = raw_port_layout.get("supported_port_modes")
    if not isinstance(raw_supported_modes, Sequence) or isinstance(
        raw_supported_modes, (str, bytes)
    ):
        raise InvalidTopologyConfig(f"{path}.supported_port_modes must be a list.")
    if not raw_supported_modes:
        raise InvalidTopologyConfig(f"{path}.supported_port_modes must not be empty.")

    supported_modes = tuple(
        _parse_port_mode(raw_mode, path, mode_index)
        for mode_index, raw_mode in enumerate(raw_supported_modes)
    )

    seen_bandwidths: set[Decimal] = set()
    seen_lane_units: set[int] = set()
    for mode in supported_modes:
        normalized_bandwidth = bandwidth_decimal(mode.port_bandwidth_gb)
        if normalized_bandwidth in seen_bandwidths:
            raise InvalidTopologyConfig(
                f"{path}.supported_port_modes contains duplicate port_bandwidth_gb "
                f"{mode.port_bandwidth_gb:g}."
            )
        if mode.lane_units in seen_lane_units:
            raise InvalidTopologyConfig(
                f"{path}.supported_port_modes contains duplicate lane_units "
                f"{mode.lane_units}."
            )
        expected_bandwidth = bandwidth_decimal(base_lane_bandwidth_gb) * mode.lane_units
        if bandwidth_decimal(mode.port_bandwidth_gb) != expected_bandwidth:
            raise InvalidTopologyConfig(
                f"{path}.supported_port_modes[{mode.index}] must satisfy "
                "port_bandwidth_gb == base_lane_bandwidth_gb * lane_units."
            )
        if mode.lane_units > total_lane_units:
            raise InvalidTopologyConfig(
                f"{path}.supported_port_modes[{mode.index}].lane_units must be less "
                "than or equal to total_lane_units."
            )
        seen_bandwidths.add(normalized_bandwidth)
        seen_lane_units.add(mode.lane_units)

    return PortLayoutConfig(
        base_lane_bandwidth_gb=base_lane_bandwidth_gb,
        total_lane_units=total_lane_units,
        supported_port_modes=supported_modes,
    )


def _parse_port_mode(
    raw_port_mode: Any,
    port_layout_path: str,
    mode_index: int,
) -> PortModeConfig:
    path = f"{port_layout_path}.supported_port_modes[{mode_index}]"
    if not isinstance(raw_port_mode, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")

    return PortModeConfig(
        index=mode_index,
        port_bandwidth_gb=_require_positive_number(
            raw_port_mode,
            "port_bandwidth_gb",
            path,
        ),
        lane_units=_require_positive_int(raw_port_mode, "lane_units", path),
    )


def _parse_link(raw_link: Any, index: int, path: str) -> LinkConfig:
    if not isinstance(raw_link, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")

    cables_per_pair = _require_non_negative_int(raw_link, "cables_per_pair", path)
    cable_bandwidth_gb = _require_non_negative_number(
        raw_link,
        "cable_bandwidth_gb",
        path,
    )
    if cables_per_pair > 0 and cable_bandwidth_gb <= 0:
        raise InvalidTopologyConfig(
            f"{path}.cable_bandwidth_gb must be greater than zero when "
            "cables_per_pair is greater than zero."
        )
    if cables_per_pair == 0 and cable_bandwidth_gb != 0:
        raise InvalidTopologyConfig(
            f"{path}.cable_bandwidth_gb must be zero when cables_per_pair is zero."
        )

    policy = _required_string(raw_link, "policy", path)
    if policy not in SUPPORTED_LINK_POLICIES:
        raise InvalidTopologyConfig(
            f"{path}.policy must be one of {sorted(SUPPORTED_LINK_POLICIES)!r}."
        )

    return LinkConfig(
        index=index,
        from_layer=_required_string(raw_link, "from", path),
        to_layer=_required_string(raw_link, "to", path),
        policy=policy,
        cables_per_pair=cables_per_pair,
        cable_bandwidth_gb=cable_bandwidth_gb,
    )


def _required_name(config: Any, path: str) -> str:
    value = _required_string(config, "name", path)
    if not normalize_identifier(value):
        raise InvalidTopologyConfig(
            f"{path}.name must contain at least one alphanumeric character."
        )
    return value


def _required_string(config: Any, key: str, path: str) -> str:
    if not isinstance(config, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidTopologyConfig(f"{path}.{key} must be a non-empty string.")
    return value.strip()


def _require_positive_int(config: Mapping[str, Any], key: str, path: str) -> int:
    value = _require_non_negative_int(config, key, path)
    if value <= 0:
        raise InvalidTopologyConfig(f"{path}.{key} must be greater than zero.")
    return value


def _require_non_negative_int(config: Mapping[str, Any], key: str, path: str) -> int:
    value = config.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidTopologyConfig(f"{path}.{key} must be an integer.")
    if value < 0:
        raise InvalidTopologyConfig(f"{path}.{key} must be greater than or equal to zero.")
    return value


def _require_positive_number(config: Mapping[str, Any], key: str, path: str) -> float:
    value = _require_non_negative_number(config, key, path)
    if value <= 0:
        raise InvalidTopologyConfig(f"{path}.{key} must be greater than zero.")
    return value


def _require_non_negative_number(config: Mapping[str, Any], key: str, path: str) -> float:
    value = config.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InvalidTopologyConfig(f"{path}.{key} must be a number.")
    if value < 0:
        raise InvalidTopologyConfig(f"{path}.{key} must be greater than or equal to zero.")
    return float(value)


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
