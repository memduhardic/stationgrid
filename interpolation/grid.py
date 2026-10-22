"""
grid.py

Grid generation for StationGrid.

Creates a regular grid covering the watershed extent, in the projected
CRS (meters), and masks out cells outside the watershed boundary.
"""

from __future__ import annotations

import numpy as np
from shapely.geometry import Point

try:
    # Shapely >= 2.0: fast vectorized point-in-polygon
    from shapely import contains_xy

    HAS_VECTORIZED = True
except ImportError:
    HAS_VECTORIZED = False


class GridGenerator:
    """
    Creates a regular interpolation grid.
    """

    def __init__(self, resolution=1000):
        self.resolution = float(resolution)

    # ------------------------------------------------------------------

    def set_resolution(self, resolution):
        self.resolution = float(resolution)

    # ------------------------------------------------------------------

    def create_grid(self, dataset):
        """
        Generate a regular grid from the watershed extent, in place on
        `dataset`. Any previously interpolated rasters are cleared since
        they belonged to the old grid.
        """

        if dataset.watershed is None:
            raise RuntimeError("Watershed has not been loaded.")

        minx, miny, maxx, maxy = dataset.watershed.total_bounds

        x = np.arange(minx, maxx + self.resolution, self.resolution)
        y = np.arange(miny, maxy + self.resolution, self.resolution)

        xx, yy = np.meshgrid(x, y)

        dataset.grid_x = xx
        dataset.grid_y = yy
        dataset.grid_resolution = self.resolution
        dataset.grid_mask = self.create_mask(dataset, xx, yy)

        dataset.clear_interpolated()

        return dataset

    # ------------------------------------------------------------------

    def create_mask(self, dataset, xx, yy):
        """True = inside basin, False = outside."""
        polygon = dataset.watershed.geometry.iloc[0]

        if HAS_VECTORIZED:
            return contains_xy(polygon, xx, yy)

        mask = np.zeros(xx.shape, dtype=bool)
        for r in range(xx.shape[0]):
            for c in range(xx.shape[1]):
                mask[r, c] = polygon.contains(Point(xx[r, c], yy[r, c]))
        return mask

    # ------------------------------------------------------------------

    def regenerate(self, dataset, resolution):
        """Recreate the grid using a new resolution."""
        self.set_resolution(resolution)
        return self.create_grid(dataset)

    # ------------------------------------------------------------------

    @staticmethod
    def shape(dataset):
        return dataset.grid_x.shape

    @staticmethod
    def cell_count(dataset):
        return dataset.grid_x.size

    @staticmethod
    def inside_cells(dataset):
        return np.count_nonzero(dataset.grid_mask)

    @staticmethod
    def outside_cells(dataset):
        return dataset.grid_mask.size - np.count_nonzero(dataset.grid_mask)

    # ------------------------------------------------------------------

    @staticmethod
    def summary(dataset):
        print()
        print("=" * 60)
        print("Grid Summary")
        print("=" * 60)
        print(f"Resolution : {dataset.grid_resolution:.1f} m")
        print(f"Rows        : {dataset.grid_x.shape[0]}")
        print(f"Columns     : {dataset.grid_x.shape[1]}")
        print(f"Total Cells : {dataset.grid_x.size:,}")
        print(f"Inside Basin: {np.count_nonzero(dataset.grid_mask):,}")
        print("=" * 60)
