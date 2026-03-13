from argparse import Namespace

from topology_generator.logger import LOGGER_NAME, setup_logging


def test_setup_logging_creates_log_file(tmp_path):
    args = Namespace(output_dir=str(tmp_path / "logs"))

    logger = setup_logging(args)
    logger.info("hello topology")
    for handler in logger.handlers:
        handler.flush()

    log_file = tmp_path / "logs" / "network_topology.log"
    assert logger.name == LOGGER_NAME
    assert log_file.exists()
    assert "hello topology" in log_file.read_text(encoding="utf-8")


def test_setup_logging_replaces_existing_handlers(tmp_path):
    args = Namespace(output_dir=str(tmp_path / "logs"))

    first_logger = setup_logging(args)
    first_logger.info("first run")
    second_logger = setup_logging(args)
    second_logger.info("second run")
    for handler in second_logger.handlers:
        handler.flush()

    log_contents = (tmp_path / "logs" / "network_topology.log").read_text(
        encoding="utf-8"
    )
    assert first_logger is second_logger
    assert len(second_logger.handlers) == 2
    assert "second run" in log_contents
