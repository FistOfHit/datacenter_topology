import networkx as nx
from pathlib import Path


def export_network_to_vdx(G: nx.Graph, output_file: str):
    """
    Export network topology to Visio VDX format with explicit shape geometry.
    """
    content = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    content += '<VisioDocument xmlns="http://schemas.microsoft.com/visio/2003/core">\n'

    # Add a rectangle master shape definition
    content += "  <Masters>\n"
    content += '    <Master ID="0" Name="Rectangle">\n'
    content += "      <Shapes>\n"
    content += '        <Shape Type="Shape">\n'
    content += "          <Geom>\n"
    content += "            <MoveTo><X>0</X><Y>0</Y></MoveTo>\n"
    content += "            <LineTo><X>1</X><Y>0</Y></LineTo>\n"
    content += "            <LineTo><X>1</X><Y>1</Y></LineTo>\n"
    content += "            <LineTo><X>0</X><Y>1</Y></LineTo>\n"
    content += "            <LineTo><X>0</X><Y>0</Y></LineTo>\n"
    content += "          </Geom>\n"
    content += "        </Shape>\n"
    content += "      </Shapes>\n"
    content += "    </Master>\n"
    content += "  </Masters>\n"

    content += "  <Pages>\n"
    content += '    <Page ID="0" Name="Page-1">\n'
    content += "      <PageSheet>\n"
    content += "        <PageProps>\n"
    content += "          <PageWidth>11</PageWidth>\n"
    content += "          <PageHeight>8.5</PageHeight>\n"
    content += "        </PageProps>\n"
    content += "      </PageSheet>\n"
    content += "      <Shapes>\n"

    # Define layout parameters
    layers = {"core": 8, "spine": 6, "leaf": 4, "server": 2}
    colors = {
        "core": "#FFB6C1",
        "spine": "#FFB6C1",
        "leaf": "#90EE90",
        "server": "#ADD8E6",
    }

    # Group nodes by type and store positions
    nodes_by_type = {}
    node_positions = {}
    for node, attrs in G.nodes(data=True):
        node_type = attrs["type"]
        if node_type not in nodes_by_type:
            nodes_by_type[node_type] = []
        nodes_by_type[node_type].append((node, attrs))

    # Add nodes with explicit geometry
    shape_id = 1
    for node_type, nodes in nodes_by_type.items():
        y_pos = layers[node_type]
        num_nodes = len(nodes)

        for idx, (node, attrs) in enumerate(nodes):
            x_pos = 2 + (8 * (idx + 1) / (num_nodes + 1))
            node_positions[node] = (x_pos, y_pos)
            attrs["shape_id"] = shape_id

            ports_text = f"{attrs['used_ports_equivalent']}/{attrs['total_ports']}"
            bandwidth_text = (
                f"{attrs['used_bandwidth_gb']}/{attrs['aggregate_bandwidth_gb']}G"
            )

            content += f"""        <Shape ID="{shape_id}" Type="Shape" Master="0">
          <XForm>
            <PinX>{x_pos}</PinX>
            <PinY>{y_pos}</PinY>
            <Width>1.5</Width>
            <Height>0.75</Height>
            <LocPinX>0.75</LocPinX>
            <LocPinY>0.375</LocPinY>
          </XForm>
          <Fill>
            <FillForegnd>{colors[node_type]}</FillForegnd>
            <FillBkgnd>#FFFFFF</FillBkgnd>
            <FillPattern>1</FillPattern>
          </Fill>
          <Line>
            <LineWeight>0.01</LineWeight>
            <LineColor>#000000</LineColor>
            <LinePattern>1</LinePattern>
          </Line>
          <Geom>
            <MoveTo><X>0</X><Y>0</Y></MoveTo>
            <LineTo><X>1.5</X><Y>0</Y></LineTo>
            <LineTo><X>1.5</X><Y>0.75</Y></LineTo>
            <LineTo><X>0</X><Y>0.75</Y></LineTo>
            <LineTo><X>0</X><Y>0</Y></LineTo>
          </Geom>
          <Para/>
          <Text>{node}\n{ports_text}\n{bandwidth_text}</Text>
        </Shape>\n"""

            shape_id += 1

    content += "      </Shapes>\n"
    content += "      <Connects>\n"

    # Add edges with explicit paths
    for source, target, attrs in G.edges(data=True):
        source_id = G.nodes[source]["shape_id"]
        target_id = G.nodes[target]["shape_id"]
        source_pos = node_positions[source]
        target_pos = node_positions[target]

        line_color = "#000000" if attrs["cable_bandwidth_gb"] == 400 else "#FF69B4"

        content += f"""        <Connect FromSheet="{source_id}" ToSheet="{target_id}">
          <Line>
            <LineWeight>0.01</LineWeight>
            <LineColor>{line_color}</LineColor>
            <LinePattern>1</LinePattern>
            <BeginArrow>0</BeginArrow>
            <EndArrow>0</EndArrow>
          </Line>
          <Geom>
            <MoveTo><X>{source_pos[0]}</X><Y>{source_pos[1]}</Y></MoveTo>
            <LineTo><X>{target_pos[0]}</X><Y>{target_pos[1]}</Y></LineTo>
          </Geom>
        </Connect>\n"""

    content += "      </Connects>\n"
    content += "    </Page>\n"
    content += "  </Pages>\n"
    content += "</VisioDocument>"

    try:
        with open(
            Path(output_file).joinpath("topology.vdx"), "w", encoding="utf-8"
        ) as f:
            f.write(content)
        print(f"Successfully exported to: {output_file}")

        # Verify file completeness
        with open(
            Path(output_file).joinpath("topology.vdx"), "r", encoding="utf-8"
        ) as f:
            content = f.read()
            if not content.endswith("</VisioDocument>"):
                print("Warning: File appears to be truncated!")
            else:
                print(f"File size: {len(content)} bytes")
    except Exception as e:
        print(f"Error exporting to VDX: {e}")
