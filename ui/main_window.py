from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFileDialog,
    QPushButton,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QCheckBox,
    QSlider,
)

import numpy as np

import config
from models.dataset import Dataset
from data_io.csv_reader import CSVReader
from data_io.shapefile_reader import ShapefileReader
from data_io.netcdf_writer import NetCDFWriter
from interpolation.grid import GridGenerator
from interpolation.idw import IDWInterpolator
from ui.map_canvas import MapCanvas
from ui.dialogs import ExportDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} v{config.VERSION}")
        self.resize(1300, 750)

        # Single persistent Dataset for the whole session - every load/
        # generate/interpolate action below updates it in place instead
        # of replacing it, so loading a new CSV never throws away an
        # already-loaded watershed, and vice versa.
        self.dataset = Dataset()

        self.csv_reader = CSVReader()
        self.shape_reader = ShapefileReader()
        self.grid_gen = GridGenerator(resolution=config.DEFAULT_GRID_SIZE)
        self.idw = IDWInterpolator(power=config.DEFAULT_IDW_POWER)
        self.netcdf_writer = NetCDFWriter()

        self._build_ui()
        self._update_controls_enabled()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        left = QVBoxLayout()
        left.addWidget(self._build_data_group())
        left.addWidget(self._build_layers_group())
        left.addWidget(self._build_grid_group())
        left.addWidget(self._build_interp_group())
        left.addWidget(self._build_date_group())
        left.addWidget(self._build_export_group())
        left.addStretch()

        left_container = QWidget()
        left_container.setLayout(left)
        left_container.setFixedWidth(280)

        self.canvas = MapCanvas()

        main_layout.addWidget(left_container)
        main_layout.addWidget(self.canvas, 1)

        self.statusBar().showMessage("Ready")

    # ------------------------------------------------------------------

    def _build_data_group(self):
        box = QGroupBox("Data")
        v = QVBoxLayout(box)

        self.btn_csv = QPushButton("Load CSV")
        self.btn_shp = QPushButton("Load Watershed")
        self.btn_remove_shp = QPushButton("Remove Watershed")

        self.lbl_csv_status = QLabel("No CSV loaded")
        self.lbl_shp_status = QLabel("No watershed loaded")
        for lbl in (self.lbl_csv_status, self.lbl_shp_status):
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: gray; font-size: 11px;")

        v.addWidget(self.btn_csv)
        v.addWidget(self.lbl_csv_status)
        v.addWidget(self.btn_shp)
        v.addWidget(self.btn_remove_shp)
        v.addWidget(self.lbl_shp_status)

        self.btn_csv.clicked.connect(self.load_csv)
        self.btn_shp.clicked.connect(self.load_shapefile)
        self.btn_remove_shp.clicked.connect(self.remove_watershed)

        return box

    # ------------------------------------------------------------------

    def _build_layers_group(self):
        """Each checkbox purely toggles visibility - it never recomputes
        anything, so switching layers on/off is instant."""
        box = QGroupBox("Layers")
        v = QVBoxLayout(box)

        self.chk_watershed = QCheckBox("Watershed boundary")
        self.chk_grid = QCheckBox("Grid mesh")
        self.chk_stations = QCheckBox("Stations")
        self.chk_raster = QCheckBox("Interpolated raster")
        self.chk_basemap = QCheckBox("Basemap (needs internet)")

        self.chk_watershed.setChecked(True)
        self.chk_grid.setChecked(True)
        self.chk_stations.setChecked(True)
        self.chk_raster.setChecked(True)
        self.chk_basemap.setChecked(config.BASEMAP_DEFAULT_ON)

        for chk in (self.chk_watershed, self.chk_grid, self.chk_stations, self.chk_raster):
            chk.toggled.connect(self._refresh_layers)
        self.chk_basemap.toggled.connect(self._refresh_basemap)

        for w in (
            self.chk_watershed, self.chk_grid, self.chk_stations,
            self.chk_raster, self.chk_basemap,
        ):
            v.addWidget(w)

        return box

    # ------------------------------------------------------------------

    def _build_grid_group(self):
        box = QGroupBox("Grid")
        v = QVBoxLayout(box)

        self.grid_size = QSpinBox()
        self.grid_size.setRange(10, 50000)
        self.grid_size.setValue(config.DEFAULT_GRID_SIZE)
        self.grid_size.setSingleStep(50)
        self.grid_size.setSuffix(" m")

        self.btn_grid = QPushButton("Generate Grid")
        self.btn_clear_grid = QPushButton("Clear Grid")

        v.addWidget(QLabel("Cell size"))
        v.addWidget(self.grid_size)
        v.addWidget(self.btn_grid)
        v.addWidget(self.btn_clear_grid)

        self.btn_grid.clicked.connect(self.generate_grid)
        self.btn_clear_grid.clicked.connect(self.clear_grid)

        return box

    # ------------------------------------------------------------------

    def _build_interp_group(self):
        box = QGroupBox("Interpolation")
        v = QVBoxLayout(box)

        self.variable = QComboBox()
        self.power = QDoubleSpinBox()
        self.power.setValue(config.DEFAULT_IDW_POWER)
        self.power.setRange(1, 10)
        self.power.setSingleStep(0.5)

        self.btn_interp = QPushButton("Interpolate")

        v.addWidget(QLabel("Variable"))
        v.addWidget(self.variable)
        v.addWidget(QLabel("IDW power"))
        v.addWidget(self.power)
        v.addWidget(self.btn_interp)

        self.variable.currentTextChanged.connect(self._on_variable_changed)
        self.btn_interp.clicked.connect(self.interpolate_current)

        return box

    # ------------------------------------------------------------------

    def _build_date_group(self):
        box = QGroupBox("Date")
        v = QVBoxLayout(box)

        self.lbl_date = QLabel("-")
        self.lbl_date.setAlignment(Qt.AlignCenter)

        nav = QHBoxLayout()
        self.btn_prev = QPushButton("< Previous")
        self.btn_next = QPushButton("Next >")
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)

        v.addWidget(self.lbl_date)
        v.addLayout(nav)
        v.addWidget(self.slider)

        self.btn_prev.clicked.connect(lambda: self._step_date(-1))
        self.btn_next.clicked.connect(lambda: self._step_date(1))
        self.slider.valueChanged.connect(self._on_slider_changed)

        return box

    # ------------------------------------------------------------------

    def _build_export_group(self):
        box = QGroupBox("Export")
        v = QVBoxLayout(box)
        self.btn_export = QPushButton("Export NetCDF...")
        self.btn_export.clicked.connect(self.export_netcdf)
        v.addWidget(self.btn_export)
        return box

    # ==================================================================
    # Data loading - each of these updates self.dataset IN PLACE, so
    # nothing already loaded gets thrown away.
    # ==================================================================

    def load_csv(self):
        filename, _ = QFileDialog.getOpenFileName(self, "CSV", "", "*.csv")
        if not filename:
            return
        try:
            self.csv_reader.read(filename, self.dataset)
        except Exception as e:
            QMessageBox.critical(self, "CSV Error", str(e))
            return

        self.lbl_csv_status.setText(
            f"{len(self.dataset.stations['Station'].unique())} stations, "
            f"{len(self.dataset.dates)} dates"
        )

        self.variable.blockSignals(True)
        self.variable.clear()
        self.variable.addItems(self.dataset.variables)
        self.variable.blockSignals(False)

        self._reset_date_slider()
        self._refresh_layers()
        self._update_controls_enabled()
        self.statusBar().showMessage("CSV loaded")

    # ------------------------------------------------------------------

    def load_shapefile(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Watershed", "", "*.shp")
        if not filename:
            return
        try:
            self.shape_reader.read(filename, self.dataset)
        except Exception as e:
            QMessageBox.critical(self, "Watershed Error", str(e))
            return

        self.lbl_shp_status.setText(
            f"{self.dataset.watershed_source}\n{self.dataset.projected_crs}"
        )

        self._refresh_layers()
        self._update_controls_enabled()
        self.statusBar().showMessage("Watershed loaded")

    # ------------------------------------------------------------------

    def remove_watershed(self):
        self.shape_reader.remove(self.dataset)
        self.lbl_shp_status.setText("No watershed loaded")
        self._refresh_layers()
        self._update_controls_enabled()
        self.statusBar().showMessage("Watershed removed")

    # ==================================================================
    # Grid
    # ==================================================================

    def generate_grid(self):
        if not self.dataset.has_watershed():
            QMessageBox.warning(self, "Warning", "Please load a watershed first.")
            return
        try:
            self.grid_gen.regenerate(self.dataset, self.grid_size.value())
        except Exception as e:
            QMessageBox.critical(self, "Grid Error", str(e))
            return

        self.statusBar().showMessage(f"Grid generated ({self.grid_size.value()} m)")
        self._refresh_layers()
        self._update_controls_enabled()

    def clear_grid(self):
        self.dataset.clear_grid()
        self._refresh_layers()
        self._update_controls_enabled()
        self.statusBar().showMessage("Grid cleared")

    # ==================================================================
    # Interpolation + date navigation
    # ==================================================================

    def _on_variable_changed(self, text):
        if text:
            self.dataset.current_variable = text
            self._refresh_raster()

    def _reset_date_slider(self):
        n = len(self.dataset.dates)
        self.slider.blockSignals(True)
        self.slider.setMaximum(max(n - 1, 0))
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self._update_date_label()

    def _update_date_label(self):
        if self.dataset.current_date is not None:
            self.lbl_date.setText(self.dataset.current_date.strftime("%Y-%m-%d"))
        else:
            self.lbl_date.setText("-")

    def _step_date(self, delta):
        new_date = self.dataset.step_date(delta)
        if new_date is None:
            return
        idx = self.dataset.dates.index(new_date)
        self.slider.blockSignals(True)
        self.slider.setValue(idx)
        self.slider.blockSignals(False)
        self._update_date_label()
        self._refresh_raster()

    def _on_slider_changed(self, idx):
        if not self.dataset.dates:
            return
        self.dataset.current_date = self.dataset.dates[idx]
        self._update_date_label()
        self._refresh_raster()

    # ------------------------------------------------------------------

    def interpolate_current(self):
        self._apply_power()
        self._refresh_raster(use_cache=False)

    def _apply_power(self):
        self.idw.set_power(self.power.value())
        if getattr(self.idw, "_power_changed", False):
            self.dataset.clear_interpolated()

    def _refresh_raster(self, use_cache=True):
        """Draw the raster for the current date/variable, using the cache
        whenever possible - navigating to an already-visited date/variable
        is instant instead of recomputing."""
        if not (self.dataset.has_grid() and self.dataset.current_date is not None
                and self.dataset.current_variable):
            return

        try:
            raster = self.idw.interpolate(
                self.dataset, self.dataset.current_date, self.dataset.current_variable,
                use_cache=use_cache,
            )
        except Exception as e:
            self.statusBar().showMessage(f"Interpolation failed: {e}")
            return

        if self.chk_raster.isChecked():
            cmap = (
                config.COLORMAP_PRECIP
                if self.dataset.current_variable == "Precipitation"
                else config.COLORMAP_TEMP
            )
            self.canvas.set_raster(
                self.dataset.grid_x, self.dataset.grid_y, raster,
                cmap=cmap, vmin=self.dataset.min_value, vmax=self.dataset.max_value,
                label=self.dataset.current_variable,
            )

        self._refresh_station_layer()

        self.statusBar().showMessage(
            f"{self.dataset.current_variable} @ {self.dataset.current_date.date()} - "
            f"min {self.dataset.min_value:.2f}, max {self.dataset.max_value:.2f}, "
            f"mean {self.dataset.mean_value:.2f}"
        )

    def _refresh_station_layer(self):
        if not self.chk_stations.isChecked() or not self.dataset.has_station_data():
            return
        if "X" not in self.dataset.stations.columns:
            return  # no projected CRS yet (watershed not loaded)

        day = self.dataset.get_day_data(self.dataset.current_date, self.dataset.current_variable)
        self.canvas.set_stations(
            day["X"].values, day["Y"].values,
            values=day[self.dataset.current_variable].values,
        )

    # ==================================================================
    # Layer visibility (no recompute - just show/hide what's cached)
    # ==================================================================

    def _refresh_layers(self):
        if self.chk_watershed.isChecked() and self.dataset.has_watershed():
            self.canvas.set_watershed(self.dataset.watershed, fit=False)
        else:
            self.canvas.clear_watershed()

        if self.chk_grid.isChecked() and self.dataset.has_grid():
            self.canvas.set_grid_mesh(self.dataset.grid_x, self.dataset.grid_y, fit=False)
        else:
            self.canvas.clear_grid_mesh()

        if self.chk_raster.isChecked() and self.dataset.has_grid():
            self._refresh_raster()
        else:
            self.canvas.clear_raster()

        if self.chk_stations.isChecked():
            self._refresh_station_layer()
        else:
            self.canvas.clear_stations()

        self.canvas.fit_to_layers()

    def _refresh_basemap(self):
        if not self.dataset.has_watershed():
            self.chk_basemap.setChecked(False)
            return
        self.canvas.set_basemap(
            self.chk_basemap.isChecked(),
            crs=self.dataset.watershed.crs.to_string(),
            provider_name=config.BASEMAP_PROVIDER,
        )

    # ==================================================================
    # Export
    # ==================================================================

    def export_netcdf(self):
        if not (self.dataset.has_grid() and self.dataset.variables):
            QMessageBox.warning(self, "Warning", "Generate a grid and load data first.")
            return

        dialog = ExportDialog(self.dataset, self)
        if not dialog.exec():
            return

        variable, start_date, end_date, out_path = dialog.values()
        if not out_path:
            QMessageBox.warning(self, "Warning", "Choose an output file.")
            return

        self._apply_power()

        dates_in_range = [d for d in self.dataset.dates if start_date <= d <= end_date]
        if not dates_in_range:
            QMessageBox.warning(self, "Warning", "No dates in that range.")
            return

        self.statusBar().showMessage(f"Exporting {len(dates_in_range)} timesteps...")
        rasters = []
        try:
            for d in dates_in_range:
                rasters.append(self.idw.interpolate(self.dataset, d, variable, use_cache=True))
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
            return

        stack = np.stack(rasters, axis=0)
        x_coords = self.dataset.grid_x[0, :]
        y_coords = self.dataset.grid_y[:, 0]

        try:
            self.netcdf_writer.write(
                out_path, stack, dates_in_range, x_coords, y_coords,
                variable_name=variable,
                units="mm" if variable == "Precipitation" else "degC",
                projected_crs=self.dataset.projected_crs,
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
            return

        self.statusBar().showMessage(f"Exported to {out_path}")
        QMessageBox.information(self, "Export complete", f"Saved: {out_path}")

    # ==================================================================
    # Control enable/disable bookkeeping
    # ==================================================================

    def _update_controls_enabled(self):
        has_ws = self.dataset.has_watershed()
        has_grid = self.dataset.has_grid()
        has_data = self.dataset.has_station_data()

        self.btn_remove_shp.setEnabled(has_ws)
        self.btn_grid.setEnabled(has_ws)
        self.btn_clear_grid.setEnabled(has_grid)
        self.btn_interp.setEnabled(has_grid and has_data)
        self.btn_export.setEnabled(has_grid and has_data)
        self.chk_basemap.setEnabled(has_ws)
