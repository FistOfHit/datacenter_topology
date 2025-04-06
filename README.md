# Datacenter Network Topology Generator

A Python tool for generating, visualizing, and exporting datacenter network topologies.

## Overview

This project provides a flexible framework for creating and analyzing datacenter network topologies. It allows users to define various network parameters and generates a complete network topology with proper connections between different layers (servers, leaf switches, spine switches, and core switches).

## Features

- Generate multi-tier datacenter network topologies
- Visualize network topologies with matplotlib
- Export topologies to Visio (VDX) format
- Create port mappings and cut-sheets in CSV and Excel formats
- Calculate bandwidth and port utilization statistics

## Installation

### Prerequisites

- Python 3.12 or higher
- Required Python packages (installed automatically):
  - matplotlib
  - networkx
  - numpy
  - pandas
  - pyyaml
  - ruff

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/FistOfHit/datacenter_topology.git
   cd datacenter_topology
   ```

2. Install the package and dependencies:
   ```bash
   pip install -e .
   ```

3. (Optional) Set up pre-commit hooks for development:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Usage

### Basic Usage

Run the topology generator with the default configuration:

```bash
python -m topology_generator.main --config config.yaml
```

### Custom Configuration

Create a custom YAML configuration file and specify it when running:

```bash
python -m topology_generator.main --config custom_config.yaml --output-dir my_output
```

### Configuration Parameters

Example configuration (see `config.yaml` for a complete example):

```yaml
# Number of devices at each layer
num_server: 16
num_leaf: 4
num_spine: 2
num_core: 1

# Port bandwidth for each device type (in Gbps)
server_port_bandwidth_gb: 10
leaf_port_bandwidth_gb: 40
spine_port_bandwidth_gb: 100
core_port_bandwidth_gb: 100

# Connection parameters between layers
server_to_leaf_num_cables: 1
server_to_leaf_cable_bandwidth_gb: 10
leaf_to_spine_num_cables: 2
leaf_to_spine_cable_bandwidth_gb: 40
spine_to_core_num_cables: 2
spine_to_core_cable_bandwidth_gb: 100
```

## Output

The tool generates the following outputs in the specified output directory:

- `topology.png`: Visualization of the network topology
- `port_mapping.csv`: CSV file with port mapping details
- `port_mapping.xlsx`: Excel file with port mapping details
- `topology.vdx`: Visio file with the network topology
- Log files with detailed execution information

## Development

### Testing

This project uses pytest for testing. To run the tests:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=topology_generator tests/

# Run specific test files
pytest tests/unit/test_topology_generator.py
```

### Continuous Integration

This project uses GitHub Actions for continuous integration:

1. **Testing Workflow**: Automatically runs tests on Python 3.12 for all pushes to main and pull requests.
2. **Linting Workflow**: Checks code quality using ruff.

### Code Quality

We use several tools to maintain code quality:

1. **Ruff**: For linting and formatting Python code
2. **Pre-commit hooks**: To enforce code quality before commits
3. **MyPy**: For static type checking

To run linting manually:

```bash
ruff check .
ruff format .
```

### Pre-commit Hooks

The pre-commit configuration includes:

- Trailing whitespace removal
- End-of-file fixer
- YAML syntax checking
- Ruff linting and formatting (with auto-fixing enabled)
- MyPy type checking
- Poetry dependency checking
- Pytest automatic test running

To set up pre-commit hooks:

```bash
# If using pip
pip install pre-commit
pre-commit install

# If using Poetry (recommended)
poetry add --group dev pre-commit
poetry run pre-commit install
```

After installation, the hooks will run automatically on every commit. If you want to run them manually on all files:

```bash
pre-commit run --all-files
```

The hooks will automatically fix many issues for you, including code formatting and simple linting errors. This ensures that all code pushed to the repository meets the project's standards.

## Project Structure

```
datacenter_topology/
├── configs/               # Configuration examples
├── tests/                 # Test files
│   ├── unit/              # Unit tests for each module
│   └── test_integration.py # Integration tests
├── topology_generator/    # Main package
│   ├── __init__.py
│   ├── argparser.py       # Command-line argument parsing
│   ├── file_handler.py    # File operations
│   ├── graph_exporter.py  # Export to Visio format
│   ├── logger.py          # Logging setup
│   ├── main.py            # Main entry point
│   ├── port_mapper.py     # Port mapping generation
│   ├── statistics_generator.py # Statistics calculation
│   ├── topology_generator.py # Core topology generation
│   └── visualiser.py      # Visualization functions
├── .github/workflows/     # GitHub Actions CI configuration
├── .pre-commit-config.yaml # Pre-commit hooks configuration
├── config.yaml            # Default configuration
├── pyproject.toml         # Project metadata and tool configuration
└── README.md              # This file
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run the tests to make sure everything works (`pytest`)
4. Commit your changes (`git commit -m 'Add some amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
