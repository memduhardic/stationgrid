"""
dataset.py

Central data model for StationGrid.

This module defines the Dataset class, which stores all project data
required throughout the application. It is the single object that
persists across the whole session - loading a new CSV, swapping the
watershed, or regenerating the grid should each update this object
in place rather than replacing it, so nothing else in the project
gets thrown away in the process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj


@dataclass
class Dataset:
    """
    Central application data container.
    """

    # ==========================================================
    # Station Data
    # ==========================================================

    stations: Optional[pd.DataFrame] = None

    station_gdf: Optional[gpd.GeoDataFrame] = None

    # ==========================================================
    # Watershed
    # ==========================================================

    watershed: Optional[gpd.GeoDataFrame] = None

    watershed_source: Optional[str] = None  # filename, for the layer panel label

    # ==========================================================
    # Coordinate Reference Systems
    # ==========================================================

    input_crs: str = "EPSG:4326"

    projected_crs: Optional[str] = None

    # ==========================================================
    # Time
    # ==========================================================

    dates: List[pd.Timestamp] = field(default_factory=list)

    current_date: Optional[pd.Timestamp] = None

    # ==========================================================
    # Variables
    # ==========================================================

    variables: List[str] = field(default_factory=list)

    current_variable: Optional[str] = None

    # ==========================================================
    # Grid
    # ==========================================================

    grid_x: Optional[np.ndarray] = None

    grid_y: Optional[np.ndarray] = None

    grid_mask: Optional[np.ndarray] = None

    grid_resolution: float = 1000.0

    # ==========================================================
    # Interpolated Data (cache - keyed by variable then date, so
    # revisiting a date/variable already computed is instant and
    # never forces you back to square one)
    # ==========================================================

    interpolated: Dict[str, Dict[pd.Timestamp, np.ndarray]] = field(
        default_factory=dict
    )

    # ==========================================================
    # Statistics
    # ==========================================================

    min_value: float = np.nan
    max_value: float = np.nan
    mean_value: float = np.nan
    std_value: float = np.nan

    # ==========================================================
    # Utility Methods
    # ==========================================================

    def clear_interpolated(self):
        """Remove all interpolated rasters (call whenever something the
        rasters depend on changes: grid, IDW power, station data)."""
        self.interpolated.clear()

    # ----------------------------------------------------------

    def clear_grid(self):
        """Remove the grid without touching stations or the watershed."""
        self.grid_x = None
        self.grid_y = None
        self.grid_mask = None
        self.clear_interpolated()

    # ----------------------------------------------------------

    def clear_watershed(self):
        """Remove the watershed. The grid is invalid without it, so it
        goes too - but stations/CSV data are left untouched."""
        self.watershed = None
        self.watershed_source = None
        self.clear_grid()

    # ----------------------------------------------------------

    def has_station_data(self) -> bool:
        return self.stations is not None

    def has_station_gdf(self) -> bool:
        return self.station_gdf is not None

    def has_watershed(self) -> bool:
        return self.watershed is not None

    def has_grid(self) -> bool:
        return (
            self.grid_x is not None
            and self.grid_y is not None
            and self.grid_mask is not None
        )

    # ----------------------------------------------------------

    def set_dates(self):
        if self.stations is None:
            self.dates = []
            self.current_date = None
            return

        self.dates = sorted(pd.to_datetime(self.stations["Date"].unique()))

        if self.dates and self.current_date not in self.dates:
            self.current_date = self.dates[0]

    # ----------------------------------------------------------

    def detect_variables(self):
        if self.stations is None:
            self.variables = []
            self.current_variable = None
            return

        ignore = {"Date", "Station", "Longitude", "Latitude", "X", "Y", "geometry"}

        self.variables = [
            col
            for col in self.stations.columns
            if col not in ignore and pd.api.types.is_numeric_dtype(self.stations[col])
        ]

        if self.variables and self.current_variable not in self.variables:
            self.current_variable = self.variables[0]

    # ----------------------------------------------------------

    def reproject_stations(self):
        """Compute projected X/Y columns for every station, using
        self.projected_crs. Safe to call any time - it's a no-op until
        both station data and a projected CRS are available, and it
        re-runs automatically whenever either changes."""
        if self.stations is None or self.projected_crs is None:
            return

        transformer = pyproj.Transformer.from_crs(
            self.input_crs, self.projected_crs, always_xy=True
        )
        x, y = transformer.transform(
            self.stations["Longitude"].values, self.stations["Latitude"].values
        )
        self.stations["X"] = x
        self.stations["Y"] = y

    # ----------------------------------------------------------

    def get_day_data(self, date, variable: Optional[str] = None) -> pd.DataFrame:
        if self.stations is None:
            raise ValueError("Station data not loaded.")

        date = pd.to_datetime(date)
        df = self.stations[self.stations["Date"] == date].copy()

        if variable is not None:
            keep = ["Station", "Longitude", "Latitude", variable]
            if "X" in df.columns and "Y" in df.columns:
                keep = ["Station", "Longitude", "Latitude", "X", "Y", variable]
            df = df[keep]

        return df

    # ----------------------------------------------------------

    def add_interpolated(self, variable: str, date, raster: np.ndarray):
        date = pd.to_datetime(date)
        self.interpolated.setdefault(variable, {})[date] = raster

    def get_interpolated(self, variable: str, date):
        date = pd.to_datetime(date)
        return self.interpolated.get(variable, {}).get(date)

    # ----------------------------------------------------------

    def update_statistics(self, raster: np.ndarray):
        self.min_value = float(np.nanmin(raster))
        self.max_value = float(np.nanmax(raster))
        self.mean_value = float(np.nanmean(raster))
        self.std_value = float(np.nanstd(raster))

    # ----------------------------------------------------------

    def grid_shape(self):
        return None if self.grid_x is None else self.grid_x.shape

    def grid_cell_count(self):
        return 0 if self.grid_x is None else self.grid_x.size

    # ----------------------------------------------------------

    def step_date(self, delta: int):
        """Move current_date forward/back by `delta` steps. Returns the
        new date, or None if there's nowhere to go."""
        if not self.dates or self.current_date is None:
            return None
        idx = self.dates.index(self.current_date)
        new_idx = min(max(idx + delta, 0), len(self.dates) - 1)
        self.current_date = self.dates[new_idx]
        return self.current_date

    # ----------------------------------------------------------

    def summary(self):
        print()
        print("=" * 60)
        print("Dataset Summary")
        print("=" * 60)

        if self.stations is None:
            print("Stations        : None")
        else:
            print(f"Records         : {len(self.stations):,}")
            print(f"Stations        : {self.stations['Station'].nunique()}")
            print(f"Dates           : {len(self.dates)}")
            print(f"Variables       : {self.variables}")

        print("Watershed       : None" if self.watershed is None else "Watershed       : Loaded")

        if self.grid_x is None:
            print("Grid            : Not generated")
        else:
            print(f"Grid Shape      : {self.grid_x.shape}")
            print(f"Grid Resolution : {self.grid_resolution:.0f} m")
            print(f"Grid Cells      : {self.grid_x.size:,}")

        print("=" * 60)
