"""ANCPI GIS Client — queries Romania's cadastral ArcGIS Server endpoints."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from ancpi.exceptions import ANCPIError, NoResultsError, QueryError, ServiceUnavailableError
from ancpi.models import MODEL_MAP, Feature, QueryResult
from ancpi.transform import PYPROJ_AVAILABLE, needs_transform, transform_response
from ancpi.services import (
    AD_ADDRESSES,
    AU_ADMIN_UNITS,
    BU_BUILDING_SURFACE,
    CP_CADASTRAL_PARCEL,
    DEFAULT_HOST,
    THEMES,
    ServiceLayer,
)

logger = logging.getLogger(__name__)


class ANCPIClient:
    """Client for querying ANCPI's ArcGIS Server REST endpoints.

    Usage:
        client = ANCPIClient()
        result = client.get_parcels_at(26.1, 44.43)
        print(result.to_geojson())
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        verify_ssl: bool = False,
        timeout: float = 30.0,
        max_retries: int = 1,
    ):
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._http = httpx.Client(verify=verify_ssl, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> ANCPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # --- Public query methods ---

    def get_parcel(self, cadastral_ref: str) -> QueryResult:
        """Look up cadastral parcel(s) by national cadastral reference number."""
        return self._query(
            CP_CADASTRAL_PARCEL,
            where=f"nationalCadastralRef='{cadastral_ref}'",
        )

    def get_parcel_by_inspire_id(self, inspire_id: str) -> QueryResult:
        """Look up parcel by INSPIRE local ID (e.g. 'RO.83.40991.102507')."""
        return self._query(
            CP_CADASTRAL_PARCEL,
            where=f"id_localId='{inspire_id}'",
        )

    def get_parcels_at(self, lon: float, lat: float) -> QueryResult:
        """Find cadastral parcels at a geographic point (WGS84)."""
        return self._spatial_query(CP_CADASTRAL_PARCEL, point=(lon, lat))

    def get_parcels_in_bbox(
        self, xmin: float, ymin: float, xmax: float, ymax: float
    ) -> QueryResult:
        """Find cadastral parcels within a bounding box (WGS84)."""
        return self._spatial_query(
            CP_CADASTRAL_PARCEL, bbox=(xmin, ymin, xmax, ymax)
        )

    def get_buildings_at(self, lon: float, lat: float) -> QueryResult:
        """Find buildings at a geographic point (WGS84)."""
        return self._spatial_query(BU_BUILDING_SURFACE, point=(lon, lat))

    def get_buildings_in_bbox(
        self, xmin: float, ymin: float, xmax: float, ymax: float
    ) -> QueryResult:
        """Find buildings within a bounding box (WGS84)."""
        return self._spatial_query(
            BU_BUILDING_SURFACE, bbox=(xmin, ymin, xmax, ymax)
        )

    def get_addresses_at(self, lon: float, lat: float) -> QueryResult:
        """Find addresses near a geographic point (WGS84)."""
        return self._spatial_query(AD_ADDRESSES, point=(lon, lat))

    def get_admin_unit(self, nuts_code: str) -> QueryResult:
        """Look up administrative unit by NUTS code (e.g. 'RO321' for Bucharest)."""
        return self._query(
            AU_ADMIN_UNITS,
            where=f"NUTSCode='{nuts_code}'",
        )

    def get_layer_info(self, theme: str) -> dict[str, Any]:
        """Get metadata for a theme's default layer (fields, extent, etc.)."""
        theme = theme.upper()
        if theme not in THEMES:
            raise ANCPIError(f"Unknown theme '{theme}'. Available: {', '.join(THEMES)}")

        layer = THEMES[theme]["default"]
        urls = layer.metadata_urls(self.host)
        return self._request_with_fallback(urls, {"f": "json"}, theme)

    def get_service_info(self, theme: str) -> dict[str, Any]:
        """Get service-level metadata for a theme."""
        theme = theme.upper()
        if theme not in THEMES:
            raise ANCPIError(f"Unknown theme '{theme}'. Available: {', '.join(THEMES)}")

        layer = THEMES[theme]["default"]
        urls = layer.service_urls(self.host)
        return self._request_with_fallback(urls, {"f": "json"}, theme)

    # --- Internal methods ---

    def _query(
        self,
        layer: ServiceLayer,
        where: str = "1=1",
        return_geometry: bool = True,
        out_fields: str = "*",
        result_count: int = 1000,
        out_sr: int = 4326,
    ) -> QueryResult:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": str(return_geometry).lower(),
            "outSR": str(out_sr),
            "resultRecordCount": str(result_count),
            "f": "json",
        }
        urls = layer.query_urls(self.host)
        data = self._request_with_fallback(urls, params, layer.theme)
        return self._parse_response(data, layer)

    def _spatial_query(
        self,
        layer: ServiceLayer,
        point: tuple[float, float] | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        return_geometry: bool = True,
        out_fields: str = "*",
        result_count: int = 1000,
        out_sr: int = 4326,
    ) -> QueryResult:
        params: dict[str, str] = {
            "outFields": out_fields,
            "returnGeometry": str(return_geometry).lower(),
            "outSR": str(out_sr),
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "resultRecordCount": str(result_count),
            "f": "json",
        }

        if point:
            params["geometry"] = json.dumps({"x": point[0], "y": point[1]})
            params["geometryType"] = "esriGeometryPoint"
        elif bbox:
            params["geometry"] = json.dumps({
                "xmin": bbox[0], "ymin": bbox[1],
                "xmax": bbox[2], "ymax": bbox[3],
            })
            params["geometryType"] = "esriGeometryEnvelope"

        urls = layer.query_urls(self.host)
        data = self._request_with_fallback(urls, params, layer.theme)
        return self._parse_response(data, layer)

    def _request_with_fallback(
        self, urls: list[str], params: dict[str, str], theme: str
    ) -> dict[str, Any]:
        """Try each URL in order, return first successful JSON response."""
        tried = []
        last_error = None

        for url in urls:
            for attempt in range(1 + self.max_retries):
                if attempt > 0:
                    time.sleep(1.0 * attempt)
                    logger.debug("Retry %d for %s", attempt, url)

                try:
                    logger.debug("GET %s %s", url, params)
                    resp = self._http.get(url, params=params)

                    if resp.status_code == 502:
                        logger.warning("502 Proxy Error from %s", url)
                        last_error = f"502 from {url}"
                        break  # don't retry 502, try next path

                    resp.raise_for_status()

                    content_type = resp.headers.get("content-type", "")
                    if "html" in content_type:
                        logger.warning("Got HTML response from %s", url)
                        last_error = f"HTML response from {url}"
                        break

                    data = resp.json()

                    if "error" in data:
                        err = data["error"]
                        code = err.get("code", 0)
                        msg = err.get("message", "Unknown error")
                        if code == 400:
                            raise QueryError(code, msg, err.get("details"))
                        logger.warning("Error %d from %s: %s", code, url, msg)
                        last_error = f"Error {code}: {msg}"
                        break

                    return data

                except httpx.TimeoutException:
                    logger.warning("Timeout from %s", url)
                    last_error = f"Timeout from {url}"
                except httpx.HTTPStatusError as e:
                    logger.warning("HTTP %d from %s", e.response.status_code, url)
                    last_error = f"HTTP {e.response.status_code} from {url}"
                except QueryError:
                    raise
                except Exception as e:
                    logger.warning("Error from %s: %s", url, e)
                    last_error = f"{type(e).__name__}: {e}"

            tried.append(url)

        raise ServiceUnavailableError(theme, tried)

    def _parse_response(self, data: dict[str, Any], layer: ServiceLayer) -> QueryResult:
        """Parse ArcGIS JSON response into typed model objects.

        Auto-transforms Stereo70 coordinates to WGS84 if pyproj is available.
        """
        # Check if response is in Stereo70 and transform if possible
        sr = data.get("spatialReference", {})
        source_wkid = needs_transform(sr)
        if source_wkid:
            if PYPROJ_AVAILABLE:
                logger.info(
                    "Response in EPSG:%d (Stereo70), transforming to WGS84", source_wkid
                )
                data = transform_response(data, source_wkid)
            else:
                logger.warning(
                    "Response in EPSG:%d (Stereo70) but pyproj not installed. "
                    "Coordinates will be in Stereo70. Install with: pip install ancpi[transform]",
                    source_wkid,
                )

        features_raw = data.get("features", [])
        exceeded = data.get("exceededTransferLimit", False)

        model_cls = MODEL_MAP.get(layer.theme, Feature)
        features = []
        for f in features_raw:
            attrs = f.get("attributes", {})
            geom = f.get("geometry")
            features.append(model_cls.from_esri(attrs, geom))

        return QueryResult(features=features, exceeded_transfer_limit=exceeded)
