from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


SUPPORTED_LINK_POLICIES = {
    "within_group_full_mesh",
    "group_to_global_full_mesh",
    "global_to_global_full_mesh",
}

LEGACY_LAYER_PORT_KEYS = {
    "ports_per_node",
    "port_bandwidth_gb_per_port",
}

GPU_NODES_LAYER_NAME = "gpu_nodes"
DEFAULT_SINGLE_FABRIC_NAME = "default"
MULTI_FABRIC_GROUP_PLACEMENT = "group"


class InvalidTopologyConfig(ValueError):
    """Raised when the supplied topology configuration is invalid."""


def bandwidth_decimal(value: float) -> Decimal:
    """Convert a numeric bandwidth into a stable decimal representation."""
    return Decimal(str(value)).normalize()


def bandwidths_equal(left: float, right: float) -> bool:
    """Compare bandwidth values without relying on exact binary float equality."""
    return bandwidth_decimal(left) == bandwidth_decimal(right) or math.isclose(
        left,
        right,
        rel_tol=1e-9,
        abs_tol=1e-12,
    )


def normalize_identifier(name: str) -> str:
    """Normalize YAML labels into stable identifiers for groups, fabrics, and nodes."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def build_grouped_node_id(
    group_name: str,
    group_index: int,
    layer_name: str,
    node_ordinal: int,
) -> str:
    """Build a stable node ID for a single-fabric grouped layer instance."""
    return (
        f"{normalize_identifier(group_name)}_{group_index}_"
        f"{normalize_identifier(layer_name)}_{node_ordinal}"
    )


def build_group_label_node_id(
    group_label: str,
    layer_name: str,
    node_ordinal: int,
) -> str:
    """Build a stable node ID for a resolved grouping label."""
    return (
        f"{normalize_identifier(group_label)}_"
        f"{normalize_identifier(layer_name)}_{node_ordinal}"
    )


def build_global_node_id(layer_name: str, node_ordinal: int) -> str:
    """Build a stable node ID for a global layer instance."""
    return f"{normalize_identifier(layer_name)}_{node_ordinal}"


def build_fabric_qualified_node_id(fabric_name: str, node_id: str) -> str:
    """Build a fabric-qualified node ID that cannot collide across fabrics."""
    return f"{normalize_identifier(fabric_name)}__{node_id}"


@dataclass(frozen=True)
class GroupConfig:
    index: int
    name: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
        }


@dataclass(frozen=True)
class GroupingConfig:
    index: int
    name: str
    members_per_group: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "members_per_group": self.members_per_group,
        }


@dataclass(frozen=True)
class PortModeConfig:
    index: int
    port_bandwidth_gb: float
    lane_units: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "port_bandwidth_gb": self.port_bandwidth_gb,
            "lane_units": self.lane_units,
        }


@dataclass(frozen=True)
class PortLayoutConfig:
    base_lane_bandwidth_gb: float
    total_lane_units: int
    supported_port_modes: tuple[PortModeConfig, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_lane_bandwidth_gb": self.base_lane_bandwidth_gb,
            "total_lane_units": self.total_lane_units,
            "supported_port_modes": [
                mode.to_dict() for mode in self.supported_port_modes
            ],
        }

    @property
    def supported_port_bandwidths_gb(self) -> tuple[float, ...]:
        return tuple(mode.port_bandwidth_gb for mode in self.supported_port_modes)

    def lane_units_for_bandwidth(self, bandwidth_gb: float) -> int | None:
        for mode in self.supported_port_modes:
            if bandwidths_equal(mode.port_bandwidth_gb, bandwidth_gb):
                return mode.lane_units
        return None


@dataclass(frozen=True)
class LayerConfig:
    index: int
    name: str
    placement: str
    nodes_per_group: int
    port_layout: PortLayoutConfig

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "placement": self.placement,
            "nodes_per_group": self.nodes_per_group,
            "port_layout": self.port_layout.to_dict(),
        }

    @property
    def total_lane_units(self) -> int:
        return self.port_layout.total_lane_units

    @property
    def supported_port_bandwidths_gb(self) -> tuple[float, ...]:
        return self.port_layout.supported_port_bandwidths_gb

    def lane_units_for_bandwidth(self, bandwidth_gb: float) -> int | None:
        return self.port_layout.lane_units_for_bandwidth(bandwidth_gb)


@dataclass(frozen=True)
class LinkConfig:
    index: int
    from_layer: str
    to_layer: str
    policy: str
    cables_per_pair: int
    cable_bandwidth_gb: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_layer,
            "to": self.to_layer,
            "policy": self.policy,
            "cables_per_pair": self.cables_per_pair,
            "cable_bandwidth_gb": self.cable_bandwidth_gb,
        }


@dataclass(frozen=True)
class FabricConfig:
    index: int
    name: str
    grouping: str | None
    layers: tuple[LayerConfig, ...]
    links: tuple[LinkConfig, ...]

    def to_dict(self) -> dict[str, Any]:
        data = {
            "name": self.name,
            "layers": [layer.to_dict() for layer in self.layers],
            "links": [link.to_dict() for link in self.links],
        }
        if self.grouping is not None:
            data["grouping"] = self.grouping
        return data


@dataclass(frozen=True)
class FabricPortLayoutConfig:
    name: str
    port_layout: PortLayoutConfig

    def to_dict(self) -> dict[str, Any]:
        return self.port_layout.to_dict()


@dataclass(frozen=True)
class GpuNodesConfig:
    total_nodes: int
    fabric_port_layouts: tuple[FabricPortLayoutConfig, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_nodes": self.total_nodes,
            "fabric_port_layouts": {
                fabric_port_layout.name: fabric_port_layout.to_dict()
                for fabric_port_layout in self.fabric_port_layouts
            },
        }

    def port_layout_for_fabric(self, fabric_name: str) -> PortLayoutConfig:
        normalized_fabric_name = normalize_identifier(fabric_name)
        for fabric_port_layout in self.fabric_port_layouts:
            if normalize_identifier(fabric_port_layout.name) == normalized_fabric_name:
                return fabric_port_layout.port_layout
        raise InvalidTopologyConfig(
            "gpu_nodes.fabric_port_layouts must define an entry for fabric "
            f"{fabric_name!r}."
        )

    @property
    def fabric_names(self) -> tuple[str, ...]:
        return tuple(fabric_port_layout.name for fabric_port_layout in self.fabric_port_layouts)


@dataclass(frozen=True)
class EffectiveFabricConfig:
    name: str | None
    grouping_name: str | None
    group_count: int | None
    layers: tuple[LayerConfig, ...]
    links: tuple[LinkConfig, ...]

    def layer(self, layer_ref: int | str) -> LayerConfig:
        if isinstance(layer_ref, int):
            return self.layers[layer_ref]

        for layer in self.layers:
            if layer.name == layer_ref:
                return layer
        raise KeyError(layer_ref)

    def group_indexes(self) -> range:
        if self.group_count is None:
            return range(0)
        return range(1, self.group_count + 1)


@dataclass(frozen=True)
class TopologyConfig(Mapping[str, Any]):
    """Validated topology configuration with dict-like compatibility."""

    groups: tuple[GroupConfig, ...]
    groupings: tuple[GroupingConfig, ...]
    layers: tuple[LayerConfig, ...]
    links: tuple[LinkConfig, ...]
    fabrics: tuple[FabricConfig, ...] = ()
    gpu_nodes: GpuNodesConfig | None = None

    @classmethod
    def from_mapping(cls, raw_config: Mapping[str, Any] | Any) -> "TopologyConfig":
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
            if has_groupings and groups:
                raise InvalidTopologyConfig(
                    "Multi-fabric configuration must use either canonical "
                    "'groupings' or legacy 'groups', not both."
                )

            if has_groupings:
                groupings = _parse_groupings(raw_config.get("groupings", []))
                gpu_nodes = _parse_gpu_nodes(raw_config.get("gpu_nodes"))
                fabrics = _parse_fabrics(raw_config.get("fabrics"))
            else:
                gpu_nodes, groupings, fabrics = _parse_legacy_multi_fabric_config(
                    raw_config,
                    groups,
                )
                groups = ()

            config = cls(
                groups=groups,
                groupings=groupings,
                layers=(),
                links=(),
                fabrics=fabrics,
                gpu_nodes=gpu_nodes,
            )
        else:
            raw_layers = raw_config.get("layers")
            if not isinstance(raw_layers, Sequence) or isinstance(
                raw_layers, (str, bytes)
            ):
                raise InvalidTopologyConfig("layers must be a list of layer mappings.")
            if len(raw_layers) < 2:
                raise InvalidTopologyConfig("Topology must contain at least 2 layers.")

            raw_links = raw_config.get("links")
            if not isinstance(raw_links, Sequence) or isinstance(
                raw_links, (str, bytes)
            ):
                raise InvalidTopologyConfig("links must be a list of link mappings.")

            layers = tuple(
                _parse_layer(raw_layer, index, f"layers[{index}]")
                for index, raw_layer in enumerate(raw_layers)
            )
            links = tuple(
                _parse_link(raw_link, index, f"links[{index}]")
                for index, raw_link in enumerate(raw_links)
            )
            config = cls(
                groups=groups,
                groupings=(),
                layers=layers,
                links=links,
            )

        config._validate_semantics()
        return config

    @property
    def is_multi_fabric(self) -> bool:
        return self.gpu_nodes is not None

    @property
    def fabric_names(self) -> tuple[str, ...]:
        if self.is_multi_fabric:
            return tuple(fabric.name for fabric in self.fabrics)
        return ()

    def group(self) -> GroupConfig | None:
        return self.groups[0] if self.groups else None

    def grouping(self, grouping_name: str) -> GroupingConfig:
        normalized_grouping_name = normalize_identifier(grouping_name)
        for grouping in self.groupings:
            if normalize_identifier(grouping.name) == normalized_grouping_name:
                return grouping
        raise KeyError(grouping_name)

    def grouping_count(self, grouping_name: str) -> int:
        if self.gpu_nodes is None:
            raise KeyError(grouping_name)
        return self.gpu_nodes.total_nodes // self.grouping(grouping_name).members_per_group

    def group_label_for_group(self, grouping_name: str, group_index: int) -> str:
        grouping = self.grouping(grouping_name)
        start_ordinal = ((group_index - 1) * grouping.members_per_group) + 1
        return self.group_label_for_ordinal(grouping_name, start_ordinal)

    def group_label_for_ordinal(self, grouping_name: str, physical_ordinal: int) -> str:
        grouping = self.grouping(grouping_name)
        zero_based_ordinal = physical_ordinal - 1
        label_parts: list[str] = []
        previous_group_size: int | None = None
        for ancestor in self._grouping_chain(grouping):
            if previous_group_size is None:
                local_index = (zero_based_ordinal // ancestor.members_per_group) + 1
            else:
                local_index = (
                    (zero_based_ordinal % previous_group_size)
                    // ancestor.members_per_group
                ) + 1
            label_parts.append(f"{ancestor.name}_{local_index}")
            previous_group_size = ancestor.members_per_group
        return "_".join(label_parts)

    def physical_node_ordinal(
        self,
        grouping_name: str,
        group_index: int,
        local_ordinal: int,
    ) -> int:
        grouping = self.grouping(grouping_name)
        return ((group_index - 1) * grouping.members_per_group) + local_ordinal

    def layer(self, layer_ref: int | str) -> LayerConfig:
        if self.is_multi_fabric:
            raise KeyError(layer_ref)
        if isinstance(layer_ref, int):
            return self.layers[layer_ref]

        for layer in self.layers:
            if layer.name == layer_ref:
                return layer
        raise KeyError(layer_ref)

    def fabric(self, fabric_name: str) -> FabricConfig:
        for fabric in self.fabrics:
            if fabric.name == fabric_name:
                return fabric
        raise KeyError(fabric_name)

    def gpu_nodes_layer_for_fabric(self, fabric_name: str) -> LayerConfig:
        if self.gpu_nodes is None:
            raise KeyError(fabric_name)
        fabric = self.fabric(fabric_name)
        if fabric.grouping is None:
            placement = "global"
            nodes_per_group = self.gpu_nodes.total_nodes
        else:
            placement = MULTI_FABRIC_GROUP_PLACEMENT
            nodes_per_group = self.grouping(fabric.grouping).members_per_group
        return LayerConfig(
            index=0,
            name=GPU_NODES_LAYER_NAME,
            placement=placement,
            nodes_per_group=nodes_per_group,
            port_layout=self.gpu_nodes.port_layout_for_fabric(fabric_name),
        )

    def iter_fabrics(self) -> tuple[EffectiveFabricConfig, ...]:
        if not self.is_multi_fabric:
            group = self.group()
            return (
                EffectiveFabricConfig(
                    name=None,
                    grouping_name=None,
                    group_count=group.count if group is not None else None,
                    layers=self.layers,
                    links=self.links,
                ),
            )

        return tuple(
            EffectiveFabricConfig(
                name=fabric.name,
                grouping_name=fabric.grouping,
                group_count=(
                    self.grouping_count(fabric.grouping)
                    if fabric.grouping is not None
                    else None
                ),
                layers=(self.gpu_nodes_layer_for_fabric(fabric.name), *fabric.layers),
                links=fabric.links,
            )
            for fabric in self.fabrics
        )

    def _grouping_chain(self, grouping: GroupingConfig) -> tuple[GroupingConfig, ...]:
        return tuple(
            candidate
            for candidate in sorted(
                self.groupings,
                key=lambda item: item.members_per_group,
                reverse=True,
            )
            if candidate.members_per_group >= grouping.members_per_group
        )

    def _validate_semantics(self) -> None:
        if len(self.groups) > 1:
            raise InvalidTopologyConfig(
                "Only one repeated group definition is supported in v1."
            )

        _validate_name_uniqueness(self.groups, "Group")
        self._validate_reserved_names()

        if self.is_multi_fabric:
            self._validate_multi_fabric_semantics()
            return

        _validate_name_uniqueness(self.layers, "Layer")
        self._validate_layer_placements(self.layers, "layers")
        self._validate_expanded_node_id_uniqueness(self.layers)
        self._validate_links(self.layers, self.links, "links")

    def _validate_reserved_names(self) -> None:
        for group in self.groups:
            if normalize_identifier(group.name) == "global":
                raise InvalidTopologyConfig(
                    f"groups[{group.index}].name uses reserved placement name 'global'."
                )

    def _validate_multi_fabric_semantics(self) -> None:
        if self.gpu_nodes is None:
            raise InvalidTopologyConfig(
                "gpu_nodes is required when using multi-fabric configuration."
            )
        if not self.fabrics:
            raise InvalidTopologyConfig(
                "fabrics must contain at least one fabric in multi-fabric mode."
            )
        _validate_fabric_name_uniqueness(self.fabrics)
        if self.groupings:
            _validate_grouping_name_uniqueness(self.groupings)
            self._validate_grouping_reserved_names()
            self._validate_grouping_sizes()
        elif any(fabric.grouping is not None for fabric in self.fabrics):
            raise InvalidTopologyConfig(
                "fabrics[*].grouping requires at least one declared grouping."
            )
        self._validate_gpu_nodes_fabric_mappings()

        for fabric in self.fabrics:
            if fabric.grouping is None:
                if any(layer.placement != "global" for layer in fabric.layers):
                    raise InvalidTopologyConfig(
                        f"fabrics[{fabric.index}].grouping is required when a fabric "
                        "contains grouped layers."
                    )
            else:
                try:
                    self.grouping(fabric.grouping)
                except KeyError as exc:
                    raise InvalidTopologyConfig(
                        f"fabrics[{fabric.index}].grouping references unknown grouping "
                        f"{fabric.grouping!r}."
                    ) from exc

            if fabric.grouping is None and self.gpu_nodes_layer_for_fabric(fabric.name).placement != "global":
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

            self._validate_layer_placements(
                fabric.layers,
                f"fabrics[{fabric.index}].layers",
                is_multi_fabric_layers=True,
            )
            effective_layers = (self.gpu_nodes_layer_for_fabric(fabric.name), *fabric.layers)
            self._validate_expanded_node_id_uniqueness(
                effective_layers,
                fabric_name=fabric.name,
                grouping_name=fabric.grouping,
            )
            self._validate_links(
                effective_layers,
                fabric.links,
                f"fabrics[{fabric.index}].links",
            )

    def _validate_grouping_reserved_names(self) -> None:
        reserved_names = {"global", MULTI_FABRIC_GROUP_PLACEMENT, GPU_NODES_LAYER_NAME}
        for grouping in self.groupings:
            normalized_name = normalize_identifier(grouping.name)
            if normalized_name in reserved_names:
                raise InvalidTopologyConfig(
                    "groupings names must not use reserved placement names "
                    f"{sorted(reserved_names)!r}."
                )

    def _validate_grouping_sizes(self) -> None:
        assert self.gpu_nodes is not None
        members_per_group_values = [grouping.members_per_group for grouping in self.groupings]
        if len(members_per_group_values) != len(set(members_per_group_values)):
            raise InvalidTopologyConfig(
                "groupings members_per_group values must be unique."
            )

        for grouping in self.groupings:
            if self.gpu_nodes.total_nodes % grouping.members_per_group != 0:
                raise InvalidTopologyConfig(
                    f"groupings[{grouping.index}].members_per_group must divide "
                    "gpu_nodes.total_nodes exactly."
                )

        sorted_groupings = sorted(
            self.groupings,
            key=lambda item: item.members_per_group,
            reverse=True,
        )
        for larger, smaller in zip(sorted_groupings[:-1], sorted_groupings[1:]):
            if larger.members_per_group % smaller.members_per_group != 0:
                raise InvalidTopologyConfig(
                    "groupings must form a clean nesting chain by divisibility."
                )

    def _validate_gpu_nodes_fabric_mappings(self) -> None:
        assert self.gpu_nodes is not None
        port_layout_names = self.gpu_nodes.fabric_names
        normalized_port_layout_names = {
            normalize_identifier(name): name for name in port_layout_names
        }
        normalized_fabric_names = {
            normalize_identifier(fabric.name): fabric.name for fabric in self.fabrics
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
        self,
        layers: Sequence[LayerConfig],
        path_prefix: str,
        is_multi_fabric_layers: bool = False,
    ) -> None:
        if is_multi_fabric_layers:
            available_placements = {"global", MULTI_FABRIC_GROUP_PLACEMENT}
        else:
            group_names = [group.name for group in self.groups]
            available_placements = {"global", *group_names}

        for layer in layers:
            if layer.placement not in available_placements:
                if is_multi_fabric_layers:
                    raise InvalidTopologyConfig(
                        f"{_layer_path(path_prefix, layer, True)}.placement must be "
                        "'global' or 'group' in multi-fabric mode."
                    )
                raise InvalidTopologyConfig(
                    f"{_layer_path(path_prefix, layer, False)}.placement must be "
                    "'global' or one of the declared groups: "
                    f"{sorted(name for name in available_placements if name != 'global')!r}."
                )

    def _validate_links(
        self,
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
            self._validate_link_policy(link, lower_layer, upper_layer, path_prefix)
            self._validate_link_bandwidth_support(
                link,
                lower_layer,
                upper_layer,
                path_prefix,
            )

    def _validate_link_policy(
        self,
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
        self,
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
        self,
        layers: Sequence[LayerConfig],
        fabric_name: str | None = None,
        grouping_name: str | None = None,
    ) -> None:
        seen_node_ids: dict[str, str] = {}
        group = self.group()
        single_fabric_group_indexes = range(1, group.count + 1) if group else ()
        multi_fabric_group_indexes = (
            range(1, self.grouping_count(grouping_name) + 1)
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
                            physical_ordinal = self.physical_node_ordinal(
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

                    group_label = self.group_label_for_group(grouping_name, group_index)
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

    def to_dict(self) -> dict[str, Any]:
        if not self.is_multi_fabric:
            return {
                "groups": [group.to_dict() for group in self.groups],
                "layers": [layer.to_dict() for layer in self.layers],
                "links": [link.to_dict() for link in self.links],
            }

        return {
            "groupings": [grouping.to_dict() for grouping in self.groupings],
            "gpu_nodes": self.gpu_nodes.to_dict() if self.gpu_nodes is not None else None,
            "fabrics": [fabric.to_dict() for fabric in self.fabrics],
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return self.to_dict() == dict(other)
        return super().__eq__(other)


def ensure_topology_config(config: Mapping[str, Any] | TopologyConfig) -> TopologyConfig:
    if isinstance(config, TopologyConfig):
        return config
    return TopologyConfig.from_mapping(config)


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


def _parse_legacy_multi_fabric_config(
    raw_config: Mapping[str, Any],
    groups: tuple[GroupConfig, ...],
) -> tuple[GpuNodesConfig, tuple[GroupingConfig, ...], tuple[FabricConfig, ...]]:
    if len(groups) > 1:
        raise InvalidTopologyConfig(
            "Only one repeated group definition is supported in legacy multi-fabric mode."
        )

    raw_gpu_nodes = raw_config.get("gpu_nodes")
    path = "gpu_nodes"
    if not isinstance(raw_gpu_nodes, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")

    nodes_per_group = _require_positive_int(raw_gpu_nodes, "nodes_per_group", path)
    total_nodes = nodes_per_group
    grouping_name: str | None = None
    if groups:
        grouping_name = groups[0].name
        total_nodes = groups[0].count * nodes_per_group

    gpu_nodes = _parse_gpu_nodes(
        {
            "total_nodes": total_nodes,
            "fabric_port_layouts": raw_gpu_nodes.get("fabric_port_layouts"),
        }
    )
    groupings = (
        (
            GroupingConfig(
                index=0,
                name=grouping_name,
                members_per_group=nodes_per_group,
            ),
        )
        if grouping_name is not None
        else ()
    )
    fabrics = _parse_fabrics(
        raw_config.get("fabrics"),
        compatibility_grouping_name=grouping_name,
        allow_missing_grouping=True,
    )
    return gpu_nodes, groupings, fabrics


def _parse_gpu_nodes(raw_gpu_nodes: Any) -> GpuNodesConfig:
    path = "gpu_nodes"
    if not isinstance(raw_gpu_nodes, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")

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


def _parse_fabrics(
    raw_fabrics: Any,
    compatibility_grouping_name: str | None = None,
    allow_missing_grouping: bool = False,
) -> tuple[FabricConfig, ...]:
    if not isinstance(raw_fabrics, Sequence) or isinstance(raw_fabrics, (str, bytes)):
        raise InvalidTopologyConfig("fabrics must be a list of fabric mappings.")

    return tuple(
        _parse_fabric(
            raw_fabric,
            index,
            compatibility_grouping_name,
            allow_missing_grouping,
        )
        for index, raw_fabric in enumerate(raw_fabrics)
    )


def _parse_fabric(
    raw_fabric: Any,
    index: int,
    compatibility_grouping_name: str | None,
    allow_missing_grouping: bool,
) -> FabricConfig:
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

    grouping = compatibility_grouping_name
    if compatibility_grouping_name is None and not allow_missing_grouping:
        grouping = _required_string(raw_fabric, "grouping", path)

    layers = tuple(
        _parse_layer(
            raw_layer,
            layer_index + 1,
            f"{path}.layers[{layer_index}]",
            compatibility_grouping_name=compatibility_grouping_name,
        )
        for layer_index, raw_layer in enumerate(raw_layers)
    )
    links = tuple(
        _parse_link(raw_link, link_index, f"{path}.links[{link_index}]")
        for link_index, raw_link in enumerate(raw_links)
    )

    return FabricConfig(
        index=index,
        name=_required_name(raw_fabric, path),
        grouping=grouping,
        layers=layers,
        links=links,
    )


def _parse_layer(
    raw_layer: Any,
    index: int,
    path: str,
    compatibility_grouping_name: str | None = None,
) -> LayerConfig:
    if not isinstance(raw_layer, Mapping):
        raise InvalidTopologyConfig(f"{path} must be a mapping.")

    legacy_keys = sorted(LEGACY_LAYER_PORT_KEYS & set(raw_layer))
    if legacy_keys:
        raise InvalidTopologyConfig(
            f"{path} uses legacy port fields {legacy_keys!r}; replace them with a "
            "port_layout block."
        )

    placement = _required_string(raw_layer, "placement", path)
    if (
        compatibility_grouping_name is not None
        and placement == compatibility_grouping_name
    ):
        placement = MULTI_FABRIC_GROUP_PLACEMENT

    return LayerConfig(
        index=index,
        name=_required_name(raw_layer, path),
        placement=placement,
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
