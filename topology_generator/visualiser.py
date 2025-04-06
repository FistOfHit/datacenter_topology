import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import random
import logging
from typing import Dict, Any, Tuple, List, Set

logger = logging.getLogger(__name__)


LAYER_HEIGHTS = {
    "server": 0,
    "leaf": 1,
    "spine": 2,
    "core": 3,
}
LAYER_COLORS = {
    "server": "#add8e6",
    "leaf": "#90ee90",
    "spine": "#ffcccb",
    "core": "#ffa07a",
}


def get_random_color():
    """
    Generate a random hex color, excluding very light and dark colors.

    Returns:
        str: A random hex color code.
    """
    r = random.randint(64, 192)
    g = random.randint(64, 192)
    b = random.randint(64, 192)
    color = "#{:02x}{:02x}{:02x}".format(r, g, b)

    return color


def format_bandwidth(bandwidth_gb: float) -> str:
    """
    Format bandwidth in GB or TB as appropriate.

    Params:
        bandwidth_gb (float): The bandwidth in GB.

    Returns:
        str: The formatted bandwidth.
    """
    if bandwidth_gb >= 1000:
        return f"{bandwidth_gb/1000:.1f}T"
    return f"{bandwidth_gb}G"


def draw_arrow_symbol(
    ax: plt.Axes,
    arrow_size: float,
    base_x: float,
    base_y: float,
    direction: str = "up",
):
    """
    Draw an arrow symbol at the specified base coordinates.

    Params:
        ax (matplotlib.axes.Axes): The matplotlib axes object.
        arrow_size (float): The size of the arrow.
        base_x (float): The x-coordinate of the base position.
        base_y (float): The y-coordinate of the base position.
        direction (str, optional): The direction of the arrow. Defaults to "up".
    """
    multiplier = 1 if direction == "up" else -1
    ax.arrow(
        base_x,
        base_y,
        0,
        arrow_size * multiplier,
        head_width=arrow_size * 0.8,
        head_length=arrow_size * 0.4,
        fc="black",
        ec="black",
        length_includes_head=True,
    )


def add_bandwidth_indicators(
    ax: plt.Axes,
    pos: Dict[str, Tuple[float, float]],
    node: str,
    node_data: Dict[str, Any],
    node_half_height: float = 0.15,
):
    """
    Add bandwidth arrows and values to a node.

    Params:
        ax (matplotlib.axes.Axes): The matplotlib axes object.
        pos (dict): The node positions.
        node (str): The node name.
        node_data (dict): The node data.
        node_half_height (float, optional): The half height of the node. Defaults to 0.15.
    """
    x, y = pos[node]
    symbol_x = x - 0.6
    arrow_size = 0.04
    text_offset = 0.08
    adjustment = node_half_height - 0.05

    directions = {"up": 1, "down": -1}

    for direction, multiplier in directions.items():
        agg_bw = node_data.get(f"aggregate_bandwidth_{direction}", 0)
        if agg_bw > 0:
            symbol_y = y + adjustment * multiplier
            draw_arrow_symbol(
                ax,
                arrow_size,
                symbol_x,
                symbol_y - (arrow_size / 2) * multiplier,
                direction,
            )
            plt.text(
                symbol_x + text_offset,
                symbol_y,
                format_bandwidth(agg_bw),
                ha="left",
                va="center",
                fontsize=8,
            )


def add_layer_bandwidth_arrow(
    ax: plt.Axes,
    y1: float,
    y2: float,
    bandwidth_gb: float,
    x_pos: float = 2.7,
):
    """
    Add a double-ended arrow showing total layer bandwidth.

    Params:
        ax (matplotlib.axes.Axes): The matplotlib axes object.
        y1 (float): The y-coordinate of the first layer.
        y2 (float): The y-coordinate of the second layer.
        bandwidth_gb (float): The total bandwidth of the layer.
        x_pos (float, optional): The x-coordinate of the arrow. Defaults to 2.7.
    """
    arrow_properties = dict(
        head_width=0.1,
        head_length=0.1,
        fc="black",
        ec="black",
        length_includes_head=True,
    )

    midpoint_y = (y1 + y2) / 2
    arrow_length = (y2 - y1) / 4
    ax.arrow(x_pos, midpoint_y, 0, arrow_length, **arrow_properties)
    ax.arrow(x_pos, midpoint_y, 0, -arrow_length, **arrow_properties)

    plt.text(
        x_pos + 0.15,
        midpoint_y,
        format_bandwidth(bandwidth_gb),
        ha="left",
        va="center",
        fontsize=8,
        color="black",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.8),
    )


def calculate_layer_bandwidth(G: nx.Graph, layer_nodes: List[str]) -> float:
    """
    Calculate total bandwidth for a layer based on number of nodes and cables.

    Params:
        G (networkx.Graph): The networkx graph.
        layer_nodes (list): The nodes in the layer.

    Returns:
        float: The total bandwidth for the layer.
    """
    total_bandwidth = 0
    for u, v in G.edges():
        if u in layer_nodes and v in layer_nodes:
            bandwidth = G.edges[u, v].get("cable_bandwidth_gb")
            num_cables = G.edges[u, v].get("num_cables")
            total_bandwidth += bandwidth * num_cables

    return total_bandwidth


def calculate_node_positions(
    node_type: str,
    nodes: List[str],
) -> Dict[str, Tuple[float, float]]:
    """
    Calculate the positions of nodes in a layer.

    Params:
        node_type (str): The node type.
        nodes (list): The nodes in the layer.

    Returns:
        Dict[str, Tuple[float, float]]: The node positions.
    """
    positions: dict[str, tuple[float, float]] = {}
    min_spacing = 1.2

    if len(nodes) > 4:
        positions[nodes[0]] = (-2, LAYER_HEIGHTS[node_type])
        positions[nodes[-1]] = (2, LAYER_HEIGHTS[node_type])

    else:
        total_width = (len(nodes) - 1) * min_spacing
        start_x = -total_width / 2
        for idx, node in enumerate(nodes):
            positions[node] = (
                float(start_x + (idx * min_spacing)),
                LAYER_HEIGHTS[node_type],
            )

    return positions


def draw_condensed_layer(
    G: nx.Graph,
    ax: plt.Axes,
    positions: Dict[str, Tuple[float, float]],
    node_type: str,
    color: str,
) -> Tuple[Set[str], List[str]]:
    """
    Draw condensed nodes for a layer.

    Params:
        G (networkx.Graph): The networkx graph.
        ax (matplotlib.axes.Axes): The matplotlib axes object.
        positions (dict): The node positions.
        node_type (str): The node type.
        color (str): The color of the nodes.

    Returns:
        Tuple[Set[str], List[str]]: The visible nodes and the node names.
    """
    node_size = 2500

    # Determine which nodes are visible in the diagram
    node_names = [n for n, d in G.nodes(data=True) if d["type"] == node_type]
    visible_nodes = set()
    nodes_to_draw = (
        [node_names[0], node_names[-1]] if len(node_names) > 3 else node_names
    )
    visible_nodes.update(nodes_to_draw)

    nx.draw_networkx_nodes(
        G,
        positions,
        nodelist=nodes_to_draw,
        node_color=color,
        node_size=node_size,
        node_shape="s",
        edgecolors="black",
    )

    # Add text and labels to the nodes
    for node in nodes_to_draw:
        used_ports_eq = G.nodes[node]["used_ports_equivalent"]
        total_ports = G.nodes[node]["total_ports"]

        name, node_id = node.split("_")
        labels = [name, node_id, f"{used_ports_eq:.0f}/{total_ports}"]

        for i, line in enumerate(labels):
            ax.text(
                positions[node][0],
                positions[node][1] + 0.05 - (i * 0.07),
                line,
                fontsize=8,
                ha="center",
                va="center",
            )

        add_bandwidth_indicators(ax, positions, node, G.nodes[node])

    # Add text to indicate there are more nodes in the layer not shown
    if len(node_names) > 3:
        plt.text(
            0,
            LAYER_HEIGHTS[node_type],
            f"...({len(node_names) - 2} more)...",
            horizontalalignment="center",
            verticalalignment="center",
        )

    return visible_nodes, node_names


def get_bandwidth_colors(G: nx.Graph) -> Dict[str, str]:
    """
    Get the bandwidth colors for the topology.

    Params:
        G (networkx.Graph): The networkx graph.

    Returns:
        Dict[str, str]: The bandwidth colors.
    """
    # Get the unique bandwidths from all links in the graph
    unique_bandwidths = set(
        d.get("cable_bandwidth_gb") for _, _, d in G.edges(data=True)
    )

    # If there are multiple bandwidths, assign a random color to each
    bandwidth_colors = {bw: "black" for bw in unique_bandwidths}
    if len(unique_bandwidths) > 1:
        bandwidth_colors = {
            bw: ("black" if i == 0 else get_random_color())
            for i, bw in enumerate(unique_bandwidths)
        }

    return bandwidth_colors


def visualize_topology(G: nx.Graph, output_dir: str | None = None):
    """
    Visualize the network topology graph with colored edges based on bandwidth.

    Params:
        G (networkx.Graph): The networkx graph.
        output_dir (str, optional): The output directory. Defaults to None.
    """
    logger.info("Starting topology visualization")

    _, ax = plt.subplots(figsize=(12, 8))

    # Calculate and draw nodes
    layer_positions = {}
    for node_type in LAYER_HEIGHTS:
        nodes = [n for n, d in G.nodes(data=True) if d["type"] == node_type]
        layer_positions.update(calculate_node_positions(node_type, nodes))

    visible_nodes = set()
    layer_node_names = {}
    for node_type, color in LAYER_COLORS.items():
        visible_set, node_names = draw_condensed_layer(
            G,
            ax,
            layer_positions,
            node_type,
            color,
        )
        visible_nodes.update(visible_set)
        layer_node_names[node_type] = node_names

    # Draw edges
    visible_edges = [
        (u, v) for u, v in G.edges() if u in visible_nodes and v in visible_nodes
    ]
    node_half_height = 0.15
    bandwidth_colors = get_bandwidth_colors(G)
    for u, v in visible_edges:
        x1, y1 = layer_positions[u]
        x2, y2 = layer_positions[v]
        bandwidth = G.edges[u, v].get("cable_bandwidth_gb", "10G")
        num_cables = G.edges[u, v].get("num_cables", 1)
        color = bandwidth_colors[bandwidth]

        if y1 < y2:
            y1 += node_half_height
            y2 -= node_half_height
        else:
            y1 -= node_half_height
            y2 += node_half_height

        plt.plot([x1, x2], [y1, y2], "-", color=color, linewidth=2, zorder=1)

        if num_cables > 1:
            plt.text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                str(num_cables),
                horizontalalignment="center",
                verticalalignment="center",
                bbox=dict(
                    facecolor="white",
                    edgecolor="black",
                    alpha=1,
                    boxstyle="circle",
                ),
                zorder=2,
                fontsize=8,
            )

    # Add layer bandwidth arrows
    for layer1, layer2 in zip(
        list(LAYER_HEIGHTS.keys())[:-1], list(LAYER_HEIGHTS.keys())[1:]
    ):
        y1, y2 = LAYER_HEIGHTS[layer1], LAYER_HEIGHTS[layer2]
        combined_nodes = layer_node_names[layer1] + layer_node_names[layer2]
        layer_bandwidth = calculate_layer_bandwidth(G, combined_nodes)
        if layer_bandwidth > 0:
            add_layer_bandwidth_arrow(ax, y1, y2, layer_bandwidth)

    if len(bandwidth_colors) > 1:
        legend_elements = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="w",
                markeredgecolor="black",
                markersize=10,
                label="Cable count",
            ),
        ]

        # Add bandwidth legend items
        for bw, color in bandwidth_colors.items():
            bandwidth_suffix = "G" if int(str(bw).rstrip("G")) < 1000 else "T"
            legend_elements.append(
                Patch(
                    facecolor=color,
                    label=f"{str(bw).rstrip('G')}{bandwidth_suffix}",
                )
            )

        ax.legend(
            handles=legend_elements, loc="upper left", bbox_to_anchor=(0.02, 0.98)
        )

    plt.xlim(-3, 3.5)
    plt.ylim(-0.5, 2.5)
    plt.title("Network Topology")
    plt.axis("off")

    if output_dir:
        output_path = f"{output_dir}/topology.png"
        plt.savefig(output_path, bbox_inches="tight", dpi=300, pad_inches=0.5)
        logger.info(f"Saved topology visualization to {output_path}")
    else:
        plt.show()
