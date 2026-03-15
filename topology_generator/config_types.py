from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from topology_generator.config_identifiers import (
    GPU_NODES_LAYER_NAME,
    MULTI_FABRIC_GROUP_PLACEMENT,
    bandwidth_decimal,
    normalize_identifier,
)


class InvalidTopologyConfig(ValueError):
    """Raised when the supplied topology configuration is invalid."""


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
    _lane_units_by_bandwidth: Mapping[Decimal, int] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_lane_units_by_bandwidth",
            {
                bandwidth_decimal(mode.port_bandwidth_gb): mode.lane_units
                for mode in self.supported_port_modes
            },
        )

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
        return self._lane_units_by_bandwidth.get(bandwidth_decimal(bandwidth_gb))


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
        return tuple(
            fabric_port_layout.name for fabric_port_layout in self.fabric_port_layouts
        )


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
        from topology_generator.config_parser import parse_topology_config

        return parse_topology_config(raw_config)

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
        from topology_generator.config_validation import validate_topology_config

        validate_topology_config(self)

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
