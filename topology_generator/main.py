from topology_generator import generate_topology
from visualiser import visualize_topology
from port_mapper import create_port_mapping, save_to_csv, save_to_excel
from graph_exporter import export_network_to_vdx
from logger import setup_logging
from argparser import parse_args
from file_handler import load_config_from_file


def main():
    args = parse_args()

    # Set up logging with the timestamped output directory
    logger = setup_logging(args)
    logger.info(f"Created output directory: {args.output_dir}")

    try:
        config = load_config_from_file(args.config)

        # Generate topology
        topology = generate_topology(config)
        logger.info("Successfully generated topology")

        # Visualize topology
        visualize_topology(topology, args.output_dir)
        logger.info("Successfully visualized topology")

        # Create a cut-sheet/port-mapping from the topology
        port_mapping = create_port_mapping(topology)
        # Save to CSV and Excel formats
        save_to_csv(port_mapping, args.output_dir)
        save_to_excel(port_mapping, args.output_dir)
        logger.info("Successfully created cut-sheet/port-mapping")

        # Export to Visio
        export_network_to_vdx(topology, args.output_dir)
        logger.info("Successfully exported topology to Visio")

    except Exception as e:
        logger.error(f"Error during execution: {str(e)}")
        raise


if __name__ == "__main__":
    main()
