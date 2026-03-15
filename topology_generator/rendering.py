from __future__ import annotations

from os import PathLike

import networkx as nx

from topology_generator.graph_metadata import fabric_names, is_multi_fabric_graph
from topology_generator.render_drawing import visualize_single_topology
from topology_generator.render_layout import build_render_summary, calculate_layout
from topology_generator.topology_generator import (
    build_fabric_output_name,
    get_fabric_view,
)


def visualize_topology(
    graph: nx.Graph,
    output_dir: str | PathLike[str] | None = None,
) -> None:
    if is_multi_fabric_graph(graph):
        for fabric_name in fabric_names(graph):
            fabric_graph = get_fabric_view(graph, fabric_name)
            render_summary = build_render_summary(fabric_graph)
            visualize_single_topology(
                fabric_graph,
                calculate_layout(fabric_graph, render_summary),
                output_dir,
                filename=f"topology_{build_fabric_output_name(fabric_name)}.png",
                title=f"Network Topology ({fabric_name})",
                render_summary=render_summary,
            )
        return

    render_summary = build_render_summary(graph)
    visualize_single_topology(
        graph,
        calculate_layout(graph, render_summary),
        output_dir,
        render_summary=render_summary,
    )
