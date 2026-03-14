from topology_generator.topology_generator import generate_topology
from topology_generator.visualiser import visualize_topology
from topology_generator.port_mapper import (
    create_port_mapping,
    save_to_excel,
)
from topology_generator.logger import setup_logging
from topology_generator.argparser import parse_args
from topology_generator.file_handler import ensure_output_dir, load_config_from_file


def main():
    """
    Main entry point for the network topology generator application.

    Orchestrates the entire workflow:
    1. Parse command line arguments
    2. Set up logging
    3. Load configuration
    4. Generate network topology
    5. Visualize the topology
    6. Create port mapping documentation
    7. Write generated outputs
    """
    # Parse command line arguments
    args = parse_args()
    ensure_output_dir(args.output_dir)

    # Set up logging with the output directory
    logger = setup_logging(args)
    logger.info(f"Created output directory: {args.output_dir}")

    try:
        # Load configuration from file
        config = load_config_from_file(args.config)

        # Generate network topology
        topology = generate_topology(config)
        logger.info("Successfully generated topology")

        # Visualize the topology
        visualize_topology(topology, args.output_dir)
        logger.info("Successfully visualized topology")

        # Create port mapping documentation
        port_mapping = create_port_mapping(topology)

        # Save the port mapping in Excel format
        save_to_excel(port_mapping, args.output_dir)
        logger.info("Successfully created cut-sheet/port-mapping")

    except Exception:
        logger.exception("Error during execution")
        raise


if __name__ == "__main__":
    main()
