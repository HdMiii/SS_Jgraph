from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDoubleSpinBox, QPushButton, QCheckBox, QGroupBox,
    QDialogButtonBox, QProgressBar, QMessageBox, QFormLayout,
    QSpinBox
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsMapLayerProxyModel, QgsWkbTypes, QgsFeatureRequest
from qgis.gui import QgsMapLayerComboBox


class JGraphDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("J-Graph Analysis")
        self.setMinimumWidth(440)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Layer selection ---
        layer_group = QGroupBox("Input Layers")
        form = QFormLayout(layer_group)

        self.node_layer_combo = QgsMapLayerComboBox()
        self.node_layer_combo.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.node_layer_combo.layerChanged.connect(self._on_node_layer_changed)
        form.addRow("Node layer (points):", self.node_layer_combo)

        self.edge_layer_combo = QgsMapLayerComboBox()
        self.edge_layer_combo.setFilters(QgsMapLayerProxyModel.LineLayer)
        form.addRow("Edge layer (lines):", self.edge_layer_combo)

        layout.addWidget(layer_group)

        # --- Base node ---
        root_group = QGroupBox("Base (Root) Node")
        root_form = QFormLayout(root_group)

        root_note = QLabel(
            "The base node is the origin of the justified graph (e.g. 'outside' or entrance).\n"
            "Depth of every other node is measured from here."
        )
        root_note.setStyleSheet("color: #555; font-size: 11px;")
        root_note.setWordWrap(True)
        root_form.addRow(root_note)

        # Label field selector
        self.label_field_combo = QComboBox()
        self.label_field_combo.addItem("— feature ID —", userData=None)
        self.label_field_combo.currentIndexChanged.connect(self._on_label_field_changed)
        root_form.addRow("Identify nodes by:", self.label_field_combo)

        # Base node value selector
        self.base_node_combo = QComboBox()
        self.base_node_combo.setEditable(False)
        root_form.addRow("Base node:", self.base_node_combo)

        layout.addWidget(root_group)

        # --- Options ---
        opt_group = QGroupBox("Options")
        opt_form = QFormLayout(opt_group)

        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setDecimals(6)
        self.tolerance_spin.setMinimum(0.0)
        self.tolerance_spin.setMaximum(1000.0)
        self.tolerance_spin.setValue(0.001)
        self.tolerance_spin.setToolTip(
            "Max distance between a line endpoint and a node point to be considered connected."
        )
        opt_form.addRow("Snap tolerance (map units):", self.tolerance_spin)

        self.overwrite_check = QCheckBox("Overwrite existing j-graph fields")
        self.overwrite_check.setChecked(True)
        opt_form.addRow(self.overwrite_check)

        self.layout_check = QCheckBox("Generate j-graph layout layers")
        self.layout_check.setChecked(True)
        self.layout_check.setToolTip(
            "Creates two new temporary layers showing the classic tree-like j-graph diagram,\n"
            "with the base node at the bottom and spaces arranged by depth level."
        )
        opt_form.addRow(self.layout_check)

        layout.addWidget(opt_group)

        # --- Output fields info ---
        info = QLabel(
            "Output fields added to node layer:\n"
            "  jg_depth — Depth from base node\n"
            "  jg_td    — Total Depth (global, from each node)\n"
            "  jg_nc    — Connected node count\n"
            "  jg_md    — Mean Depth\n"
            "  jg_ra    — Relative Asymmetry\n"
            "  jg_rra   — Real Relative Asymmetry\n"
            "  jg_int   — Integration (1/RRA)"
        )
        info.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(info)

        # --- Progress ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # --- Buttons ---
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.button(QDialogButtonBox.Ok).setText("Run Analysis")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Populate initial state
        self._on_node_layer_changed(self.node_layer_combo.currentLayer())

    def _on_node_layer_changed(self, layer):
        """Refresh the label field combo and base node list when node layer changes."""
        self.label_field_combo.blockSignals(True)
        self.label_field_combo.clear()
        self.label_field_combo.addItem("— feature ID —", userData=None)

        if layer is not None:
            for field in layer.fields():
                self.label_field_combo.addItem(field.name(), userData=field.name())

        self.label_field_combo.blockSignals(False)
        self._on_label_field_changed(0)

    def _on_label_field_changed(self, _index):
        """Repopulate base node combo based on selected label field."""
        self.base_node_combo.clear()
        layer = self.node_layer_combo.currentLayer()
        if layer is None:
            return

        field_name = self.label_field_combo.currentData()

        if field_name is None:
            # Use feature IDs
            for feat in layer.getFeatures():
                self.base_node_combo.addItem(f"FID {feat.id()}", userData=feat.id())
        else:
            seen = set()
            for feat in layer.getFeatures():
                val = feat[field_name]
                label = str(val) if val is not None else "(null)"
                if label not in seen:
                    seen.add(label)
                    self.base_node_combo.addItem(label, userData=feat.id())

    def get_node_layer(self):
        return self.node_layer_combo.currentLayer()

    def get_edge_layer(self):
        return self.edge_layer_combo.currentLayer()

    def get_tolerance(self):
        return self.tolerance_spin.value()

    def get_overwrite(self):
        return self.overwrite_check.isChecked()

    def get_generate_layout(self):
        return self.layout_check.isChecked()

    def get_base_node_fid(self):
        """Return the feature ID of the selected base node, or None."""
        return self.base_node_combo.currentData()

    def set_progress(self, value, maximum=100):
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)
