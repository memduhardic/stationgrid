# HEC GridMaker

A desktop GIS tool (Python / PySide6) that turns point-based station observations — precipitation, temperature, or any numeric variable — into gridded fields over a watershed, and exports them as CF-compliant NetCDF for use in **HEC-HMS** gridded meteorology.

## Features

- **Station CSV import** with automatic detection of numeric variables
- **Watershed import** (Shapefile, GeoJSON, GeoPackage — anything GeoPandas can read), with automatic UTM zone detection
- **Regular grid generation** over the watershed extent at a user-defined resolution (meters), masked to the basin boundary
- **IDW interpolation** (adjustable power), fully vectorized with a low-memory fallback for very fine grids
- **Per-date caching** — stepping back to a date/variable already computed is instant
- **Interactive map** — free scroll-zoom and drag-pan, independent layers (watershed, grid mesh, raster, stations, optional basemap)
- **NetCDF export** (CF-1.8, compressed) with a `grid_mapping` CRS variable, ready for HEC-HMS / HEC-DSSVue grid import

## Workflow

```
Station CSV ─┐
             ├─► Projected CRS (UTM) ─► Grid + basin mask ─► IDW per date ─► NetCDF
Watershed ───┘
```

## Installation

Requires **Python 3.10+**.

```bash
git clone https://github.com/<memduhardic/hec-gridmaker.git
cd hec-gridmaker

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

1. **Load CSV** – station observations
2. **Load Watershed** – basin boundary polygon
3. **Generate Grid** – choose cell size in meters
4. **Interpolate** – pick variable, IDW power, and step through dates
5. **Export NetCDF** – choose variable, date range, and output file

Sample inputs are provided in [`examples/`](examples/) (synthetic data, for testing only).

## Input format

Station CSV — one row per station per date, coordinates in WGS84 (EPSG:4326):

```csv
Date,Station,Longitude,Latitude,Precipitation,Temperature
2020-01-01,ST01,34.10,39.20,5.6,3.9
2020-01-01,ST02,34.55,39.05,3.8,0.2
```

`Date`, `Station`, `Longitude`, `Latitude` are required. Every other numeric column becomes a selectable variable.

The watershed file must have a defined CRS. Multi-part inputs are dissolved into a single polygon.

## Configuration

Defaults (grid size, IDW power, colormaps, basemap) live in [`config.py`](config.py). The basemap is off by default because it needs internet access to the tile server.

## Project structure

```
hec-gridmaker/
├── main.py                  # entry point
├── config.py                # defaults
├── models/
│   └── dataset.py           # central session state
├── data_io/
│   ├── csv_reader.py
│   ├── shapefile_reader.py
│   └── netcdf_writer.py
├── interpolation/
│   ├── grid.py              # grid + basin mask
│   └── idw.py               # IDW with caching
├── ui/
│   ├── main_window.py
│   ├── map_canvas.py
│   └── dialogs.py
└── examples/                # sample CSV + watershed
```

## License

MIT — see [LICENSE](LICENSE).
