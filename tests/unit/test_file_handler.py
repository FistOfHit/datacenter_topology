import pytest
import yaml

from topology_generator.config_schema import InvalidTopologyConfig, TopologyConfig
from topology_generator.file_handler import ensure_output_dir, load_config_from_file


def test_load_config_from_file_returns_validated_mapping(sample_config_file, sample_config):
    loaded_config = load_config_from_file(str(sample_config_file))

    assert isinstance(loaded_config, TopologyConfig)
    assert loaded_config == sample_config
    assert loaded_config["groups"][0]["name"] == "pod"
    assert loaded_config.layer("leaf").placement == "pod"


def test_load_config_from_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        load_config_from_file("nonexistent_file.yaml")


def test_load_config_from_invalid_yaml(tmp_path):
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("layers: [", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        load_config_from_file(str(config_file))


def test_load_config_from_empty_file_reports_precise_error(tmp_path):
    config_file = tmp_path / "empty.yaml"
    config_file.write_text("", encoding="utf-8")

    with pytest.raises(InvalidTopologyConfig, match="non-empty mapping"):
        load_config_from_file(str(config_file))


def test_load_config_rejects_missing_layers_key(tmp_path):
    config_file = tmp_path / "invalid.yaml"
    yaml.safe_dump({"groups": [], "links": []}, config_file.open("w", encoding="utf-8"))

    with pytest.raises(InvalidTopologyConfig, match="layers must be a list"):
        load_config_from_file(str(config_file))


def test_load_config_rejects_invalid_group_placement(tmp_path, sample_config):
    config_file = tmp_path / "invalid.yaml"
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_layers[0]["placement"] = "unit"
    invalid_config["layers"] = invalid_layers
    yaml.safe_dump(invalid_config, config_file.open("w", encoding="utf-8"))

    with pytest.raises(InvalidTopologyConfig, match="placement must be 'global'"):
        load_config_from_file(str(config_file))


def test_load_config_rejects_non_adjacent_links(tmp_path, sample_config):
    config_file = tmp_path / "invalid.yaml"
    invalid_config = dict(sample_config)
    invalid_links = [dict(link) for link in sample_config["links"]]
    invalid_links[0]["to"] = "spine"
    invalid_config["links"] = invalid_links
    yaml.safe_dump(invalid_config, config_file.open("w", encoding="utf-8"))

    with pytest.raises(InvalidTopologyConfig, match="Links are only allowed between adjacent layers"):
        load_config_from_file(str(config_file))


def test_load_config_rejects_policy_placement_mismatch(tmp_path, sample_config):
    config_file = tmp_path / "invalid.yaml"
    invalid_config = dict(sample_config)
    invalid_links = [dict(link) for link in sample_config["links"]]
    invalid_links[1]["policy"] = "within_group_full_mesh"
    invalid_config["links"] = invalid_links
    yaml.safe_dump(invalid_config, config_file.open("w", encoding="utf-8"))

    with pytest.raises(InvalidTopologyConfig, match="within_group_full_mesh requires both layers"):
        load_config_from_file(str(config_file))


def test_ensure_output_dir_creates_directory(tmp_path):
    output_dir = tmp_path / "nested" / "outputs"

    returned_path = ensure_output_dir(str(output_dir))

    assert returned_path == output_dir
    assert output_dir.exists()
