# SS_Jgraph — Space Syntax J-Graph Analysis for QGIS

A QGIS plugin for **justified graph (j-graph) analysis** of building and urban layouts using Space Syntax methods. Given a point layer (spaces/rooms) and a line layer (connections), the plugin calculates topological depth and integration metrics for every node and writes them back as attributes.

---

## Background

The **justified graph** is a core technique in Space Syntax theory. A building or urban layout is represented as a graph where:

- **Nodes** = spaces (rooms, courtyards, streets, etc.)
- **Edges** = connections between spaces (doors, openings, passages)

The graph is "justified" from a chosen **base node** (typically "outside" or the main entrance), arranging all other spaces in levels by their topological distance from that root. This reveals the hierarchical access structure of the layout — which spaces are shallow (easily accessible) and which are deep (private or segregated).

This plugin is based on the methods described in:

> Hillier, B., Hanson, J. and Graham, H. (1987). Ideas are in things: an application of the space syntax method to discovering house genotypes. *Environment and Planning B: planning and design*, 14(4), pp.363–385.

---

## Features

- Select any point layer as nodes and any line layer as edges
- Choose a **base (root) node** by feature ID or by any attribute field (e.g. a `name` field labelled `"outside"`)
- Automatically snaps line endpoints to the nearest node within a configurable tolerance
- Writes six analysis fields directly to the node layer:

| Field | Description |
|-------|-------------|
| `jg_depth` | Topological depth from the base node |
| `jg_td` | Total Depth — sum of distances to all other nodes |
| `jg_nc` | Number of nodes reachable from this node |
| `jg_md` | Mean Depth — average distance to all other nodes |
| `jg_ra` | Relative Asymmetry |
| `jg_rra` | Real Relative Asymmetry (size-normalised) |
| `jg_int` | **Integration** — the primary Space Syntax metric (1/RRA) |

- Works with any QGIS-supported vector format (GeoPackage, Shapefile, etc.)

---

## Usage

### 1. Prepare your data

You need two vector layers:

- **Node layer** (point): one point per space. Optionally include a text field (e.g. `name`) to label the outside/entrance node.
- **Edge layer** (line): one line per connection. Each line must start and end at node point locations. Lines do not need to be straight — only the endpoints are used.

> **Important:** line endpoints must snap to node points. If they don't coincide exactly, use the **Snap tolerance** option in the dialog.

### 2. Run the analysis

1. Go to **J-Graph → J-Graph Analysis** in the menu bar (or click the toolbar icon)
2. Select your **node layer** and **edge layer**
3. In the **Base (Root) Node** section:
   - Choose which field to identify nodes by (or use feature ID)
   - Select the base node from the dropdown (e.g. your "outside" node)
4. Set the **snap tolerance** if your line endpoints don't sit exactly on node points
5. Click **Run Analysis**

Results are written to the node layer immediately. Use **Layer → Symbology** to colour nodes by `jg_int` to produce an integration heat map.

### 3. Interpreting results

- **`jg_depth`**: how many steps from the outside. Depth 1 = directly accessible from outside; higher values = more private/deep.
- **`jg_int`**: the headline metric. Higher = more integrated (easier to reach from the rest of the layout). Colour nodes from cool (low integration) to warm (high integration) to visualise movement potential.
- **`jg_rra`**: size-normalised, so integration values can be compared across buildings of different sizes.

---

## Requirements

- QGIS 3.0 or later
- Python 3 (bundled with QGIS)
- No additional Python packages required

---

## Repository

https://github.com/HdMiii/SS_Jgraph

---

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.
