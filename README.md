# ANCPI GIS Client

Python client for querying Romania's ANCPI (National Agency for Cadastre and Land Registration) geoportal endpoints.

## Install

```bash
# Using uv (recommended)
uv venv
uv pip install -e .

# Optional: enable Stereo70 → WGS84 coordinate transformation
uv pip install -e ".[transform]"

# Or install everything
uv pip install -e ".[all]"
```

## CLI Usage

```bash
# Look up a cadastral parcel by number (searches label field)
ancpi parcel 105966

# Look up by full national cadastral reference (county.zone.number)
ancpi parcel AB.1017.70112

# Look up by INSPIRE ID
ancpi parcel --inspire-id RO.83.40991.102507

# Find parcels at a geographic point (lat,lon) — most reliable
ancpi parcel --at 44.43,26.1

# Find parcels in a bounding box
ancpi parcel --bbox 44.3,26.0,44.5,26.2

# Find buildings at a point
ancpi building --at 44.43,26.1

# Look up administrative unit by NUTS code
ancpi admin RO321

# Look up address at a point
ancpi address --at 44.43,26.1

# Show layer metadata
ancpi info CP
ancpi info BU
ancpi info AD
ancpi info AU
```

### Output formats

```bash
# Table format (default in terminal)
ancpi --format table admin RO321

# JSON (default when piped)
ancpi admin RO321 | jq .

# GeoJSON (QGIS, OpenStreetMap tools, Leaflet, Mapbox)
ancpi --format geojson admin RO321 > bucharest.geojson

# KML (Google Earth, Google Maps, QGIS)
ancpi --format kml admin RO321 > bucharest.kml

# Write to file
ancpi --format geojson -o parcels.geojson parcel --at 26.1,44.43
ancpi --format kml -o parcels.kml parcel --at 26.1,44.43

# Omit geometry (smaller/faster output)
ancpi --no-geometry admin RO321

# Debug mode
ancpi -v parcel --at 26.1,44.43
```

### Import into other tools

| Format | Tool | How to import |
|--------|------|---------------|
| GeoJSON | **QGIS** | Layer > Add Layer > Add Vector Layer, select the `.geojson` file |
| GeoJSON | **OpenStreetMap** (geojson.io) | Drag & drop onto geojson.io |
| GeoJSON | **Leaflet/Mapbox** | Load directly in JS |
| KML | **Google Earth** | File > Open, select the `.kml` file |
| KML | **Google Maps** | My Maps > Import, upload the `.kml` file |
| KML | **QGIS** | Layer > Add Layer > Add Vector Layer, select the `.kml` file |

## Library Usage

```python
from ancpi import ANCPIClient

client = ANCPIClient()

# Query admin unit
result = client.get_admin_unit("RO321")
print(f"Found {result.count} features")
print(result.features[0].nuts_code)

# Query cadastral parcel
result = client.get_parcel("102507")
for parcel in result.features:
    print(parcel.cadastral_ref, parcel.area)

# Spatial query
result = client.get_parcels_at(lon=26.1, lat=44.43)

# Export as GeoJSON
geojson = result.to_geojson()

# Export as KML (for Google Earth / Google Maps)
kml_str = result.to_kml_str()
with open("parcels.kml", "w") as f:
    f.write(kml_str)

# Export as dicts
data = result.to_dicts()

# Use as context manager
with ANCPIClient() as client:
    result = client.get_buildings_at(26.1, 44.43)
```

## Available Themes

| Theme | Description | Layers |
|-------|-------------|--------|
| CP | Cadastral Parcels | Zoning, Parcel, Boundary |
| BU | Buildings | BuildingPart (point/surface), Building (point/surface) |
| AD | Addresses | Address points |
| AU | Administrative Units | NUTS regions, counties, municipalities |

## Coordinate Transformation (Stereo70 → WGS84)

Some ANCPI endpoints return coordinates in Romania's Stereo70 projection (EPSG:3844) instead of WGS84. When `pyproj` is installed, the client auto-detects this and transforms coordinates to WGS84 so they work directly with Google Maps, QGIS, etc.

```bash
uv pip install ancpi[transform]
```

```python
from ancpi import ANCPIClient, PYPROJ_AVAILABLE

print(f"Transform support: {PYPROJ_AVAILABLE}")

# Coordinates are auto-transformed to WGS84 when pyproj is available
client = ANCPIClient()
result = client.get_parcel("102507")
# geometry is now in WGS84 regardless of server response CRS
```

You can also use the transform module directly:

```python
from ancpi.transform import transform_point, PYPROJ_AVAILABLE

if PYPROJ_AVAILABLE:
    lon, lat = transform_point(500000, 500000, from_epsg=3844)
    print(f"Center of projection: {lat:.6f}°N, {lon:.6f}°E")
    # Center of projection: 46.000000°N, 25.000000°E
```

## Known Limitations

- **CP and BU query endpoints are frequently down** (502/timeout). Even when up, attribute queries (by cadastral number) are very slow and often time out — spatial queries (`--at`, `--bbox`) are more reliable. Metadata (`ancpi info`) always works. The client tries multiple server paths with fallback.
- **SSL certificate is broken** — `verify_ssl=False` is the default.
- **Max 1000 records per query** — use bbox queries to page through large areas.
- **~70.5% coverage** — not all properties are registered in the system.
- Server is ArcGIS 10.8 at `geoportal.ancpi.ro`.

## Endpoint Reference

See [ancpi-gis-endpoints.md](ancpi-gis-endpoints.md) for full endpoint documentation.
