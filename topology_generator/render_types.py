from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NodeBoxGeometry:
    width: float
    height: float
    name_y_offset: float
    ordinal_y_offset: float
    ports_value_y_offset: float
    ports_label_y_offset: float
    aggregate_x_offset: float
    aggregate_text_offset: float
    aggregate_arrow_size: float
    aggregate_left_extent: float
    fanout_arc_width: float
    fanout_arc_height: float
    fanout_radius_padding: float
    fanout_narrow_extra_padding: float
    fanout_narrow_span_threshold_deg: float
    fanout_up_margin_deg: float
    fanout_down_margin_deg: float

    @property
    def half_height(self) -> float:
        return self.height / 2


@dataclass(frozen=True)
class LayoutProfile:
    node_box: NodeBoxGeometry
    layer_spacing: float
    grouped_node_offset: float
    global_node_offset: float
    group_side_padding: float
    group_vertical_padding: float
    two_group_inner_gap: float
    hidden_group_lane_width: float
    right_annotation_gap: float
    right_annotation_extent: float
    plot_padding_x: float
    plot_padding_y: float
    figure_width: float
    figure_height_min: float
    figure_height_max: float
    save_padding_inches: float
    placeholder_text_height: float
    placeholder_text_char_width: float

    def grouped_half_span(self) -> float:
        return (
            self.grouped_node_offset
            + (self.node_box.width / 2)
            + self.group_side_padding
            + self.node_box.aggregate_left_extent
        )


@dataclass(frozen=True)
class LayoutResult:
    positions: dict[str, tuple[float, float]]
    visible_nodes: set[str]
    group_bounds: list[tuple[float, float, float, float, str]]
    placeholder_labels: list[tuple[float, float, str]]
    profile: LayoutProfile
    layer_bandwidth_x: float
    layer_heights: dict[int, float]


@dataclass(frozen=True)
class RenderSummary:
    sorted_node_items: list[tuple[str, dict[str, Any]]]
    grouped_layer_nodes: dict[int, dict[int, list[str]]]
    global_layer_nodes: dict[int, list[str]]
    all_nodes_by_layer: dict[int, list[str]]
    layer_bandwidths: dict[tuple[int, int], float]
    group_layer_bandwidths: dict[tuple[int, int, int], float]
