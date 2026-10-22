"""
dialogs.py

Small dialogs used by MainWindow. Currently just the NetCDF export
dialog - pick a variable, a date range, and an output path.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QFileDialog,
)


class ExportDialog(QDialog):
    def __init__(self, dataset, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export NetCDF")
        self.dataset = dataset

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.variable_combo = QComboBox()
        self.variable_combo.addItems(dataset.variables)
        if dataset.current_variable in dataset.variables:
            self.variable_combo.setCurrentText(dataset.current_variable)
        form.addRow("Variable", self.variable_combo)

        self.start_combo = QComboBox()
        self.end_combo = QComboBox()
        date_labels = [d.strftime("%Y-%m-%d") for d in dataset.dates]
        self.start_combo.addItems(date_labels)
        self.end_combo.addItems(date_labels)
        if date_labels:
            self.end_combo.setCurrentIndex(len(date_labels) - 1)
        form.addRow("Start date", self.start_combo)
        form.addRow("End date", self.end_combo)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)
        form.addRow("Output file", path_row)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save NetCDF", "", "*.nc")
        if filename:
            if not filename.endswith(".nc"):
                filename += ".nc"
            self.path_edit.setText(filename)

    def values(self):
        """Returns (variable, start_date, end_date, output_path)."""
        variable = self.variable_combo.currentText()
        dates = self.dataset.dates
        start_idx = self.start_combo.currentIndex()
        end_idx = self.end_combo.currentIndex()
        start_date = dates[start_idx]
        end_date = dates[end_idx]
        return variable, start_date, end_date, self.path_edit.text()
