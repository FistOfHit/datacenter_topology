import networkx as nx
import pandas as pd

from topology_generator.port_mapper import (
    PORT_MAPPING_COLUMNS,
    create_port_mapping,
    extract_port_mapping_rows,
    save_to_excel,
)


def test_extract_port_mapping_rows_preserves_layer_orientation():
    graph = nx.Graph()
    graph.add_node("aggregation_1", layer_index=1)
    graph.add_node("compute_1", layer_index=0)
    graph.add_edge(
        "aggregation_1",
        "compute_1",
        source_ports=[3],
        target_ports=[1],
        num_cables=1,
        cable_bandwidth_gb=400,
    )

    rows = extract_port_mapping_rows(graph)

    assert rows == [
        {
            "source_serial_number": None,
            "source_node_id": "compute_1",
            "source_node_port": 1,
            "target_node_port": 3,
            "target_node_id": "aggregation_1",
            "target_serial_number": None,
            "cable_number": 1,
        }
    ]


def test_create_port_mapping_returns_expected_dataframe(sample_config):
    from topology_generator.topology_generator import generate_topology

    df = create_port_mapping(generate_topology(sample_config))

    assert list(df.columns) == PORT_MAPPING_COLUMNS
    assert len(df) == 9
    assert df.iloc[0].to_dict() == {
        "source_serial_number": None,
        "source_node_id": "compute_1",
        "source_node_port": 1,
        "target_node_port": 1,
        "target_node_id": "aggregation_1",
        "target_serial_number": None,
        "cable_number": 1,
    }
    assert df.iloc[-1].to_dict() == {
        "source_serial_number": None,
        "source_node_id": "fabric_1",
        "source_node_port": 5,
        "target_node_port": 1,
        "target_node_id": "core_1",
        "target_serial_number": None,
        "cable_number": 9,
    }


def test_save_to_excel_writes_file(tmp_path):
    df = pd.DataFrame(
        [
            {
                "source_serial_number": None,
                "source_node_id": "node1",
                "source_node_port": 1,
                "target_node_port": 1,
                "target_node_id": "node2",
                "target_serial_number": None,
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
