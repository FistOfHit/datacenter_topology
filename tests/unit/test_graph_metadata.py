import networkx as nx

from topology_generator.graph_metadata import (
    fabric_names,
    flatten_node_attrs_for_fabric,
    is_multi_fabric_graph,
    node_sort_key,
)


def test_graph_metadata_helpers_expose_graph_flags():
    graph = nx.Graph()
    graph.graph["is_multi_fabric"] = True
    graph.graph["fabric_names"] = ("backend", "frontend")

    assert is_multi_fabric_graph(graph) is True
    assert fabric_names(graph) == ("backend", "frontend")


def test_flatten_node_attrs_for_fabric_flattens_shared_gpu_metrics():
    attrs = {
        "layer_index": 0,
        "layer_name": "gpu_nodes",
        "is_shared_gpu_node": True,
        "fabric_metrics": {
            "backend": {
                "group_label": "pod_1",
                "port_pools": (
                    {
                        "name": "fabric",
                        "used_lane_units": 1,
                        "total_lane_units": 1,
                        "port_offset": 0,
                        "base_lane_bandwidth_gb": 100,
                        "supported_port_bandwidths_gb": (100.0,),
                    },
                ),
            }
        },
    }

    flattened = flatten_node_attrs_for_fabric(attrs, "backend")

    assert flattened is not None
    assert flattened["fabric"] == "backend"
    assert flattened["group_label"] == "pod_1"
    assert flattened["port_pools"][0]["used_lane_units"] == 1
    assert flattened["port_pools"][0]["name"] == "fabric"


def test_node_sort_key_matches_port_mapping_natural_order():
    pod_2 = {
        "layer_index": 0,
        "group_order": 2,
        "node_ordinal": 1,
    }
    pod_10 = {
        "layer_index": 0,
        "group_order": 10,
        "node_ordinal": 1,
    }

    assert node_sort_key("pod_2_gpu_nodes_1", pod_2) < node_sort_key(
        "pod_10_gpu_nodes_1",
        pod_10,
    )
