"""
map_canvas.py

A self-contained map widget used by MainWindow. Two things this fixes
relative to a plain embedded matplotlib canvas:

1. Free pan/zoom, always on - no need to click a toolbar button first.
   Scroll wheel zooms centered on the cursor; left-click-drag pans.
   (matplotlib's own pan/zoom-rect toolbar buttons are deliberately not
   used, since toggling between them is exactly the "not free" feeling
   you were describing.)

2. Layers are tracked and updated independently - setting a new raster
   or moving to a different date does NOT clear the axes and redraw
   everything from scratch, so your current pan/zoom position, and any
   other visible layers, are left alone. Each layer has its own
   set_/clear_ method and can be added, removed, or swapped without
   touching the others.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class MapCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.figure = Figure()
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_aspect("equal")

        self._layers = {}   # name -> artist or list of artists
        self._colorbar = None
        self._pan_start = None  # (event.x, event.y, xlim, ylim)

        self._build_ui()
        self._connect_events()

    # ------------------------------------------------------------------
    # UI scaffolding
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        bar = QHBoxLayout()
        self.btn_reset = QPushButton("Reset View")
        self.btn_reset.clicked.connect(self.fit_to_layers)
        bar.addWidget(self.btn_reset)
        bar.addStretch()

        layout.addLayout(bar)
        layout.addWidget(self.canvas, 1)

    def _connect_events(self):
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)

    # ------------------------------------------------------------------
    # Free pan / zoom
    # ------------------------------------------------------------------

    def _on_scroll(self, event):
        if event.xdata is None or event.ydata is None:
            return
        scale = 1 / 1.2 if event.button == "up" else 1.2

        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        relx = (xlim[1] - event.xdata) / (xlim[1] - xlim[0])
        rely = (ylim[1] - event.ydata) / (ylim[1] - ylim[0])
        new_w = (xlim[1] - xlim[0]) * scale
        new_h = (ylim[1] - ylim[0]) * scale

        self.ax.set_xlim(event.xdata - new_w * (1 - relx), event.xdata + new_w * relx)
        self.ax.set_ylim(event.ydata - new_h * (1 - rely), event.ydata + new_h * rely)
        self.canvas.draw_idle()

    def _on_press(self, event):
        if event.button == 1 and event.inaxes == self.ax and event.x is not None:
            self._pan_start = (event.x, event.y, self.ax.get_xlim(), self.ax.get_ylim())

    def _on_motion(self, event):
        if self._pan_start is None or event.x is None or event.y is None:
            return
        x0, y0, xlim0, ylim0 = self._pan_start
        inv = self.ax.transData.inverted()
        dx0, dy0 = inv.transform((x0, y0))
        dx1, dy1 = inv.transform((event.x, event.y))
        dx, dy = dx0 - dx1, dy0 - dy1
        self.ax.set_xlim(xlim0[0] + dx, xlim0[1] + dx)
        self.ax.set_ylim(ylim0[0] + dy, ylim0[1] + dy)
        self.canvas.draw_idle()

    def _on_release(self, event):
        self._pan_start = None

    def fit_to_layers(self):
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Layer removal helper
    # ------------------------------------------------------------------

    def _remove_layer(self, name):
        artist = self._layers.pop(name, None)
        if artist is None:
            return
        items = artist if isinstance(artist, (list, tuple)) else [artist]
        for item in items:
            try:
                item.remove()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Watershed layer
    # ------------------------------------------------------------------

    def set_watershed(self, gdf, fit=True):
        self._remove_layer("watershed")
        artists = gdf.boundary.plot(ax=self.ax, color="black", linewidth=1.8).collections
        self._layers["watershed"] = list(artists)
        if fit:
            self.fit_to_layers()
        self.canvas.draw_idle()

    def clear_watershed(self):
        self._remove_layer("watershed")
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Grid mesh (structure preview, no data)
    # ------------------------------------------------------------------

    def set_grid_mesh(self, xx, yy, fit=True):
        self._remove_layer("grid_mesh")
        mesh = self.ax.pcolormesh(
            xx, yy, xx * 0, shading="nearest",
            facecolor="none", edgecolor="black", linewidth=0.4, alpha=0.4,
        )
        self._layers["grid_mesh"] = mesh
        if fit:
            self.fit_to_layers()
        self.canvas.draw_idle()

    def clear_grid_mesh(self):
        self._remove_layer("grid_mesh")
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Interpolated raster
    # ------------------------------------------------------------------

    def set_raster(self, xx, yy, raster, cmap="viridis", vmin=None, vmax=None, label=""):
        """Updates in place (mesh.set_array) when the grid shape hasn't
        changed, so navigating between dates doesn't reset your pan/zoom
        or flicker the whole canvas - only the colors change."""
        existing = self._layers.get("raster")
        if existing is not None and existing.get_array().size == raster.size:
            existing.set_array(raster.ravel())
            existing.set_clim(vmin, vmax)
            existing.set_cmap(cmap)
            self.canvas.draw_idle()
            return

        self._remove_layer("raster")
        mesh = self.ax.pcolormesh(
            xx, yy, raster, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest"
        )
        self._layers["raster"] = mesh

        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
        self._colorbar = self.figure.colorbar(mesh, ax=self.ax, label=label)

        self.canvas.draw_idle()

    def clear_raster(self):
        self._remove_layer("raster")
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
            self._colorbar = None
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Stations
    # ------------------------------------------------------------------

    def set_stations(self, x, y, values=None, cmap="coolwarm", label=""):
        existing = self._layers.get("stations")
        if existing is not None and len(existing.get_offsets()) == len(x):
            existing.set_offsets(list(zip(x, y)))
            if values is not None:
                existing.set_array(values)
            self.canvas.draw_idle()
            return

        self._remove_layer("stations")
        if values is not None:
            sc = self.ax.scatter(
                x, y, c=values, cmap=cmap, s=45, marker="^",
                edgecolor="black", linewidth=0.6, zorder=5,
            )
        else:
            sc = self.ax.scatter(
                x, y, c="black", s=35, marker="^", zorder=5,
            )
        self._layers["stations"] = sc
        self.canvas.draw_idle()

    def clear_stations(self):
        self._remove_layer("stations")
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Basemap (optional, needs live internet access to the tile server)
    # ------------------------------------------------------------------

    def set_basemap(self, enabled: bool, crs, provider_name: str = "CartoDB.Positron"):
        self._remove_layer("basemap")
        if not enabled:
            self.canvas.draw_idle()
            return

        try:
            import contextily as cx

            provider = cx.providers
            for part in provider_name.split("."):
                provider = provider[part]

            before = list(self.ax.images)
            cx.add_basemap(self.ax, crs=crs, source=provider)
            after = list(self.ax.images)
            new_images = [im for im in after if im not in before]
            self._layers["basemap"] = new_images
            # basemap should sit behind everything else
            for im in new_images:
                im.set_zorder(0)
        except Exception as exc:
            print(f"Basemap unavailable ({exc}) - continuing without it.")

        self.canvas.draw_idle()
