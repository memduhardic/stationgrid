"""
shapefile_reader.py

Read watershed polygons for StationGrid.
"""

from pathlib import Path

import geopandas as gpd

from models.dataset import Dataset


class ShapefileReader:
    """
    Read watershed boundary files.
    """

    def __init__(self):
        pass

    # ------------------------------------------------------------------

    def read(
        self, filename: str | Path, dataset: Dataset, force_redetect_crs: bool = False
    ) -> Dataset:
        """
        Load a watershed polygon into `dataset`, in place.

        Replacing the watershed invalidates the existing grid (its geometry
        no longer matches), so the grid + interpolation cache are cleared -
        but station/CSV data is left completely untouched, so you don't
        need to reload your CSV just because you picked a different
        watershed shapefile.

        Parameters
        ----------
        filename : str or Path
        dataset : Dataset - updated in place
        force_redetect_crs : bool - re-run UTM auto-detection even if a
            projected CRS was already chosen for an earlier watershed
            (use this if you're switching to a watershed in a very
            different location).
        """

        filename = Path(filename)

        if not filename.exists():
            raise FileNotFoundError(filename)

        print(f"\nReading watershed: {filename.name}")

        gdf = gpd.read_file(filename)

        self.validate(gdf)

        gdf = gdf.dissolve().reset_index(drop=True)

        dataset.watershed = gdf
        dataset.watershed_source = filename.name
        dataset.input_crs = str(gdf.crs) if gdf.crs is not None else dataset.input_crs

        if dataset.projected_crs is None or force_redetect_crs:
            dataset.projected_crs = gdf.estimate_utm_crs()

        dataset.watershed = dataset.watershed.to_crs(dataset.projected_crs)

        # Old grid (if any) belonged to the previous watershed geometry.
        dataset.clear_grid()
        dataset.reproject_stations()

        self.summary(dataset)

        return dataset

    # ------------------------------------------------------------------

    def remove(self, dataset: Dataset) -> Dataset:
        """Remove the watershed (and, necessarily, the grid built from it)
        without touching station data."""
        dataset.clear_watershed()
        return dataset

    # ------------------------------------------------------------------

    @staticmethod
    def validate(gdf):
        if gdf.empty:
            raise ValueError("Shapefile contains no features.")
        if gdf.crs is None:
            raise ValueError("Input shapefile has no Coordinate Reference System.")
        if gdf.geometry.is_empty.any():
            raise ValueError("One or more geometries are empty.")

    # ------------------------------------------------------------------

    @staticmethod
    def extent(dataset: Dataset):
        minx, miny, maxx, maxy = dataset.watershed.total_bounds
        return minx, miny, maxx, maxy

    @staticmethod
    def area(dataset: Dataset):
        """Watershed area in square kilometers."""
        return dataset.watershed.geometry.area.iloc[0] / 1_000_000

    @staticmethod
    def centroid(dataset: Dataset):
        return dataset.watershed.geometry.centroid.iloc[0]

    # ------------------------------------------------------------------

    def summary(self, dataset: Dataset):
        minx, miny, maxx, maxy = self.extent(dataset)

        print()
        print("=" * 60)
        print("Watershed Summary")
        print("=" * 60)
        print(f"Input CRS     : {dataset.input_crs}")
        print(f"Projected CRS : {dataset.projected_crs}")
        print()
        print(f"Area (km2)    : {self.area(dataset):.2f}")
        print()
        print("Extent (meters)")
        print(f"Min X : {minx:.2f}")
        print(f"Min Y : {miny:.2f}")
        print(f"Max X : {maxx:.2f}")
        print(f"Max Y : {maxy:.2f}")
        print("=" * 60)
