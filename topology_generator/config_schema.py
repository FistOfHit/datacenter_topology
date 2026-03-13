from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class InvalidTopologyConfig(ValueError):
    """Raised when the supplied topology configuration is invalid."""


@dataclass(frozen=True)
class LayerConfig:
    index: int
    name: str
    node_count_in_layer: int
    ports_per_node: int
    port_bandwidth_gb_per_port: float
    uplink_cables_per_node_to_each_node_in_next_layer: int
    uplink_cable_bandwidth_gb: float
    downlink_cables_per_node_to_each_node_in_previous_layer: int
    downlink_cable_bandwidth_gb: float

    def to_dict(self) -> dict[str, Any]:
        layer_dict: dict[str, Any] = {
            "name": self.name,
            "node_count_in_layer": self.node_count_in_layer,
            "ports_per_node": self.ports_per_node,
            "port_bandwidth_gb_per_port": self.port_bandwidth_gb_per_port,
        }
        if (
            self.downlink_cables_per_node_to_each_node_in_previous_layer > 0
            or self.downlink_cable_bandwidth_gb > 0
        ):
            layer_dict[
                "downlink_cables_per_node_to_each_node_in_previous_layer"
            ] = self.downlink_cables_per_node_to_each_node_in_previous_layer
            layer_dict["downlink_cable_bandwidth_gb"] = (
                self.downlink_cable_bandwidth_gb
            )
        if (
            self.uplink_cables_per_node_to_each_node_in_next_layer > 0
            or self.uplink_cable_bandwidth_gb > 0
        ):
            layer_dict[
                "uplink_cables_per_node_to_each_node_in_next_layer"
            ] = self.uplink_cables_per_node_to_each_node_in_next_layer
            layer_dict["uplink_cable_bandwidth_gb"] = self.uplink_cable_bandwidth_gb
        return layer_dict


@dataclass(frozen=True)
class TopologyConfig(Mapping[str, Any]):
    """Validated topology configuration with dict-like compatibility."""

    layers: tuple[LayerConfig, ...]

    @classmethod
    def from_mapping(cls, raw_config: Mapping[str, Any]) -> "TopologyConfig":
        if not isinstance(raw_config, Mapping):
            raise InvalidTopologyConfig("Configuration must be a mapping.")

        raw_layers = raw_config.get("layers")
        if not isinstance(raw_layers, Sequence) or isinstance(raw_layers, (str, bytes)):
            raise InvalidTopologyConfig("layers must be a list of layer mappings.")
        if len(raw_layers) < 2:
            raise InvalidTopologyConfig("Topology must contain at least 2 layers.")

        layers = tuple(
            _parse_layer(raw_layer, index, len(raw_layers))
            for index, raw_layer in enumerate(raw_layers)
        )
        config = cls(layers=layers)
        config._validate_semantics()
        return config

    def _validate_semantics(self) -> None:
        for layer in self.layers:
            if layer.node_count_in_layer <= 0:
                raise InvalidTopologyConfig(
                    f"layers[{layer.index}].node_count_in_layer must be greater than zero."
                )
            if layer.ports_per_node < 0:
                raise InvalidTopologyConfig(
                    f"layers[{layer.index}].ports_per_node must be greater than or equal to zero."
                )
            if layer.port_bandwidth_gb_per_port <= 0:
                raise InvalidTopologyConfig(
                    f"layers[{layer.index}].port_bandwidth_gb_per_port must be greater than zero."
                )

            if (
                layer.uplink_cables_per_node_to_each_node_in_next_layer > 0
                and layer.uplink_cable_bandwidth_gb <= 0
            ):
                raise InvalidTopologyConfig(
                    f"layers[{layer.index}].uplink_cable_bandwidth_gb must be greater than zero "
                    "when uplink_cables_per_node_to_each_node_in_next_layer is greater than zero."
                )
            if (
                layer.downlink_cables_per_node_to_each_node_in_previous_layer > 0
                and layer.downlink_cable_bandwidth_gb <= 0
            ):
                raise InvalidTopologyConfig(
                    f"layers[{layer.index}].downlink_cable_bandwidth_gb must be greater than zero "
                    "when downlink_cables_per_node_to_each_node_in_previous_layer is greater than zero."
                )
            if (
                layer.uplink_cables_per_node_to_each_node_in_next_layer == 0
                and layer.uplink_cable_bandwidth_gb != 0
            ):
                raise InvalidTopologyConfig(
                    f"layers[{layer.index}].uplink_cable_bandwidth_gb must be zero when "
                    "uplink_cables_per_node_to_each_node_in_next_layer is zero."
                )
            if (
                layer.downlink_cables_per_node_to_each_node_in_previous_layer == 0
                and layer.downlink_cable_bandwidth_gb != 0
            ):
                raise InvalidTopologyConfig(
                    f"layers[{layer.index}].downlink_cable_bandwidth_gb must be zero when "
                    "downlink_cables_per_node_to_each_node_in_previous_layer is zero."
                )

        bottom_layer = self.layers[0]
        if (
            bottom_layer.downlink_cables_per_node_to_each_node_in_previous_layer != 0
            or bottom_layer.downlink_cable_bandwidth_gb != 0
        ):
            raise InvalidTopologyConfig(
                "layers[0] cannot define non-zero downlink settings."
            )

        top_layer = self.layers[-1]
        if (
            top_layer.uplink_cables_per_node_to_each_node_in_next_layer != 0
            or top_layer.uplink_cable_bandwidth_gb != 0
        ):
            raise InvalidTopologyConfig(
                f"layers[{top_layer.index}] cannot define non-zero uplink settings."
            )

        for lower, upper in self.adjacent_pairs():
            if (
                lower.uplink_cables_per_node_to_each_node_in_next_layer
                != upper.downlink_cables_per_node_to_each_node_in_previous_layer
            ):
                raise InvalidTopologyConfig(
                    "Adjacent layers must agree on link counts: "
                    f"layers[{lower.index}].uplink_cables_per_node_to_each_node_in_next_layer != "
                    f"layers[{upper.index}].downlink_cables_per_node_to_each_node_in_previous_layer."
                )
            if lower.uplink_cable_bandwidth_gb != upper.downlink_cable_bandwidth_gb:
                raise InvalidTopologyConfig(
                    "Adjacent layers must agree on link bandwidth: "
                    f"layers[{lower.index}].uplink_cable_bandwidth_gb != "
                    f"layers[{upper.index}].downlink_cable_bandwidth_gb."
                )

            if lower.uplink_cable_bandwidth_gb > lower.port_bandwidth_gb_per_port:
                raise InvalidTopologyConfig(
                    f"layers[{lower.index}].uplink_cable_bandwidth_gb exceeds "
                    f"layers[{lower.index}].port_bandwidth_gb_per_port."
                )
            if lower.uplink_cable_bandwidth_gb > upper.port_bandwidth_gb_per_port:
                raise InvalidTopologyConfig(
                    f"layers[{lower.index}].uplink_cable_bandwidth_gb exceeds "
                    f"layers[{upper.index}].port_bandwidth_gb_per_port."
                )

        for layer in self.layers:
            if self.required_ports_per_node(layer.index) > layer.ports_per_node:
                raise InvalidTopologyConfig(
                    f"layers[{layer.index}].ports_per_node is insufficient for the configured "
                    "adjacent-layer cabling pattern."
                )

    def layer(self, layer_index: int) -> LayerConfig:
        return self.layers[layer_index]

    def adjacent_pairs(self) -> Iterator[tuple[LayerConfig, LayerConfig]]:
        for index in range(len(self.layers) - 1):
            yield self.layers[index], self.layers[index + 1]

    def required_ports_per_node(self, layer_index: int) -> int:
        layer = self.layer(layer_index)
        required_ports = 0

        if layer_index > 0:
            lower_layer = self.layer(layer_index - 1)
            required_ports += (
                lower_layer.node_count_in_layer
                * layer.downlink_cables_per_node_to_each_node_in_previous_layer
            )

        if layer_index < len(self.layers) - 1:
            upper_layer = self.layer(layer_index + 1)
            required_ports += (
                upper_layer.node_count_in_layer
                * layer.uplink_cables_per_node_to_each_node_in_next_layer
            )

        return required_ports

    def derived_down_bandwidth_per_node(self, layer_index: int) -> float:
        if layer_index == 0:
            return 0.0
        lower_layer = self.layer(layer_index - 1)
        layer = self.layer(layer_index)
        return (
            lower_layer.node_count_in_layer
            * layer.downlink_cables_per_node_to_each_node_in_previous_layer
            * layer.downlink_cable_bandwidth_gb
        )

    def derived_up_bandwidth_per_node(self, layer_index: int) -> float:
        if layer_index == len(self.layers) - 1:
            return 0.0
        upper_layer = self.layer(layer_index + 1)
        layer = self.layer(layer_index)
        return (
            upper_layer.node_count_in_layer
            * layer.uplink_cables_per_node_to_each_node_in_next_layer
            * layer.uplink_cable_bandwidth_gb
        )

    def to_dict(self) -> dict[str, Any]:
        return {"layers": [layer.to_dict() for layer in self.layers]}

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


def _parse_layer(
    raw_layer: Any,
    index: int,
    total_layers: int,
) -> LayerConfig:
    if not isinstance(raw_layer, Mapping):
        raise InvalidTopologyConfig(f"layers[{index}] must be a mapping.")

    return LayerConfig(
        index=index,
        name=_optional_name(raw_layer, index),
        node_count_in_layer=_require_positive_int(
            raw_layer, "node_count_in_layer", f"layers[{index}]"
        ),
        ports_per_node=_require_non_negative_int(
            raw_layer, "ports_per_node", f"layers[{index}]"
        ),
        port_bandwidth_gb_per_port=_require_positive_number(
            raw_layer,
            "port_bandwidth_gb_per_port",
            f"layers[{index}]",
        ),
        uplink_cables_per_node_to_each_node_in_next_layer=_directional_int(
            raw_layer,
            "uplink_cables_per_node_to_each_node_in_next_layer",
            f"layers[{index}]",
            default_zero=index == total_layers - 1,
        ),
        uplink_cable_bandwidth_gb=_directional_number(
            raw_layer,
            "uplink_cable_bandwidth_gb",
            f"layers[{index}]",
            default_zero=index == total_layers - 1,
        ),
        downlink_cables_per_node_to_each_node_in_previous_layer=_directional_int(
            raw_layer,
            "downlink_cables_per_node_to_each_node_in_previous_layer",
            f"layers[{index}]",
            default_zero=index == 0,
        ),
        downlink_cable_bandwidth_gb=_directional_number(
            raw_layer,
            "downlink_cable_bandwidth_gb",
            f"layers[{index}]",
            default_zero=index == 0,
        ),
    )


def _optional_name(raw_layer: Mapping[str, Any], index: int) -> str:
    value = raw_layer.get("name")
    if value is None:
        return f"layer_{index}"
    if not isinstance(value, str) or not value.strip():
        raise InvalidTopologyConfig(f"layers[{index}].name must be a non-empty string.")
    return value.strip()


def _directional_int(
    raw_layer: Mapping[str, Any],
    key: str,
    path: str,
    *,
    default_zero: bool,
) -> int:
    if key not in raw_layer and default_zero:
        return 0
    return _require_non_negative_int(raw_layer, key, path)


def _directional_number(
    raw_layer: Mapping[str, Any],
    key: str,
    path: str,
    *,
    default_zero: bool,
) -> float:
    if key not in raw_layer and default_zero:
        return 0.0
    return _require_non_negative_number(raw_layer, key, path)


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


def _require_non_negative_number(
    config: Mapping[str, Any],
    key: str,
    path: str,
) -> float:
    value = config.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InvalidTopologyConfig(f"{path}.{key} must be a number.")
    if value < 0:
        raise InvalidTopologyConfig(f"{path}.{key} must be greater than or equal to zero.")
    return float(value)
