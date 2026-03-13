import pytest
import yaml

from topology_generator.config_schema import InvalidTopologyConfig, TopologyConfig
from topology_generator.file_handler import ensure_output_dir, load_config_from_file


def test_load_config_from_file_returns_validated_mapping(sample_config_file, sample_config):
    loaded_config = load_config_from_file(str(sample_config_file))

    assert isinstance(loaded_config, TopologyConfig)
    assert loaded_config == sample_config
    assert loaded_config["layers"][0]["name"] == "compute"
    assert loaded_config.layer(1).node_count_in_layer == 2


def test_load_config_from_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        load_config_from_file("nonexistent_file.yaml")


def test_load_config_from_invalid_yaml(tmp_path):
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("layers: [", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        load_config_from_file(str(config_file))


def test_load_config_rejects_missing_layers_key(tmp_path):
    config_file = tmp_path / "invalid.yaml"
    yaml.safe_dump({"foo": []}, config_file.open("w", encoding="utf-8"))

    with pytest.raises(InvalidTopologyConfig, match="layers must be a list"):
        load_config_from_file(str(config_file))


def test_load_config_rejects_reciprocity_mismatch(tmp_path, sample_config):
    config_file = tmp_path / "invalid.yaml"
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_layers[1]["downlink_cables_per_node_to_each_node_in_previous_layer"] = 2
    invalid_config["layers"] = invalid_layers
    yaml.safe_dump(invalid_config, config_file.open("w", encoding="utf-8"))

    with pytest.raises(InvalidTopologyConfig, match="agree on link counts"):
        load_config_from_file(str(config_file))


def test_load_config_rejects_invalid_boundary_direction_values(tmp_path, sample_two_layer_config):
    config_file = tmp_path / "invalid.yaml"
    invalid_config = dict(sample_two_layer_config)
    invalid_layers = [dict(layer) for layer in sample_two_layer_config["layers"]]
    invalid_layers[0]["downlink_cables_per_node_to_each_node_in_previous_layer"] = 1
    invalid_layers[0]["downlink_cable_bandwidth_gb"] = 10
    invalid_config["layers"] = invalid_layers
    yaml.safe_dump(invalid_config, config_file.open("w", encoding="utf-8"))

    with pytest.raises(InvalidTopologyConfig, match="cannot define non-zero downlink"):
        load_config_from_file(str(config_file))


def test_load_config_rejects_cable_bandwidth_above_port_bandwidth(tmp_path, sample_two_layer_config):
    config_file = tmp_path / "invalid.yaml"
    invalid_config = dict(sample_two_layer_config)
    invalid_layers = [dict(layer) for layer in sample_two_layer_config["layers"]]
    invalid_layers[0]["uplink_cable_bandwidth_gb"] = 30
    invalid_layers[1]["downlink_cable_bandwidth_gb"] = 30
    invalid_config["layers"] = invalid_layers
    yaml.safe_dump(invalid_config, config_file.open("w", encoding="utf-8"))

    with pytest.raises(InvalidTopologyConfig, match="exceeds"):
        load_config_from_file(str(config_file))


def test_load_config_rejects_insufficient_ports_for_dense_adjacency(tmp_path, sample_config):
    config_file = tmp_path / "invalid.yaml"
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_layers[1]["ports_per_node"] = 3
    invalid_config["layers"] = invalid_layers
    yaml.safe_dump(invalid_config, config_file.open("w", encoding="utf-8"))

    with pytest.raises(InvalidTopologyConfig, match="insufficient"):
        load_config_from_file(str(config_file))


def test_load_config_defaults_missing_layer_name(tmp_path, sample_two_layer_config):
    config_file = tmp_path / "valid.yaml"
    valid_config = dict(sample_two_layer_config)
    valid_layers = [dict(layer) for layer in sample_two_layer_config["layers"]]
    valid_layers[0].pop("name")
    valid_config["layers"] = valid_layers
    yaml.safe_dump(valid_config, config_file.open("w", encoding="utf-8"))

    loaded_config = load_config_from_file(str(config_file))

    assert loaded_config.layer(0).name == "layer_0"


def test_ensure_output_dir_creates_directory(tmp_path):
    output_dir = tmp_path / "nested" / "outputs"

    returned_path = ensure_output_dir(str(output_dir))

    assert returned_path == output_dir
    assert output_dir.exists()
