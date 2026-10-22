"""
csv_reader.py

Read station observation CSV files and populate the Dataset object.

Expected CSV format
-------------------

Date,Station,Longitude,Latitude,Precipitation,Temperature

2000-01-01,ST01,35.44,39.83,12.4,6.1
2000-01-01,ST02,35.89,39.52,15.8,5.7
2000-01-02,ST01,35.44,39.83,3.2,7.4
"""

from pathlib import Path

import pandas as pd

from models.dataset import Dataset


class CSVReader:
    """
    Read and validate station CSV files.
    """

    REQUIRED_COLUMNS = ["Date", "Station", "Longitude", "Latitude"]

    def __init__(self):
        pass

    # ------------------------------------------------------------------

    def read(self, filename: str | Path, dataset: Dataset | None = None) -> Dataset:
        """
        Read a CSV file and load it into `dataset`, updating it in place.

        If `dataset` is None a fresh one is created - but when a dataset is
        passed in (the normal case, from the running app), its watershed,
        grid, and any other already-loaded state is left untouched. Only
        station-dependent state (dates, variables, interpolation cache) is
        refreshed, since the new station data invalidates it.

        Parameters
        ----------
        filename : str or Path
        dataset : Dataset, optional - reused and updated in place if given

        Returns
        -------
        Dataset
        """

        filename = Path(filename)

        if not filename.exists():
            raise FileNotFoundError(filename)

        print(f"\nReading CSV: {filename.name}")

        df = pd.read_csv(filename)

        self.validate_columns(df)

        df = self.prepare_dataframe(df)

        if dataset is None:
            dataset = Dataset()

        dataset.stations = df
        dataset.set_dates()
        dataset.detect_variables()

        # Station set changed -> any cached rasters are stale, and X/Y need
        # recomputing if a projected CRS is already known (e.g. watershed
        # was loaded first).
        dataset.clear_interpolated()
        dataset.reproject_stations()

        dataset.summary()

        return dataset

    # ------------------------------------------------------------------

    def validate_columns(self, df: pd.DataFrame):
        missing = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns:\n{missing}")

    # ------------------------------------------------------------------

    def prepare_dataframe(self, df: pd.DataFrame):
        df = df.copy()

        df["Date"] = pd.to_datetime(df["Date"])
        df["Station"] = df["Station"].astype(str)

        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")

        df = df.dropna(subset=["Longitude", "Latitude"])
        df = df.sort_values(["Date", "Station"]).reset_index(drop=True)

        ignore = {"Date", "Station", "Longitude", "Latitude"}
        for col in df.columns:
            if col in ignore:
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    # ------------------------------------------------------------------

    @staticmethod
    def preview(df: pd.DataFrame, n=5):
        print()
        print("=" * 60)
        print(df.head(n))
        print("=" * 60)
