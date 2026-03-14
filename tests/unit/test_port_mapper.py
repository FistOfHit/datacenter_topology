import networkx as nx
import pandas as pd
import pytest

from topology_generator.port_mapper import (
    MULTI_FABRIC_PORT_MAPPING_COLUMNS,
    PORT_MAPPING_COLUMNS,
    create_port_mapping,
    extract_port_mapping_rows,
    save_to_excel,
)


def test_extract_port_mapping_rows_preserves_layer_orientation():
    graph = nx.Graph()
    graph.add_node("pod_1_leaf_1", layer_index=1, group_label="pod_1")
    graph.add_node("pod_1_compute_1", layer_index=0, group_label="pod_1")
    graph.add_edge(
        "pod_1_leaf_1",
        "pod_1_compute_1",
        source_ports=[3],
        target_ports=[1],
        source_lane_units_per_cable=2,
        target_lane_units_per_cable=1,
        num_cables=1,
        cable_bandwidth_gb=800,
    )

    rows = extract_port_mapping_rows(graph)

    assert rows == [
        {
            "source_serial_number": None,
            "source_group": "pod_1",
            "source_node_id": "pod_1_compute_1",
            "source_node_port": 1,
            "source_lane_units": 1,
            "target_node_port": 3,
            "target_lane_units": 2,
            "target_node_id": "pod_1_leaf_1",
            "target_group": "pod_1",
            "target_serial_number": None,
            "cable_bandwidth_gb": 800,
            "cable_number": 1,
        }
    ]


def test_extract_port_mapping_rows_rejects_mismatched_allocations():
    graph = nx.Graph()
    graph.add_node("compute_1", layer_index=0, group_label="global")
    graph.add_node("leaf_1", layer_index=1, group_label="global")
    graph.add_edge(
        "compute_1",
        "leaf_1",
        source_ports=[1, 2],
        target_ports=[1],
        source_lane_units_per_cable=1,
        target_lane_units_per_cable=1,
        num_cables=2,
        cable_bandwidth_gb=400,
    )

    with pytest.raises(ValueError, match="allocation mismatch"):
        extract_port_mapping_rows(graph)


def test_extract_port_mapping_rows_rejects_num_cables_mismatch():
    graph = nx.Graph()
    graph.add_node("compute_1", layer_index=0, group_label="global")
    graph.add_node("leaf_1", layer_index=1, group_label="global")
    graph.add_edge(
        "compute_1",
        "leaf_1",
        source_ports=[1],
        target_ports=[1],
        source_lane_units_per_cable=1,
        target_lane_units_per_cable=1,
        num_cables=2,
        cable_bandwidth_gb=400,
    )

    with pytest.raises(ValueError, match="num_cables"):
        extract_port_mapping_rows(graph)


def test_create_port_mapping_returns_expected_dataframe(sample_config):
    from topology_generator.topology_generator import generate_topology

    df = create_port_mapping(generate_topology(sample_config))

    assert list(df.columns) == PORT_MAPPING_COLUMNS
    assert len(df) == 8
    assert df.iloc[0].to_dict() == {
        "source_serial_number": None,
        "source_group": "pod_1",
        "source_node_id": "pod_1_compute_1",
        "source_node_port": 1,
        "source_lane_units": 1,
        "target_node_port": 1,
        "target_lane_units": 1,
        "target_node_id": "pod_1_leaf_1",
        "target_group": "pod_1",
        "target_serial_number": None,
        "cable_bandwidth_gb": 100.0,
        "cable_number": 1,
    }
    assert df.iloc[-1].to_dict() == {
        "source_serial_number": None,
        "source_group": "pod_2",
        "source_node_id": "pod_2_leaf_1",
        "source_node_port": 4,
        "source_lane_units": 1,
        "target_node_port": 2,
        "target_lane_units": 1,
        "target_node_id": "spine_2",
        "target_group": "global",
        "target_serial_number": None,
        "cable_bandwidth_gb": 100.0,
        "cable_number": 8,
    }


def test_save_to_excel_writes_file(tmp_path):
    df = pd.DataFrame(
        [
            {
                "source_serial_number": None,
                "source_group": "pod_1",
                "source_node_id": "node1",
                "source_node_port": 1,
                "source_lane_units": 1,
                "target_node_port": 1,
                "target_lane_units": 2,
                "target_node_id": "node2",
                "target_group": "global",
                "target_serial_number": None,
                "cable_bandwidth_gb": 800,
                "cable_number": 1,
            }
        ],
        columns=PORT_MAPPING_COLUMNS,
    )

    save_to_excel(df, str(tmp_path))

    written_file = tmp_path / "port_mapping.xlsx"
    loaded_df = pd.read_excel(written_file)
    assert written_file.exists()
    assert list(loaded_df.columns) == PORT_MAPPING_COLUMNS
    assert loaded_df.iloc[0]["source_node_id"] == "node1"


def test_create_port_mapping_merges_multi_fabric_rows(multi_fabric_config):
    from topology_generator.topology_generator import generate_topology

    df = create_port_mapping(generate_topology(multi_fabric_config))

    assert list(df.columns) == MULTI_FABRIC_PORT_MAPPING_COLUMNS
    assert len(df) == 7
    assert set(df["fabric"]) == {"backend", "frontend", "oob"}
    assert set(df.loc[df["fabric"] == "oob", "source_group"]) == {
        "pod_1_rack_1",
        "pod_1_rack_2",
    }


def test_extract_port_mapping_rows_uses_natural_node_ordering():
    graph = nx.Graph()
    graph.add_node("pod_2_gpu_nodes_1", layer_index=0, group_label="pod_2")
    graph.add_node("pod_10_gpu_nodes_1", layer_index=0, group_label="pod_10")
    graph.add_node("backend__pod_2_leaf_1", layer_index=1, group_label="pod_2")
    graph.add_node("backend__pod_10_leaf_1", layer_index=1, group_label="pod_10")
    graph.add_edge(
        "pod_10_gpu_nodes_1",
        "backend__pod_10_leaf_1",
        source_ports=[1],
        target_ports=[1],
        source_lane_units_per_cable=1,
        target_lane_units_per_cable=1,
        num_cables=1,
        cable_bandwidth_gb=400,
    )
    graph.add_edge(
        "pod_2_gpu_nodes_1",
        "backend__pod_2_leaf_1",
        source_ports=[1],
        target_ports=[1],
        source_lane_units_per_cable=1,
        target_lane_units_per_cable=1,
        num_cables=1,
        cable_bandwidth_gb=400,
    )

    rows = extract_port_mapping_rows(graph)

    assert [row["source_node_id"] for row in rows] == [
        "pod_2_gpu_nodes_1",
        "pod_10_gpu_nodes_1",
    ]
