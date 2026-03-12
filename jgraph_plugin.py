"""
JGraph Analysis QGIS Plugin

Runs j-graph (justified graph / Space Syntax) analysis on a point layer
(nodes = spaces) and a line layer (edges = connections), writing integration
metrics back to the node layer as new attributes.
"""

import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsVectorLayer, QgsVectorDataProvider, QgsField, QgsFeature,
    QgsGeometry, QgsPointXY, QgsProject, QgsWkbTypes, edit
)
from qgis.PyQt.QtCore import QVariant

from .jgraph_dialog import JGraphDialog
from .jgraph_analysis import (
    run_analysis, match_line_endpoints_to_nodes,
    build_graph, compute_jgraph_layout
)

# Fields written to the node layer
OUTPUT_FIELDS = [
    ("jg_depth", QVariant.Int,    "Depth from Base Node"),
    ("jg_td",    QVariant.Double, "Total Depth (global)"),
    ("jg_nc",    QVariant.Int,    "Connected Node Count"),
    ("jg_md",    QVariant.Double, "Mean Depth"),
    ("jg_ra",    QVariant.Double, "Relative Asymmetry"),
    ("jg_rra",   QVariant.Double, "Real Relative Asymmetry"),
    ("jg_int",   QVariant.Double, "Integration (1/RRA)"),
]

RESULT_KEYS = {
    "jg_td":  "total_depth",
    "jg_nc":  "node_count",
    "jg_md":  "mean_depth",
    "jg_ra":  "ra",
    "jg_rra": "rra",
    "jg_int": "integration",
}


class JGraphPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.action = QAction(QIcon(icon_path), "J-Graph Analysis", self.iface.mainWindow())
        self.action.setToolTip("Run justified graph (Space Syntax) analysis")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&J-Graph", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu("&J-Graph", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        dlg = JGraphDialog(self.iface.mainWindow())
        if not dlg.exec_():
            return

        node_layer = dlg.get_node_layer()
        edge_layer = dlg.get_edge_layer()
        tolerance = dlg.get_tolerance()
        overwrite = dlg.get_overwrite()

        if node_layer is None or edge_layer is None:
            QMessageBox.warning(None, "J-Graph", "Please select both a node layer and an edge layer.")
            return

        base_fid = dlg.get_base_node_fid()
        generate_layout = dlg.get_generate_layout()

        try:
            self._run_analysis(node_layer, edge_layer, tolerance, overwrite, base_fid, generate_layout, dlg)
        except Exception as e:
            QMessageBox.critical(None, "J-Graph Error", str(e))
            raise

    def _run_analysis(self, node_layer, edge_layer, tolerance, overwrite, base_fid, generate_layout, dlg):
        # --- Check for projected CRS ---
        node_crs = node_layer.crs()
        if node_crs.isGeographic():
            QMessageBox.warning(
                None, "J-Graph",
                f"The node layer '{node_layer.name()}' uses a geographic CRS "
                f"({node_crs.authid()}).\n\n"
                "J-Graph analysis requires a projected CRS so that distances "
                "are in linear units (metres, feet, etc.).\n\n"
                "Please reproject your layers first:\n"
                "  Processing → Toolbox → Reproject Layer"
            )
            return

        # --- Collect node geometries ---
        node_geoms = {}   # fid -> QgsPointXY
        for feat in node_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            pt = geom.asPoint()
            node_geoms[feat.id()] = pt

        if not node_geoms:
            QMessageBox.warning(None, "J-Graph", "Node layer has no valid point features.")
            return

        # --- Check layer is editable ---
        caps = node_layer.dataProvider().capabilities()
        if not (caps & QgsVectorDataProvider.AddAttributes and
                caps & QgsVectorDataProvider.ChangeAttributeValues):
            QMessageBox.warning(
                None, "J-Graph",
                f"The node layer '{node_layer.name()}' does not support editing.\n\n"
                "Please save your layer as a GeoPackage or Shapefile first:\n"
                "Right-click the layer → Export → Save Features As."
            )
            return

        # --- Validate base node ---
        if base_fid is None or base_fid not in node_geoms:
            QMessageBox.warning(None, "J-Graph", "Selected base node was not found in the node layer.")
            return

        # --- Collect edge geometries ---
        edge_geoms = {}   # fid -> list of QgsPointXY (polyline vertices)
        for feat in edge_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            if QgsWkbTypes.isMultiType(geom.wkbType()):
                parts = geom.asMultiPolyline()
                if parts:
                    edge_geoms[feat.id()] = parts[0]
            else:
                edge_geoms[feat.id()] = geom.asPolyline()

        if not edge_geoms:
            QMessageBox.warning(None, "J-Graph", "Edge layer has no valid line features.")
            return

        # --- Match line endpoints to nodes ---
        edge_triples = match_line_endpoints_to_nodes(node_geoms, edge_geoms, tolerance)
        edge_pairs = [(a, b) for a, b, _ in edge_triples]
        # Map sorted node pair -> original edge fid for attribute inheritance
        edge_line_map = {tuple(sorted([a, b])): lid for a, b, lid in edge_triples}

        if not edge_pairs:
            QMessageBox.warning(
                None, "J-Graph",
                f"No edges could be matched to nodes within tolerance {tolerance}.\n"
                "Try increasing the snap tolerance or check that line endpoints "
                "coincide with node points."
            )
            return

        # --- Build graph once ---
        node_ids = list(node_geoms.keys())
        graph = build_graph(node_ids, edge_pairs)

        # --- Depth from base node (BFS from root) ---
        depth_from_root = self._bfs_depths(graph, base_fid)

        # --- Global integration (BFS from every node) ---
        results = run_analysis(node_ids, edge_pairs)

        # --- Ensure output fields exist on node layer ---
        self._ensure_fields(node_layer, overwrite)

        # --- Write results back to node layer ---
        field_names = [f[0] for f in OUTPUT_FIELDS]
        field_indices = {name: node_layer.fields().indexFromName(name) for name in field_names}

        total = len(results)
        dlg.set_progress(0, total)

        with edit(node_layer):
            for i, (fid, metrics) in enumerate(results.items()):
                attrs = {}

                # Depth from base node
                depth_idx = field_indices.get("jg_depth", -1)
                if depth_idx >= 0:
                    d = depth_from_root.get(fid)
                    attrs[depth_idx] = int(d) if d is not None else None

                # Global metrics
                for field_name, result_key in RESULT_KEYS.items():
                    idx = field_indices.get(field_name, -1)
                    if idx >= 0:
                        val = metrics.get(result_key)
                        attrs[idx] = float(val) if val is not None else None

                node_layer.changeAttributeValues(fid, attrs)
                dlg.set_progress(i + 1, total)

        node_layer.triggerRepaint()

        # --- Generate layout layers ---
        if generate_layout:
            base_pt = node_geoms[base_fid]
            self._create_layout_layers(graph, depth_from_root, edge_pairs, results,
                                       origin=(base_pt.x(), base_pt.y()),
                                       node_layer=node_layer, edge_layer=edge_layer,
                                       edge_line_map=edge_line_map)

        # --- Summary ---
        reachable = sum(1 for d in depth_from_root.values() if d is not None)
        integrated = sum(1 for r in results.values() if r.get("integration") is not None)
        layout_note = "\n  Layout layers added to project." if generate_layout else ""
        QMessageBox.information(
            None, "J-Graph Complete",
            f"Analysis complete.\n"
            f"  Nodes processed:         {len(results)}\n"
            f"  Edges matched:           {len(edge_pairs)}\n"
            f"  Reachable from base:     {reachable}\n"
            f"  Nodes with integration:  {integrated}\n\n"
            f"Fields written to '{node_layer.name()}':\n"
            f"  jg_depth, jg_td, jg_nc, jg_md, jg_ra, jg_rra, jg_int"
            f"{layout_note}"
        )

    @staticmethod
    def _bfs_depths(graph, root):
        """
        BFS from root. Returns dict { node_id: depth } for all reachable nodes.
        Unreachable nodes get None.
        """
        from collections import deque
        depths = {nid: None for nid in graph}
        depths[root] = 0
        queue = deque([root])
        while queue:
            current = queue.popleft()
            for neighbor in graph[current]:
                if depths[neighbor] is None:
                    depths[neighbor] = depths[current] + 1
                    queue.append(neighbor)
        return depths

    def _create_layout_layers(self, graph, depth_from_root, edge_pairs, results, origin=(0.0, 0.0),
                              node_layer=None, edge_layer=None, edge_line_map=None):
        """
        Create two temporary memory layers showing the j-graph as a classic
        tree diagram: base node stays at its real geographic location,
        other nodes arranged in rows by depth above it.

        All attributes from the original node and edge layers are inherited.
        """
        positions = compute_jgraph_layout(graph, depth_from_root, origin=origin)
        if not positions:
            return

        # --- Build lookup dicts for original features ---
        orig_node_feats = {}
        if node_layer is not None:
            for feat in node_layer.getFeatures():
                orig_node_feats[feat.id()] = feat

        orig_edge_feats = {}
        if edge_layer is not None:
            for feat in edge_layer.getFeatures():
                orig_edge_feats[feat.id()] = feat

        # --- Node layout layer ---
        crs_id = node_layer.crs().authid() if node_layer is not None else "EPSG:4326"
        node_vl = QgsVectorLayer(f"Point?crs={crs_id}", "J-Graph Layout — Nodes", "memory")
        node_pr = node_vl.dataProvider()

        # Build field list: original node fields (already include jg_* written earlier) + node_fid
        node_fields = []
        orig_node_field_names = set()
        if node_layer is not None:
            for f in node_layer.fields():
                node_fields.append(QgsField(f.name(), f.type(), f.typeName(),
                                            f.length(), f.precision()))
                orig_node_field_names.add(f.name())
        if "node_fid" not in orig_node_field_names:
            node_fields.append(QgsField("node_fid", QVariant.Int))
        # Fallback jg fields when no original layer provided
        if node_layer is None:
            node_fields += [
                QgsField("node_fid", QVariant.Int),
                QgsField("jg_depth", QVariant.Int),
                QgsField("jg_int",   QVariant.Double),
                QgsField("jg_td",    QVariant.Double),
                QgsField("jg_md",    QVariant.Double),
                QgsField("jg_ra",    QVariant.Double),
                QgsField("jg_rra",   QVariant.Double),
            ]

        node_pr.addAttributes(node_fields)
        node_vl.updateFields()

        node_features = []
        for fid, (x, y) in positions.items():
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))

            if node_layer is not None:
                orig = orig_node_feats.get(fid)
                attrs = list(orig.attributes()) if orig is not None else [None] * len(node_layer.fields())
                if "node_fid" not in orig_node_field_names:
                    attrs.append(fid)
            else:
                m = results.get(fid, {})
                d = depth_from_root.get(fid)
                attrs = [
                    fid,
                    int(d) if d is not None else None,
                    m.get("integration"),
                    m.get("total_depth"),
                    m.get("mean_depth"),
                    m.get("ra"),
                    m.get("rra"),
                ]

            feat.setAttributes(attrs)
            node_features.append(feat)

        node_pr.addFeatures(node_features)
        node_vl.updateExtents()

        # --- Edge layout layer ---
        edge_vl = QgsVectorLayer(f"LineString?crs={crs_id}", "J-Graph Layout — Edges", "memory")
        edge_pr = edge_vl.dataProvider()

        # Build field list: original edge fields + from_fid / to_fid identifiers
        edge_fields = []
        orig_edge_field_names = set()
        if edge_layer is not None:
            for f in edge_layer.fields():
                edge_fields.append(QgsField(f.name(), f.type(), f.typeName(),
                                            f.length(), f.precision()))
                orig_edge_field_names.add(f.name())
        if "from_fid" not in orig_edge_field_names:
            edge_fields.append(QgsField("from_fid", QVariant.Int))
        if "to_fid" not in orig_edge_field_names:
            edge_fields.append(QgsField("to_fid", QVariant.Int))
        if edge_layer is None:
            edge_fields = [QgsField("from_fid", QVariant.Int), QgsField("to_fid", QVariant.Int)]

        edge_pr.addAttributes(edge_fields)
        edge_vl.updateFields()

        seen = set()
        edge_features = []
        for a, b in edge_pairs:
            key = tuple(sorted([a, b]))
            if key in seen:
                continue
            if a not in positions or b not in positions:
                continue
            seen.add(key)

            if edge_layer is not None:
                orig_eid = edge_line_map.get(key) if edge_line_map else None
                orig = orig_edge_feats.get(orig_eid) if orig_eid is not None else None
                attrs = list(orig.attributes()) if orig is not None else [None] * len(edge_layer.fields())
                if "from_fid" not in orig_edge_field_names:
                    attrs.append(a)
                if "to_fid" not in orig_edge_field_names:
                    attrs.append(b)
            else:
                attrs = [a, b]

            ax, ay = positions[a]
            bx, by = positions[b]
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(ax, ay), QgsPointXY(bx, by)]))
            feat.setAttributes(attrs)
            edge_features.append(feat)

        edge_pr.addFeatures(edge_features)
        edge_vl.updateExtents()

        # Add edge layer first so nodes draw on top
        QgsProject.instance().addMapLayer(edge_vl)
        QgsProject.instance().addMapLayer(node_vl)

    def _ensure_fields(self, layer, overwrite):
        """Add output fields to layer if they don't exist.

        If *overwrite* is True and a field already exists, delete it first so
        it is re-created with the canonical type defined in OUTPUT_FIELDS.
        """
        provider = layer.dataProvider()
        existing = {f.name(): i for i, f in enumerate(layer.fields())}

        if overwrite:
            indices_to_delete = [existing[name] for name, _, _ in OUTPUT_FIELDS
                                 if name in existing]
            if indices_to_delete:
                provider.deleteAttributes(indices_to_delete)
                layer.updateFields()

        # Re-read after possible deletion
        existing = [f.name() for f in layer.fields()]
        new_fields = []
        for name, vtype, _ in OUTPUT_FIELDS:
            if name not in existing:
                new_fields.append(QgsField(name, vtype))

        if new_fields:
            provider.addAttributes(new_fields)
            layer.updateFields()
