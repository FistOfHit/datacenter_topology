import pandas as pd
import networkx as nx
import os


def create_port_mapping(G: nx.Graph) -> pd.DataFrame:
    """
    Create a port mapping from the network topology graph.

    Params:
        G: nx.Graph - The network topology graph.

    Returns:
        pd.DataFrame - The port mapping.
    """
    data = []
    cable_counter = 1

    for source, target, attrs in G.edges(data=True):
        source_node_id = source
        target_node_id = target

        # Extract port numbers from the lists
        source_ports = attrs.get("source_ports", [])
        target_ports = attrs.get("target_ports", [])

        for source_port, target_port in zip(source_ports, target_ports):
            data.append(
                {
                    "source_serial_number": None,
                    "source_node_id": source_node_id,
                    "source_node_port": source_port,
                    "target_node_port": target_port,
                    "target_node_id": target_node_id,
                    "target_serial_number": None,
                    "cable_number": cable_counter,
                }
            )
            cable_counter += 1

    df = pd.DataFrame(data)

    return df


def save_to_csv(df: pd.DataFrame, output_path: str, filename: str = "port_mapping.csv"):
    """
    Save the port mapping to a CSV file.

    Params:
        df (pd.DataFrame): The DataFrame containing the port mapping data.
        output_path (str): The directory path where the CSV file will be saved.
        filename (str, optional): The name of the CSV file. Defaults to "port_mapping.csv".
    """
    df.to_csv(os.path.join(output_path, filename), index=False)


def save_to_excel(
    df: pd.DataFrame, output_path: str, filename: str = "port_mapping.xlsx"
):
    """
    Save the port mapping to an Excel file.

    Params:
        df (pd.DataFrame): The DataFrame containing the port mapping data.
        output_path (str): The directory path where the Excel file will be saved.
        filename (str, optional): The name of the Excel file. Defaults to "port_mapping.xlsx".
    """
    df.to_excel(os.path.join(output_path, filename), index=False)
