# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python client library + CLI for querying Romania's ANCPI (National Agency for Cadastre and Land Registration) geoportal ArcGIS Server endpoints. Looks up cadastral parcels, buildings, addresses, and administrative units by cadastral number, INSPIRE ID, or spatial queries.

## Development Commands

```bash
# Setup
uv venv
uv pip install -e ".[all]"       # all optional deps (pyproj, shapely, geojson)
source .venv/bin/activate

# Run CLI
ancpi parcel 102507               # by cadastral ref
ancpi parcel --at 26.1,44.43     # spatial query
ancpi --format geojson admin RO321
ancpi info CP                     # layer metadata (always works even when query endpoints are down)

# No test suite, linter, or CI exists yet
```

## Architecture

The `ancpi/` package has a layered design:

- **`services.py`** — Service registry. `ServiceLayer` frozen dataclasses define each ArcGIS MapServer layer (theme, layer_id, endpoint paths). Each layer has ordered `base_paths` (`/arcgis/`, `/inspireview/`) for fallback. `THEMES` dict maps theme codes (CP, BU, AD, AU) to their layers.

- **`client.py`** — `ANCPIClient` is the core HTTP class using `httpx` with `verify=False` (ANCPI's SSL cert chain is broken). `_request_with_fallback()` tries each URL path in order, handles 502s, timeouts, and HTML error responses. Public methods (`get_parcel`, `get_parcels_at`, `get_buildings_at`, etc.) call internal `_query`/`_spatial_query` which build ArcGIS REST params and parse responses.

- **`models.py`** — Dataclasses (`Feature`, `Parcel`, `Building`, `Address`, `AdminUnit`) parsed from ESRI JSON. `QueryResult` wraps a feature list and provides `to_geojson()`, `to_kml()`, `to_dicts()` export. ESRI→GeoJSON and ESRI→KML geometry conversion is in the `Feature` base class.

- **`transform.py`** — Optional Stereo70 (EPSG:3844) → WGS84 coordinate transformation via `pyproj`. Auto-detects Stereo70 spatial references in responses and transforms in `client.py:_parse_response()`. Gracefully degrades when `pyproj` isn't installed.

- **`cli.py`** — Click CLI with commands: `parcel`, `building`, `address`, `admin`, `info`. Global options: `--format json|geojson|kml|table`, `--output`, `--no-geometry`, `--verbose`. Auto-detects terminal vs pipe for default format.

- **`exceptions.py`** — `ANCPIError` base, `ServiceUnavailableError` (all paths failed), `QueryError` (server error JSON), `NoResultsError`.

## Key Constraints

- **CP and BU endpoints are frequently down** (502/timeout on ANCPI's side). AU and metadata endpoints are stable. Always test with `ancpi info <theme>` first.
- All requests use `outSR=4326` to request WGS84 from the server. If the server returns Stereo70 instead, the transform module handles it.
- Max 1000 records per query (ArcGIS Server limit).
- `ancpi-gis-endpoints.md` contains detailed endpoint research and is the reference doc for all ANCPI URLs and layer schemas.
