"""
idw.py

Inverse Distance Weighting (IDW) interpolation.

Workflow:
    Stations -> IDW -> Raster -> Mask Outside Watershed

Results are cached on the Dataset (variable, date) so switching back to
a date/variable you've already interpolated is instant - no recompute,
no "start from the beginning". The cache is invalidated automatically
whenever the grid, IDW power, or the station data itself changes (see
Dataset.clear_interpolated, called from grid regeneration and CSV/
shapefile loading).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class IDWInterpolator:
    def __init__(self, power: float = 2.0):
        self.power = power

    # ------------------------------------------------------------------

    def set_power(self, power: float):
        """Changing the power invalidates any cached rasters - they were
        computed with the old exponent."""
        new_power = float(power)
        if new_power != self.power:
            self.power = new_power
            self._power_changed = True
        else:
            self._power_changed = False

    # ------------------------------------------------------------------

    def interpolate(self, dataset, date, variable: str, use_cache: bool = True):
        """
        Interpolate one day. Returns the cached raster if one already
        exists for this (variable, date) and use_cache is True.
        """

        if not dataset.has_grid():
            raise RuntimeError("Grid has not been generated.")

        if use_cache:
            cached = dataset.get_interpolated(variable, date)
            if cached is not None:
                dataset.update_statistics(cached)
                return cached

        df = dataset.get_day_data(date=date, variable=variable)

        if len(df) == 0:
            raise ValueError(f"No observations found for {date}")

        if "X" not in df.columns or "Y" not in df.columns:
            raise RuntimeError(
                "Stations have no projected X/Y coordinates yet - load a "
                "watershed first so a projected CRS can be determined, or "
                "call dataset.reproject_stations()."
            )

        raster = self._idw(dataset, df, variable)
        raster = np.where(dataset.grid_mask, raster, np.nan)

        dataset.update_statistics(raster)
        dataset.add_interpolated(variable, date, raster)

        return raster

    # ------------------------------------------------------------------

    def _idw(self, dataset, df: pd.DataFrame, variable: str):
        """Vectorized IDW - one array op per station instead of a nested
        pixel loop, using the same distance/weight formula as before."""

        xx = dataset.grid_x
        yy = dataset.grid_y

        station_x = df["X"].values
        station_y = df["Y"].values
        values = df[variable].values

        valid = np.isfinite(values) & np.isfinite(station_x) & np.isfinite(station_y)
        station_x, station_y, values = station_x[valid], station_y[valid], values[valid]

        if len(values) == 0:
            raise ValueError(f"No valid values found for {variable}")

        # Fully vectorized (n_stations, ny, nx) broadcast is much faster for
        # typical station counts, but for a very fine grid x many stations
        # it can use a lot of memory - fall back to the per-station loop
        # (same math, lower peak memory) above ~200M station-cell products.
        if len(values) * xx.size > 200_000_000:
            return self._idw_loop(xx, yy, station_x, station_y, values)

        dx = xx[None, :, :] - station_x[:, None, None]
        dy = yy[None, :, :] - station_y[:, None, None]
        distance = np.sqrt(dx**2 + dy**2)
        distance = np.where(distance < 1.0, 1.0, distance)

        weight = 1.0 / distance**self.power
        numerator = np.sum(weight * values[:, None, None], axis=0)
        denominator = np.sum(weight, axis=0)

        raster = numerator / denominator
        return raster.astype(np.float32)

    # ------------------------------------------------------------------

    def _idw_loop(self, xx, yy, station_x, station_y, values):
        """Low-memory fallback: same result as _idw's vectorized path, one
        station at a time."""
        numerator = np.zeros(xx.shape, dtype=np.float64)
        denominator = np.zeros(xx.shape, dtype=np.float64)

        for x, y, value in zip(station_x, station_y, values):
            distance = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
            distance = np.where(distance < 1.0, 1.0, distance)
            weight = 1.0 / distance**self.power
            numerator += weight * value
            denominator += weight

        return (numerator / denominator).astype(np.float32)

    # ------------------------------------------------------------------

    def interpolate_current(self, dataset, use_cache: bool = True):
        """Interpolate currently selected variable and date."""
        return self.interpolate(
            dataset=dataset,
            date=dataset.current_date,
            variable=dataset.current_variable,
            use_cache=use_cache,
        )

    # ------------------------------------------------------------------

    def summary(self, raster):
        print()
        print("=" * 60)
        print("Interpolation Summary")
        print("=" * 60)
        print(f"Minimum : {np.nanmin(raster):.3f}")
        print(f"Maximum : {np.nanmax(raster):.3f}")
        print(f"Mean    : {np.nanmean(raster):.3f}")
        print(f"Std Dev : {np.nanstd(raster):.3f}")
        print("=" * 60)
