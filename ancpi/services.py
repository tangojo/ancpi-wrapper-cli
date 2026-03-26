"""Service layer definitions for ANCPI ArcGIS endpoints."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceLayer:
    """Defines an ANCPI ArcGIS MapServer layer."""

    theme: str
    name: str
    layer_id: int
    service_path: str  # e.g. "CP/CP_View/MapServer"
    geometry_type: str  # esriGeometryPolygon, esriGeometryPoint, etc.
    key_field: str | None = None  # primary lookup field
    base_paths: tuple[str, ...] = field(default_factory=lambda: (
        "/arcgis/rest/services",
        "/inspireview/rest/services",
    ))

    def query_urls(self, host: str) -> list[str]:
        """Return ordered list of full query URLs to try."""
        return [
            f"{host}{base}/{self.service_path}/{self.layer_id}/query"
            for base in self.base_paths
        ]

    def metadata_urls(self, host: str) -> list[str]:
        """Return ordered list of full metadata URLs to try."""
        return [
            f"{host}{base}/{self.service_path}/{self.layer_id}"
            for base in self.base_paths
        ]

    def service_urls(self, host: str) -> list[str]:
        """Return ordered list of full service URLs to try."""
        return [
            f"{host}{base}/{self.service_path}"
            for base in self.base_paths
        ]


# --- Cadastral Parcels (CP) ---

CP_CADASTRAL_ZONING = ServiceLayer(
    theme="CP",
    name="Cadastral Zoning",
    layer_id=0,
    service_path="CP/CP_View/MapServer",
    geometry_type="esriGeometryPolygon",
)

CP_CADASTRAL_PARCEL = ServiceLayer(
    theme="CP",
    name="Cadastral Parcel",
    layer_id=1,
    service_path="CP/CP_View/MapServer",
    geometry_type="esriGeometryPolygon",
    key_field="nationalCadastralRef",
)

CP_CADASTRAL_BOUNDARY = ServiceLayer(
    theme="CP",
    name="Cadastral Boundary",
    layer_id=2,
    service_path="CP/CP_View/MapServer",
    geometry_type="esriGeometryPolyline",
)

# --- Buildings (BU) ---

BU_BUILDING_PART_POINT = ServiceLayer(
    theme="BU",
    name="BuildingPart [Point]",
    layer_id=1,
    service_path="BU/BU_View/MapServer",
    geometry_type="esriGeometryPoint",
)

BU_BUILDING_PART_SURFACE = ServiceLayer(
    theme="BU",
    name="BuildingPart [Surface]",
    layer_id=2,
    service_path="BU/BU_View/MapServer",
    geometry_type="esriGeometryPolygon",
)

BU_BUILDING_POINT = ServiceLayer(
    theme="BU",
    name="Building [Point]",
    layer_id=4,
    service_path="BU/BU_View/MapServer",
    geometry_type="esriGeometryPoint",
)

BU_BUILDING_SURFACE = ServiceLayer(
    theme="BU",
    name="Building [Surface]",
    layer_id=5,
    service_path="BU/BU_View/MapServer",
    geometry_type="esriGeometryPolygon",
)

# --- Addresses (AD) ---

AD_ADDRESSES = ServiceLayer(
    theme="AD",
    name="Addresses",
    layer_id=0,
    service_path="AD/AD_View/MapServer",
    geometry_type="esriGeometryPoint",
)

# --- Administrative Units (AU) ---

AU_ADMIN_UNITS = ServiceLayer(
    theme="AU",
    name="Administrative Units",
    layer_id=0,
    service_path="AU/AU_View/MapServer",
    geometry_type="esriGeometryPolygon",
    key_field="NUTSCode",
)

# --- Lookup tables ---

THEMES = {
    "CP": {
        "name": "Cadastral Parcels",
        "layers": {
            "zoning": CP_CADASTRAL_ZONING,
            "parcel": CP_CADASTRAL_PARCEL,
            "boundary": CP_CADASTRAL_BOUNDARY,
        },
        "default": CP_CADASTRAL_PARCEL,
    },
    "BU": {
        "name": "Buildings",
        "layers": {
            "building_part_point": BU_BUILDING_PART_POINT,
            "building_part_surface": BU_BUILDING_PART_SURFACE,
            "building_point": BU_BUILDING_POINT,
            "building_surface": BU_BUILDING_SURFACE,
        },
        "default": BU_BUILDING_SURFACE,
    },
    "AD": {
        "name": "Addresses",
        "layers": {
            "addresses": AD_ADDRESSES,
        },
        "default": AD_ADDRESSES,
    },
    "AU": {
        "name": "Administrative Units",
        "layers": {
            "admin_units": AU_ADMIN_UNITS,
        },
        "default": AU_ADMIN_UNITS,
    },
}

DEFAULT_HOST = "https://geoportal.ancpi.ro"
