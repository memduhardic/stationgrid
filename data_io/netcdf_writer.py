# data_io/netcdf_writer.py

import numpy as np
import pandas as pd
import pyproj
import xarray as xr


class NetCDFWriter:
    def write(
        self,
        output_file,
        raster_stack,
        dates,
        x_coords,
        y_coords,
        variable_name="Precipitation",
        units="mm",
        projected_crs=None,
    ):
        """
        Parameters
        ----------
        output_file : str
        raster_stack : np.ndarray, shape (time, y, x)
        dates : list[pd.Timestamp]
        x_coords, y_coords : np.ndarray, 1-D, projected meters
        projected_crs : anything pyproj.CRS.from_user_input accepts
            (e.g. dataset.projected_crs) - written as a CF grid_mapping
            variable so HEC-HMS's NetCDF grid importer (or HEC-DSSVue's
            netCDF->DSS GridUtility) can pick up the projection.
        """

        ds = xr.Dataset(
            data_vars={
                variable_name: (
                    ("time", "y", "x"),
                    raster_stack.astype(np.float32),
                    {
                        "units": units,
                        "long_name": variable_name,
                        "grid_mapping": "crs",
                        "coordinates": "x y",
                    },
                )
            },
            coords={
                "time": pd.to_datetime(dates),
                "x": x_coords,
                "y": y_coords,
            },
        )

        if projected_crs is not None:
            crs = pyproj.CRS.from_user_input(projected_crs)
            ds["crs"] = xr.DataArray(
                0,
                attrs={
                    "grid_mapping_name": crs.to_cf().get("grid_mapping_name", "unknown"),
                    "spatial_ref": crs.to_wkt(),
                    "crs_wkt": crs.to_wkt(),
                },
            )

        ds["x"].attrs = {"units": "m", "standard_name": "projection_x_coordinate"}
        ds["y"].attrs = {"units": "m", "standard_name": "projection_y_coordinate"}
        ds.attrs["Conventions"] = "CF-1.8"
        ds.attrs["source"] = "HEC GridMaker IDW interpolation"

        encoding = {variable_name: {"zlib": True, "complevel": 4}}

        ds.to_netcdf(output_file, engine="netcdf4", encoding=encoding)

        print(f"NetCDF saved: {output_file}")
        return ds
