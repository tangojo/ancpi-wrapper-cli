"""Coordinate transformation between Stereo70 (EPSG:3844) and WGS84 (EPSG:4326).

Requires the optional 'pyproj' dependency:
    pip install ancpi[transform]
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Known Stereo70 spatial reference WKIDs
STEREO70_WKIDS = {3844, 31700}
WGS84_WKID = 4326
ETRS89_WKID = 4258

# WKIDs that don't need transformation (already geographic/WGS84-compatible)
GEOGRAPHIC_WKIDS = {WGS84_WKID, ETRS89_WKID}

try:
    from pyproj import Transformer

    _transformer_cache: dict[tuple[int, int], Transformer] = {}

    def _get_transformer(from_epsg: int, to_epsg: int) -> Transformer:
        key = (from_epsg, to_epsg)
        if key not in _transformer_cache:
            _transformer_cache[key] = Transformer.from_crs(
                f"EPSG:{from_epsg}", f"EPSG:{to_epsg}", always_xy=True
            )
        return _transformer_cache[key]

    PYPROJ_AVAILABLE = True

except ImportError:
    PYPROJ_AVAILABLE = False


def needs_transform(spatial_ref: dict[str, Any] | None) -> int | None:
    """Check if a spatial reference needs transformation to WGS84.

    Returns the source WKID if transformation is needed, None otherwise.
    """
    if not spatial_ref:
        return None
    wkid = spatial_ref.get("wkid") or spatial_ref.get("latestWkid")
    if wkid and wkid in STEREO70_WKIDS:
        return wkid
    return None


def transform_point(x: float, y: float, from_epsg: int) -> tuple[float, float]:
    """Transform a single point from the given CRS to WGS84.

    Returns (lon, lat) in WGS84.
    """
    if not PYPROJ_AVAILABLE:
        raise ImportError(
            "pyproj is required for Stereo70 coordinate transformation. "
            "Install with: pip install ancpi[transform]"
        )
    t = _get_transformer(from_epsg, WGS84_WKID)
    return t.transform(x, y)


def transform_geometry(
    esri_geom: dict[str, Any], from_epsg: int
) -> dict[str, Any]:
    """Transform an ESRI geometry dict from the given CRS to WGS84.

    Handles Point (x/y), Polygon (rings), and Polyline (paths).
    Returns a new dict with transformed coordinates.
    """
    if not PYPROJ_AVAILABLE:
        raise ImportError(
            "pyproj is required for Stereo70 coordinate transformation. "
            "Install with: pip install ancpi[transform]"
        )

    t = _get_transformer(from_epsg, WGS84_WKID)
    result = {}

    if "x" in esri_geom and "y" in esri_geom:
        lon, lat = t.transform(esri_geom["x"], esri_geom["y"])
        result["x"] = lon
        result["y"] = lat

    elif "rings" in esri_geom:
        result["rings"] = [
            [list(t.transform(pt[0], pt[1])) for pt in ring]
            for ring in esri_geom["rings"]
        ]

    elif "paths" in esri_geom:
        result["paths"] = [
            [list(t.transform(pt[0], pt[1])) for pt in path]
            for path in esri_geom["paths"]
        ]

    # Preserve any other keys except spatialReference
    for k, v in esri_geom.items():
        if k not in ("x", "y", "rings", "paths", "spatialReference"):
            result[k] = v

    result["spatialReference"] = {"wkid": WGS84_WKID}
    return result


def transform_response(data: dict[str, Any], source_wkid: int) -> dict[str, Any]:
    """Transform all geometries in an ArcGIS JSON response from Stereo70 to WGS84.

    Modifies the response in-place and returns it.
    """
    features = data.get("features", [])
    for feature in features:
        geom = feature.get("geometry")
        if geom:
            feature["geometry"] = transform_geometry(geom, source_wkid)

    # Update the spatial reference in the response
    if "spatialReference" in data:
        data["spatialReference"] = {"wkid": WGS84_WKID}

    return data
