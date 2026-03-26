"""Data models for ANCPI GIS features."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring


def _parse_esri_date(ms: int | None) -> datetime | None:
    """Convert ESRI epoch milliseconds to datetime."""
    if ms is None or ms < 0:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _rings_to_geojson_coords(rings: list[list[list[float]]]) -> list:
    """Convert ESRI rings to GeoJSON polygon coordinates."""
    return [[[pt[0], pt[1]] for pt in ring] for ring in rings]


@dataclass
class Feature:
    """Base class for all GIS features."""

    object_id: int | None
    inspire_id: str | None
    inspire_namespace: str | None
    geometry: dict[str, Any] | None
    raw_attributes: dict[str, Any] = field(repr=False)

    def to_dict(self, include_geometry: bool = True) -> dict[str, Any]:
        result = {k: v for k, v in self.raw_attributes.items()}
        if include_geometry and self.geometry:
            result["geometry"] = self.geometry
        return result

    def to_geojson_feature(self, include_geometry: bool = True) -> dict[str, Any]:
        """Convert to a GeoJSON Feature."""
        geojson_geom = None
        if include_geometry and self.geometry:
            geojson_geom = self._esri_to_geojson_geometry(self.geometry)

        properties = {
            k: v for k, v in self.raw_attributes.items()
            if k not in ("SHAPE", "SHAPE_Length", "SHAPE_Area")
        }
        return {
            "type": "Feature",
            "properties": properties,
            "geometry": geojson_geom,
        }

    def to_kml_placemark(self, include_geometry: bool = True) -> Element:
        """Convert to a KML Placemark element."""
        pm = Element("Placemark")

        # Name
        name = self.inspire_id or str(self.object_id or "")
        SubElement(pm, "name").text = name

        # Description as plain text key=value pairs (avoids CDATA escaping issues)
        desc_parts = []
        for k, v in self.raw_attributes.items():
            if k in ("SHAPE", "SHAPE_Length", "SHAPE_Area"):
                continue
            if v is not None:
                desc_parts.append(f"{k}: {v}")
        if desc_parts:
            SubElement(pm, "description").text = "\n".join(desc_parts)

        # Geometry
        if include_geometry and self.geometry:
            geom_el = self._esri_to_kml_geometry(self.geometry)
            if geom_el is not None:
                pm.append(geom_el)

        return pm

    @staticmethod
    def _esri_to_kml_geometry(esri_geom: dict) -> Element | None:
        """Convert ESRI geometry to KML geometry element."""
        if "rings" in esri_geom:
            if len(esri_geom["rings"]) == 1:
                poly = Element("Polygon")
                outer = SubElement(poly, "outerBoundaryIs")
                ring = SubElement(outer, "LinearRing")
                coords = " ".join(
                    f"{pt[0]},{pt[1]},0" for pt in esri_geom["rings"][0]
                )
                SubElement(ring, "coordinates").text = coords
                return poly
            else:
                multi = Element("MultiGeometry")
                for ring_coords in esri_geom["rings"]:
                    poly = SubElement(multi, "Polygon")
                    outer = SubElement(poly, "outerBoundaryIs")
                    ring = SubElement(outer, "LinearRing")
                    coords = " ".join(
                        f"{pt[0]},{pt[1]},0" for pt in ring_coords
                    )
                    SubElement(ring, "coordinates").text = coords
                return multi
        if "paths" in esri_geom:
            if len(esri_geom["paths"]) == 1:
                ls = Element("LineString")
                coords = " ".join(
                    f"{pt[0]},{pt[1]},0" for pt in esri_geom["paths"][0]
                )
                SubElement(ls, "coordinates").text = coords
                return ls
            else:
                multi = Element("MultiGeometry")
                for path in esri_geom["paths"]:
                    ls = SubElement(multi, "LineString")
                    coords = " ".join(f"{pt[0]},{pt[1]},0" for pt in path)
                    SubElement(ls, "coordinates").text = coords
                return multi
        if "x" in esri_geom and "y" in esri_geom:
            pt = Element("Point")
            SubElement(pt, "coordinates").text = f"{esri_geom['x']},{esri_geom['y']},0"
            return pt
        return None

    @staticmethod
    def _esri_to_geojson_geometry(esri_geom: dict) -> dict | None:
        if "rings" in esri_geom:
            coords = _rings_to_geojson_coords(esri_geom["rings"])
            if len(coords) == 1:
                return {"type": "Polygon", "coordinates": coords}
            return {"type": "MultiPolygon", "coordinates": [[ring] for ring in coords]}
        if "paths" in esri_geom:
            paths = esri_geom["paths"]
            if len(paths) == 1:
                return {"type": "LineString", "coordinates": paths[0]}
            return {"type": "MultiLineString", "coordinates": paths}
        if "x" in esri_geom and "y" in esri_geom:
            return {"type": "Point", "coordinates": [esri_geom["x"], esri_geom["y"]]}
        return None


@dataclass
class Parcel(Feature):
    """A cadastral parcel."""

    cadastral_ref: str | None = None
    area: float | None = None
    area_uom: str | None = None
    valid_from: datetime | None = None
    label: str | None = None

    @classmethod
    def from_esri(cls, attrs: dict, geometry: dict | None = None) -> Parcel:
        return cls(
            object_id=attrs.get("OBJECTID"),
            inspire_id=attrs.get("id_localId"),
            inspire_namespace=attrs.get("id_namespace"),
            geometry=geometry,
            raw_attributes=attrs,
            cadastral_ref=attrs.get("nationalCadastralRef"),
            area=attrs.get("areaValue"),
            area_uom=attrs.get("areaValue_uom"),
            valid_from=_parse_esri_date(attrs.get("validFrom")),
            label=attrs.get("label"),
        )


@dataclass
class Building(Feature):
    """A building or building part."""

    @classmethod
    def from_esri(cls, attrs: dict, geometry: dict | None = None) -> Building:
        return cls(
            object_id=attrs.get("OBJECTID"),
            inspire_id=attrs.get("id_localId"),
            inspire_namespace=attrs.get("id_namespace"),
            geometry=geometry,
            raw_attributes=attrs,
        )


@dataclass
class Address(Feature):
    """An address point."""

    @classmethod
    def from_esri(cls, attrs: dict, geometry: dict | None = None) -> Address:
        return cls(
            object_id=attrs.get("OBJECTID"),
            inspire_id=attrs.get("id_localId"),
            inspire_namespace=attrs.get("id_namespace"),
            geometry=geometry,
            raw_attributes=attrs,
        )


@dataclass
class AdminUnit(Feature):
    """An administrative unit (NUTS region, county, municipality)."""

    nuts_code: str | None = None

    @classmethod
    def from_esri(cls, attrs: dict, geometry: dict | None = None) -> AdminUnit:
        return cls(
            object_id=attrs.get("OBJECTID"),
            inspire_id=attrs.get("id_localId"),
            inspire_namespace=attrs.get("id_namespace"),
            geometry=geometry,
            raw_attributes=attrs,
            nuts_code=attrs.get("NUTSCode"),
        )


# Model registry keyed by theme
MODEL_MAP: dict[str, type[Feature]] = {
    "CP": Parcel,
    "BU": Building,
    "AD": Address,
    "AU": AdminUnit,
}


@dataclass
class QueryResult:
    """Container for query results."""

    features: list[Feature]
    exceeded_transfer_limit: bool = False

    @property
    def count(self) -> int:
        return len(self.features)

    def to_geojson(self, include_geometry: bool = True) -> dict[str, Any]:
        """Convert all features to a GeoJSON FeatureCollection."""
        return {
            "type": "FeatureCollection",
            "features": [f.to_geojson_feature(include_geometry) for f in self.features],
        }

    def to_geojson_str(self, include_geometry: bool = True, indent: int = 2) -> str:
        return json.dumps(self.to_geojson(include_geometry), indent=indent)

    def to_dicts(self, include_geometry: bool = True) -> list[dict[str, Any]]:
        return [f.to_dict(include_geometry) for f in self.features]

    def to_kml(self, include_geometry: bool = True) -> Element:
        """Convert all features to a KML Document."""
        kml = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        doc = SubElement(kml, "Document")
        SubElement(doc, "name").text = "ANCPI Export"

        # Add a default style for polygons
        style = SubElement(doc, "Style", id="default")
        line_style = SubElement(style, "LineStyle")
        SubElement(line_style, "color").text = "ff0000ff"  # red
        SubElement(line_style, "width").text = "2"
        poly_style = SubElement(style, "PolyStyle")
        SubElement(poly_style, "color").text = "400000ff"  # semi-transparent red

        for feat in self.features:
            pm = feat.to_kml_placemark(include_geometry)
            SubElement(pm, "styleUrl").text = "#default"
            doc.append(pm)

        return kml

    def to_kml_str(self, include_geometry: bool = True) -> str:
        """Convert all features to a KML string."""
        kml = self.to_kml(include_geometry)
        xml_bytes = tostring(kml, encoding="unicode", xml_declaration=False)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes
