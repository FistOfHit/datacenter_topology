from __future__ import annotations

import re
from decimal import Decimal


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


def bandwidth_decimal(value: float) -> Decimal:
    """Convert a numeric bandwidth into a stable decimal representation."""
    return Decimal(str(value)).normalize()


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
