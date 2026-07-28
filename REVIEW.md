# Code Review & Implementation Plan

**Date:** 2026-07-28
**Reviewed commit:** `28fac45` (working tree clean)
**Scope:** full `ancpi/` package (1202 LOC), `pyproject.toml`, `ancpi-gis-endpoints.md`

---

## 0. Blocking context: ANCPI is offline and its hostname is gone

Before anything else — **`geoportal.ancpi.ro` does not currently resolve.** This is not a
local/network artifact; the record has been withdrawn from DNS.

Diagnostic evidence:

| Check | Result |
|---|---|
| `example.com`, `pypi.org` | 200 — general internet works |
| `ancpi.ro`, `www.ancpi.ro` | resolve (Cloudflare IPs) |
| `dig ancpi.ro NS` | `cash.ns.cloudflare.com`, `ingrid.ns.cloudflare.com` |
| `dig geoportal.ancpi.ro` | **NXDOMAIN** + authoritative SOA for `ancpi.ro` |
| `dig zzz-nonexistent-test.ancpi.ro` (control) | NXDOMAIN — *byte-identical response* |
| Tavily fetch (external infrastructure) | returned nothing |

The resolver is genuinely recursing into the `ancpi.ro` zone and receiving an authoritative
answer. A corporate blocklist would typically return a sinkhole IP or `REFUSED`; an NXDOMAIN
carrying the correct Cloudflare SOA — identical to a deliberately bogus control name — means
Cloudflare itself reports no `geoportal` label in the zone.

**Cause:** ANCPI has been in a nationwide outage since 23:02 on 13 July 2026. The initial
restoration target of 20 July was missed; on 20 July ANCPI announced migration of all
applications into the Romanian Government Cloud (*Cloudul Guvernamental*), coordinated by STS,
with migration estimated complete 22 July. Services are being restored **in stages**, with no
announced completion date pending a verification report. The `geoportal` hostname appears to
have been withdrawn during migration and not yet republished.

### Consequences for this repo

- **Path-level fallback cannot help.** All three base paths (`/arcgis/`, `/inspireview/`,
  `/maps/`) live under the same dead hostname. Adding more paths is worthless while DNS fails.
- **The `host` parameter is the real escape hatch**, but `DEFAULT_HOST` is a hardcoded
  constant (`services.py:163`). Republication under a new Government Cloud hostname currently
  requires a code change plus a release.
- **Current error messaging is actively misleading** — see item **B4**.
- **Nothing can be verified live.** Items **A3** and **B3** below are inferences from the
  reference doc and one third-party capture; they *must* be confirmed against a live server
  before acting. Everything else is verifiable offline with fixtures, which is the only way to
  make progress until ANCPI returns.

---

## A. Correctness bugs

### A1. Polygon holes are destroyed in GeoJSON and KML export
**`models.py:128` (`_esri_to_geojson_geometry`), `models.py:83` (`_esri_to_kml_geometry`)**
**Severity: high — silent data corruption**

Esri encodes a polygon's outer ring and its holes as *sibling entries* in `rings`,
distinguished only by winding order (outer = clockwise, hole = counter-clockwise). The code
treats every ring as an independent polygon.

Reproduced:

```python
>>> g = {'rings': [[[0,0],[0,10],[10,10],[10,0],[0,0]],   # outer, CW
...                [[2,2],[4,2],[4,4],[2,4],[2,2]]]}      # hole, CCW
>>> Feature._esri_to_geojson_geometry(g)
{'type': 'MultiPolygon',
 'coordinates': [[[[0,0],[0,10],[10,10],[10,0],[0,0]]],
                 [[[2,2],[4,2],[4,4],[2,4],[2,2]]]]}      # two SOLID overlapping polygons
```

A courtyard building, or a parcel with an excluded interior, comes out geometrically wrong.
`_esri_to_kml_geometry` has the same defect and never emits `<innerBoundaryIs>`.

**Fix:** compute each ring's signed area (shoelace). Positive/CW ⇒ starts a new polygon;
negative/CCW ⇒ a hole appended to the most recent polygon. Emit `Polygon` for a single
resulting polygon, `MultiPolygon` for several. For KML, emit one `<outerBoundaryIs>` plus
N `<innerBoundaryIs>` per polygon.

### A2. GeoJSON output violates RFC 7946 winding order
**`models.py:130`**
**Severity: high — renders inverted in common tooling**

RFC 7946 §3.1.6 mandates the right-hand rule: exterior rings counter-clockwise, holes
clockwise. Esri produces the opposite. Rings are copied through unreversed.

Mapbox GL JS enforces winding and will fill the *inverse* of the shape — the entire map minus
the parcel. d3-geo has the same failure mode.

**Fix:** falls out of A1 — reverse each ring to RFC 7946 orientation when emitting.

### A3. Field name mismatch — `id_localId` vs `INSPIRE_ID` ⚠️ NEEDS LIVE VERIFICATION
**`models.py:158`, `client.py:80`, `cli.py:70-76`**
**Severity: high if confirmed**

Two independent sources say the field is `INSPIRE_ID`:
- this repo's own `ancpi-gis-endpoints.md:115` and `:144`
- a third-party capture of a real ANCPI response (`notes.alinpanaitiu.com`), which also shows
  `spatialReference: {wkid: 3844}` — i.e. Stereo70 returned despite `outSR=4326`

The code instead uses `id_localId` in the WHERE clause and in `attrs.get("id_localId")`.
If the doc is right, `get_parcel_by_inspire_id()` returns a server error and every model's
`inspire_id` is silently `None`. The CLI table columns inherit the same assumption.

**Fix:** confirm against a live layer's `fields` list (`ancpi info CP`) first. Then either
correct the constant or, better, resolve the field name from layer metadata at runtime.

### A4. SQL injection / breakage on quotes
**`client.py:71, 73, 80, 115`**
**Severity: medium**

```python
where = f"label='{cadastral_ref}'"
```

Unescaped user input interpolated into a SQL WHERE clause. At minimum an apostrophe breaks the
query; at worst it is injectable against the server's WHERE evaluator.

**Fix:** escape `'` → `''`, and validate inputs against expected patterns (cadastral refs,
INSPIRE IDs and NUTS codes all have well-defined shapes).

### A5. `Feature.from_esri` does not exist
**`client.py:279`**
**Severity: low (latent)**

```python
model_cls = MODEL_MAP.get(layer.theme, Feature)
... model_cls.from_esri(attrs, geom)
```

Confirmed: `hasattr(Feature, 'from_esri') == False`. Any theme not in `MODEL_MAP` raises
`AttributeError` rather than a typed `ANCPIError`. Unreachable for the four current themes,
but a trap for anyone adding a layer.

**Fix:** move the default `from_esri` up to `Feature` (this also resolves **C2**).

---

## B. Functional gaps

### B1. `exceededTransferLimit` is detected but never acted upon
**`client.py:277`**
**Severity: high — silent truncation**

The flag is surfaced as a "results were truncated" warning and then ignored. Esri's
documentation is explicit that clients should page via `resultOffset` / `resultRecordCount`
until the flag returns false, and should **rely on the flag rather than the returned row
count** (internal spatial-index filtering can set it even below the requested count, and can
even return zero rows while more remain).

Any bbox query over a Romanian city silently truncates at 1000 features today.

**Fix:** auto-paginating loop in `_query` / `_spatial_query`, looping until
`exceededTransferLimit` is false; expose `max_features` to bound it.

### B2. `result_count=1000` is hardcoded
**`client.py:146, 168`**

The real ceiling is the layer's `maxRecordCount` — which is already fetched in
`get_layer_info()` and rendered by the CLI (`cli.py:248`). Read it instead of assuming.

**Fix:** lazily fetch and cache layer metadata per `ServiceLayer`; use its `maxRecordCount`.

### B3. Missing `/maps/eterra3_publish` fallback ⚠️ DEPRIORITISED — see §0
**`services.py:16-19`**

`ancpi-gis-endpoints.md:100-104` records
`geoportal.ancpi.ro/maps/rest/services/eterra3_publish/MapServer/{0,1}/query` as an
alternative source for exactly the two themes documented as least reliable (0 = buildings,
1 = parcels). Note the layer IDs differ from the INSPIRE services, so `ServiceLayer` would
need per-path layer IDs rather than one shared `layer_id`.

**However:** this shares the dead hostname, so it fixes nothing today. Low priority until
ANCPI returns, and only worth doing if it survives the Government Cloud migration.

### B4. `last_error` is computed and discarded — masks the real failure
**`client.py:200, 253`**
**Severity: high — this one is causing concrete harm right now**

Every failure branch assigns `last_error`, but `ServiceUnavailableError(theme, tried)` never
receives it. The underlying `socket.gaierror` is swallowed by the broad `except Exception` at
`client.py:247`.

The practical result today: the tool reports *"The ANCPI server may be temporarily down — try
again later"* and the CLI adds *"Tip: CP attribute queries are often unreliable. Try a spatial
query instead."* Both are false. The host does not resolve; **no query of any shape can
work.** A user is sent chasing query syntax instead of learning that ANCPI moved.

**Fix:** thread `last_error` into the exception, and special-case DNS resolution failure
(`socket.gaierror` / `httpx.ConnectError` wrapping it) with a distinct
`HostUnreachableError` and an accurate message.

### B5. Retry logic doesn't retry the useful cases
**`client.py:203-215`**

502 and HTML responses `break` immediately (reasonable — they indicate a wedged backend).
Transient timeouts retry with `time.sleep(1.0 * attempt)` and `max_retries=1`: exactly one
retry, after one second, no jitter. For a service this flaky, exponential backoff with jitter
and a higher default would help materially.

### B6. `verify=False` by default, silently
**`client.py:47`**

Justified by ANCPI's broken certificate chain, but it disables MITM protection with no signal
to the user.

**Fix:** ship/pin the correct CA bundle if obtainable; otherwise emit a single one-time
warning so the choice is visible.

### B7. Non-UTF-8 output encoding
**`cli.py:50`**

```python
with open(output_file, "w") as f:
```

No `encoding=`, so the platform locale is used — Romanian diacritics (`ă î ș ț â`) in
locality and street names will mangle or raise on non-UTF-8 systems. Additionally
`json.dumps(...)` at `cli.py:40, 47` uses the default `ensure_ascii=True`, escaping all
diacritics into `\uXXXX`.

**Fix:** `encoding="utf-8"` on write; `ensure_ascii=False` on dumps.

---

## C. API design

### C1. lat/lon ordering is a trap
**`client.py:83, 95, 107` vs `cli.py:279`**

The CLI accepts `lat,lon` then immediately flips to `(lon, lat)`; the library takes
`get_parcels_at(lon, lat)`. Two conventions in one codebase, distinguishable only by argument
position — and both are `float`, so a transposition fails **silently** by querying the wrong
place. This already caused one fix (commit `28fac45`).

**Fix:** make the coordinate arguments keyword-only — `get_parcels_at(*, lat, lon)` — so the
mistake becomes unrepresentable. Same for the bbox methods.

### C2. `Building` and `Address` models add nothing
**`models.py:171-197`**

Both are pure boilerplate over `Feature` with identical `from_esri` bodies.

**Fix:** delete them in favour of the base-class `from_esri` from **A5**, or give them real
parsed fields (street, number, postcode for `AD`; storeys, function for `BU`).

---

## D. Infrastructure

### D1. No tests, no linter, no CI
**Severity: high — this is what makes every item above expensive to fix**

Every finding except **A3** and **B3** is testable **entirely offline** with recorded
fixtures: geometry conversion, pagination, fallback ordering, WHERE-escaping, error
propagation, encoding. Given the endpoints are down more often than up — and are wholly
unreachable right now — a fixture-based suite is the *only* way to develop this reliably.

**Fix:** `pytest` + `respx` (httpx mocking) + `ruff`; capture real ESRI JSON responses as
fixtures under `tests/fixtures/`.

### D2. Optional-dependency extras are unused
**`pyproject.toml:17`**

`shapely` and `geojson` are declared under the `geo` extra but imported nowhere in the
package. Either use them — `shapely.geometry.polygon.orient()` solves **A1** and **A2**
outright — or drop the extra.

### D3. No packaging metadata
**`pyproject.toml`**

Missing `readme`, `license`, `authors`, `classifiers`, `urls`. Not publishable as-is.

---

## Implementation plan

Ordered by value-per-effort. Phases 1–2 are fully offline and unblocked today.

### Phase 1 — Make the failure legible (unblocked, ~half day)
Highest value right now: the tool currently lies about why it fails.

1. **B4** — thread `last_error` into `ServiceUnavailableError`; add `HostUnreachableError`
   for DNS failures with an accurate message pointing at the Government Cloud migration.
2. Narrow the broad `except Exception` (`client.py:247`) so `socket.gaierror` is
   distinguishable from genuine HTTP errors.
3. Suppress the misleading "try a spatial query instead" CLI tip when the failure was DNS.
4. Make `DEFAULT_HOST` overridable via `ANCPI_HOST` env var, so a republished hostname needs
   no code change (§0).

### Phase 2 — Test harness + geometry correctness (unblocked, ~1–2 days)
5. **D1** — add `pytest` + `respx` + `ruff`; wire a minimal CI workflow.
6. Capture ESRI JSON fixtures: simple polygon, **donut with hole**, multipart polygon,
   polyline, point, error response, paginated response.
7. **A1 + A2** — rewrite `_esri_to_geojson_geometry` and `_esri_to_kml_geometry` with signed-
   area ring classification and RFC 7946 winding. Test against the donut fixture.
8. **D2** — decide on `shapely`: adopt it for `orient()` or drop the extra.
9. **A5 + C2** — hoist `from_esri` to `Feature`; delete the empty subclasses.

### Phase 3 — Robustness (unblocked, ~1 day)
10. **B1** — auto-pagination driven by `exceededTransferLimit`, with a `max_features` bound.
11. **B2** — read `maxRecordCount` from cached layer metadata.
12. **A4** — escape and validate WHERE inputs.
13. **B5** — exponential backoff with jitter; raise default `max_retries`.
14. **B7** — UTF-8 output, `ensure_ascii=False`.
15. **C1** — keyword-only coordinate arguments.

### Phase 4 — Requires a live server (BLOCKED on ANCPI restoration)
16. **A3** — confirm `INSPIRE_ID` vs `id_localId` via `ancpi info CP`; correct or resolve
    field names dynamically from layer metadata.
17. Verify whether `outSR=4326` is actually honoured, or whether Stereo70 (EPSG:3844) comes
    back regardless — the third-party capture suggests the latter, which would make `pyproj`
    a hard requirement rather than an extra.
18. **B3** — re-evaluate the `/maps/eterra3_publish` fallback if it survives the migration.
19. **B6** — inspect the real certificate chain; pin a CA bundle if feasible.
20. Re-baseline `ancpi-gis-endpoints.md` against the Government Cloud hostnames.

### Phase 5 — Polish
21. **D3** — complete packaging metadata.
22. Consider the official INSPIRE **WMS/WFS** download services registered for ANCPI's
    Cadastral Parcels theme (issued 2020-01-22) as a standards-based, more stable transport
    than ArcGIS REST.

---

## Open questions

- **Is bulk extraction even permitted?** An MDPI survey of INSPIRE cadastral services notes
  Romania is among the countries permitting **single-parcel download only**. If so, the
  pagination work in **B1** may hit a deliberate policy limit rather than a technical one, and
  the library should document that constraint rather than fight it.
- **What is the post-migration hostname?** Unknown until ANCPI completes staged restoration.
  Phase 1 item 4 is designed so this costs users nothing when it lands.
- **Is the `id_localId` naming a leftover from a different service?** Worth checking whether
  `/inspireview/` and `/maps/eterra3_publish/` genuinely use different field names — if so,
  field naming belongs on `ServiceLayer`, not hardcoded in `models.py`.
