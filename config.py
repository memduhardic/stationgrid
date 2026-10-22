"""
Configuration file for HEC GridMaker
"""

from pathlib import Path

# =============================================================================
# Application
# =============================================================================

APP_NAME = "HEC GridMaker"
VERSION = "0.2.0"

# =============================================================================
# Directories
# =============================================================================

ROOT_DIR = Path(__file__).resolve().parent

DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# =============================================================================
# Coordinate System
# =============================================================================

# Default CRS for station coordinates
INPUT_CRS = "EPSG:4326"

# Leave None for automatic UTM detection (from the watershed centroid)
PROJECTED_CRS = None

# =============================================================================
# Grid
# =============================================================================

DEFAULT_GRID_SIZE = 1000  # meters

DEFAULT_IDW_POWER = 2.0

DEFAULT_SEARCH_RADIUS = 50000  # meters (0 = unlimited, use all stations)

DEFAULT_MIN_POINTS = 3

# =============================================================================
# Display
# =============================================================================

FIGURE_WIDTH = 10
FIGURE_HEIGHT = 8

COLORMAP_PRECIP = "Blues"
COLORMAP_TEMP = "RdYlBu_r"

# Basemap tiles require live internet access to the tile provider. Off by
# default so the app stays fast/usable on restricted networks (e.g. DSİ);
# toggle it on from the Layers panel when you have connectivity.
BASEMAP_DEFAULT_ON = False
BASEMAP_PROVIDER = "CartoDB.Positron"

# =============================================================================
# NetCDF
# =============================================================================

NETCDF_ENGINE = "netcdf4"
NETCDF_COMPRESSION = True
NETCDF_LEVEL = 4
