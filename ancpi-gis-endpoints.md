# ANCPI Geoportal - Romanian Property GIS Endpoints

## Overview

Romania's National Agency for Cadastre and Land Registration (ANCPI) operates a public geoportal at `geoportal.ancpi.ro` powered by **ArcGIS Server 10.8**. It provides INSPIRE-compliant geospatial services for cadastral parcels, buildings, addresses, administrative units, and more.

**Coverage:** ~70.5% of Romania's estimated 40 million properties (as of 2026).

**Known Issues:**
- SSL certificate chain is broken — programmatic access requires skipping cert verification (`-k` in curl, `verify=False` in Python requests)
- The `/maps/` HTML directory is disabled — append `?f=json` to discover services
- Bulk download is restricted — individual parcel queries only
- CP WMS endpoint returns intermittent 502 errors

---

## Server Instances

Three separate ArcGIS Server 10.8 instances run on `geoportal.ancpi.ro`:

| Base Path | Purpose | Notes |
|-----------|---------|-------|
| `/inspireview/rest/services` | INSPIRE View services | Full HTML directory enabled |
| `/maps/rest/services` | Main map/cadastral services | HTML directory disabled, use `?f=json` |
| `/arcgis/rest/services` | Additional INSPIRE services | Partially accessible |

---

## INSPIRE View Services (`/inspireview/rest/services`)

All services use **EPSG:4258** (ETRS89) spatial reference.

### Themes & Layers

| Folder | Service | Layers | Min Scale |
|--------|---------|--------|-----------|
| **AD** | AD/AD_View (MapServer) | `0: Addresses` | — |
| **AU** | AU/AU_View (MapServer) | Administrative Units | — |
| **BU** | BU/BU_View (MapServer) | `0: BuildingPart` (group), `1: BuildingPart [Point]`, `2: BuildingPart [Surface]`, `3: Building` (group), `4: Building [Point]`, `5: Building [Surface]` | 1:10,000 - 1:25,000 |
| **CP** | CP/CP_View (MapServer) | `0: Cadastral Zoning`, `1: Cadastral Parcel`, `2: Cadastral Boundary` | 1:10,000 |
| **GG** | GG/GG_View (MapServer) | Geographical Grid (LAEA) | — |
| **GN** | GN/GN_View (MapServer) | Geographical Names | — |
| **HY** | HY/HY_View (MapServer) | Hydrography | — |
| **OI** | OI/OI_Index + OI/OI_View (MapServer) | Orthoimagery index + view | — |
| **RS** | RS/RS_View (MapServer) | Reference Systems | — |
| **TN** | TN/TN_View (MapServer) | Transport Networks (14+ layers: roads, railways, waterways, ports, generic transport) | — |
| **US** | US/US_View (MapServer) | Utility Services | — |

### Root-level Services

| Service | Type |
|---------|------|
| CheckErrors | GPServer |
| UploadTool | GPServer |
| UtilitatiStereo | MapServer |

### URL Patterns

**REST Query:**
```
https://geoportal.ancpi.ro/inspireview/rest/services/{THEME}/{THEME}_View/MapServer/{LAYER_ID}/query?f=geojson&where=...
```

**WMS GetCapabilities:**
```
https://geoportal.ancpi.ro/inspireview/rest/services/{THEME}/{THEME}_View/MapServer/exts/InspireView/service?SERVICE=WMS&REQUEST=GetCapabilities
```

**INSPIRE Domain Info:**
```
https://geoportal.ancpi.ro/inspireview/rest/services/{THEME}/{THEME}_View/MapServer/exts/InspireView/domainInfo
```

---

## Main Map Services (`/maps/rest/services`)

### Folders & Services

| Folder | Services |
|--------|----------|
| **Administrativ/** | Administrativ, Administrativ_nou, Administrativ_download, LimiteBasemap, NoBasemap |
| **ANCPI/** | CP_Yellow, CP_Yellow_Vidra, CP_Yellow_vt, LAKI_MNT, MNT (terrain model), TopRo5_Topo, TopRo5_Topo_3844 |
| **apia/** | (empty or restricted) |
| **Descarcare/** | MNT_Descarcare, PUG, SectoareCadastrale, TopRO50_UAT_Descarcare, TopRO_Descarcare |
| **Imobile/** | Imobile_3844 |
| **Ortofoto/** | GrilaMozaic, Laki_2_Liv9, Mozaic, Mozaic_vt, Ortofoto2005 (+_3844), Ortofoto2008 (+_3844), Ortofoto2009 (+_3844), Ortofoto2010 (+_3844), Ortofoto2012 (+_3844), Ortofoto2016, Ortofoto2019, Ortofoto2020 |
| **TopRO5/** | Acoperire (land cover), Adrese (addresses), Cladiri (buildings), Hidrografie (hydrography), Toponime (place names), Transporturi (transport) |

### eterra3_publish (Root-level)

Cached/tiled MapServer with **Data + Query** capabilities.

**Layers:**
- `0`: Constructii (Buildings)
- `1`: Parcele cadastrale (Cadastral Parcels)

**Spatial Reference:** EPSG:31700 (Stereo70 old)

**Query Endpoints:**
```
https://geoportal.ancpi.ro/maps/rest/services/eterra3_publish/MapServer/0/query  # Buildings
https://geoportal.ancpi.ro/maps/rest/services/eterra3_publish/MapServer/1/query  # Parcels
```

---

## Query Parameters (ArcGIS REST API)

Standard ArcGIS MapServer query parameters apply:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `f` | Output format | `json`, `geojson`, `pjson` |
| `where` | SQL WHERE clause | `INSPIRE_ID='RO.83.40991.102507'` |
| `geometry` | Spatial filter geometry | JSON envelope or point |
| `geometryType` | Type of geometry filter | `esriGeometryEnvelope`, `esriGeometryPoint` |
| `spatialRel` | Spatial relationship | `esriSpatialRelIntersects` |
| `outFields` | Fields to return | `*` for all |
| `outSR` | Output spatial reference | `4326` for WGS84 |
| `inSR` | Input spatial reference | `4326` |
| `returnGeometry` | Include geometry | `true` / `false` |
| `resultOffset` | Pagination offset | `0` |
| `resultRecordCount` | Max records per page | `1000` (server max) |
| `returnIdsOnly` | Return only object IDs | `true` / `false` |
| `returnCountOnly` | Return only count | `true` / `false` |
| `orderByFields` | Sort order | field name + `ASC`/`DESC` |
| `outStatistics` | Aggregation/statistics | JSON statistics definition |

### INSPIRE_ID Format

```
RO.<county_code>.<UAT_code>.<cadastral_number>
```

Example: `RO.83.40991.102507`

---

## Example Queries

### Query cadastral parcel by INSPIRE_ID (GeoJSON)
```
https://geoportal.ancpi.ro/inspireview/rest/services/CP/CP_View/MapServer/1/query?f=geojson&where=INSPIRE_ID='RO.83.40991.102507'&outFields=*
```

### Query cadastral parcel by INSPIRE_ID (eterra3)
```
https://geoportal.ancpi.ro/maps/rest/services/eterra3_publish/MapServer/1/query?f=geojson&where=INSPIRE_ID='RO.83.40991.102507'&outFields=*
```

### Spatial query (find parcels intersecting a point)
```
https://geoportal.ancpi.ro/inspireview/rest/services/CP/CP_View/MapServer/1/query?f=geojson&geometry={"x":26.1,"y":44.4}&geometryType=esriGeometryPoint&spatialRel=esriSpatialRelIntersects&inSR=4326&outFields=*
```

### Get buildings in an area (envelope)
```
https://geoportal.ancpi.ro/inspireview/rest/services/BU/BU_View/MapServer/5/query?f=geojson&geometry={"xmin":26.0,"ymin":44.3,"xmax":26.2,"ymax":44.5}&geometryType=esriGeometryEnvelope&spatialRel=esriSpatialRelIntersects&inSR=4326&outFields=*
```

---

## Other Public Portals & Data Sources

### ANCPI Portals

| Portal | URL | Description |
|--------|-----|-------------|
| Geoportal (main) | https://geoportal.ancpi.ro/ | Main entry point |
| Cadastral Map Viewer | https://geoportal.ancpi.ro/geoportal/imobile/Harta.html | Interactive map |
| Cadastral Sectors Viewer | https://geoportal.ancpi.ro/portal/apps/webappviewer/index.html?id=01a39376d558409a93b01a9a15b832e2 | Updated Feb 2026 |
| MyEterra | https://myeterra.ancpi.ro/ | Public property lookup |
| eTerra | https://eterra.ancpi.ro/eterra/ | Internal cadastral system (may require auth) |
| Portal Sharing API | https://geoportal.ancpi.ro/portal/sharing/rest/portals/info | ArcGIS Portal metadata |
| ArcGIS REST SDK | https://geoportal.ancpi.ro/arcgis/sdk/rest/gettingstarted.html | API documentation |

### Government Geoportal

| Portal | URL | Description |
|--------|-----|-------------|
| geoportal.gov.ro | https://geoportal.gov.ro/arcgis/apps/sites/ | Government-wide ArcGIS Hub (currently returning 500) |

### data.europa.eu Datasets (European Open Data Portal)

| Dataset | URL | Status |
|---------|-----|--------|
| Cadastral map 1:50,000 | https://data.europa.eu/data/datasets/-96ae3445-e257-4f53-9574-6348c51a3387-?locale=en | HTTP 200 (SPA shell — verify content loads) |
| Related cadastral dataset | https://data.europa.eu/data/datasets/-964b7bce-7eaa-45d1-bd45-452512e0d759-?locale=en | **Dead/orphaned** — HTTP 200 but dataset not found in data.gov.ro API; empty SPA shell |
| Cadastral plane 1:5,000 | https://data.europa.eu/data/datasets/-884301bf-0ef4-4246-a14f-25c7151ec7c6-?locale=en | HTTP 200 (SPA shell — verify content loads) |

> **Note:** data.europa.eu returns HTTP 200 for all URLs because it's a Vue.js SPA — the shell page always loads. The actual dataset content is fetched via JavaScript. Dataset `964b7bce-...` was not found via the data.gov.ro CKAN API (`package_show`), suggesting it has been removed or was never properly published. The data.gov.ro portal has very limited cadastral data — only 1 result for "cadastr" (a hydrography dataset mislabeled).

**Formats available:** KMZ downloads from data.europa.eu. For FileGeoDatabase, Shapefile, DXF, DGN — requires free registration at ANCPI geoportal.

### data.gov.ro Datasets

Administrative boundary KMZ/SHP files are available on data.gov.ro (mirrored to data.europa.eu):
- Territorial Administrative Units (multiple versions: 2020-2024)
- Latest (March 2024) includes **SHP format**: `unitate_administrativa_judet.zip`, `unitate_administrativa_uat.zip`

### Third-Party APIs

| Service | URL | Description |
|---------|-----|-------------|
| API Store - ANCPI | https://api.store/romania-api/ancpi-api | REST API wrapper |
| API Store - Real Estate | https://api.store/romania-api/ancpi-api/real-estate-api | Property bodies with cadastral numbers |
| API Store - Cadastral Plots | https://api.store/romania-api/ancpi-api/cadastral-plots-api | Cadastral plot data |
| API Store - Map 1:50,000 | https://api.store/romania-api/ancpi-api/cadastral-map-with-scale-level-150000-api | Cadastral map |

---

## Spatial References

| EPSG | Name | Used In |
|------|------|---------|
| 4258 | ETRS89 | INSPIRE View services |
| 3844 | Stereo70 (Pulkovo 1942) | `_3844` suffixed services, Imobile |
| 31700 | Stereo70 (old) | eterra3_publish |
| 4326 | WGS84 | Can be used as `outSR` parameter |

---

## Key References

- [Alin Panaitiu - Fetching land coordinates from Romania's Geoportal](https://notes.alinpanaitiu.com/Fetching-land-coordinates-from-Romania's-Geoportal) — Detailed technical writeup on querying the API
- [Dateno - ANCPI InspireView catalog](https://dateno.io/registry/catalog/temp00001656/) — Service catalog
- [EuroGeographics - Romania](https://eurogeographics.org/member/national-agency-for-cadastre-and-land-registration-of-romania/) — ANCPI international profile
- [INSPIRE Geoportal (EU)](https://inspire-geoportal.ec.europa.eu/) — Central European INSPIRE access point
- [QGIS Developer thread](https://www.mail-archive.com/qgis-developer@lists.osgeo.org/msg55756.html) — Notes on disabled HTML directory workaround
