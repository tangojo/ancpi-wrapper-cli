"""CLI for ANCPI GIS Client."""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console
from rich.table import Table

from ancpi.client import ANCPIClient
from ancpi.exceptions import ANCPIError
from ancpi.models import QueryResult
from ancpi.services import THEMES

console = Console(stderr=True)
output_console = Console()


def _is_pipe() -> bool:
    return not sys.stdout.isatty()


def _output_result(
    result: QueryResult,
    fmt: str,
    output_file: str | None,
    no_geometry: bool,
    theme: str,
) -> None:
    """Format and output query results."""
    include_geom = not no_geometry

    if fmt == "geojson":
        text = result.to_geojson_str(include_geometry=include_geom)
    elif fmt == "kml":
        text = result.to_kml_str(include_geometry=include_geom)
    elif fmt == "json":
        text = json.dumps(result.to_dicts(include_geometry=include_geom), indent=2)
    elif fmt == "table":
        _print_table(result, theme, include_geom)
        if result.exceeded_transfer_limit:
            console.print("[yellow]Warning: results were truncated (server limit reached)[/]")
        return
    else:
        text = json.dumps(result.to_dicts(include_geometry=include_geom), indent=2)

    if output_file:
        with open(output_file, "w") as f:
            f.write(text)
        console.print(f"Written {result.count} features to {output_file}")
    else:
        click.echo(text)

    if result.exceeded_transfer_limit:
        console.print("[yellow]Warning: results were truncated (server limit reached)[/]")


def _print_table(result: QueryResult, theme: str, include_geom: bool) -> None:
    """Print results as a rich table."""
    if not result.features:
        console.print("[dim]No results found.[/]")
        return

    table = Table(title=f"{theme} Results ({result.count} features)")

    # Pick columns based on theme
    if theme == "CP":
        cols = ["OBJECTID", "nationalCadastralRef", "label", "areaValue", "id_localId"]
    elif theme == "BU":
        cols = ["OBJECTID", "id_localId", "id_namespace"]
    elif theme == "AD":
        cols = ["OBJECTID", "id_localId", "id_namespace"]
    elif theme == "AU":
        cols = ["OBJECTID", "NUTSCode", "id_localId", "SHAPE_Area"]
    else:
        # Generic: show first few fields
        cols = list(result.features[0].raw_attributes.keys())[:6]

    if include_geom:
        cols.append("has_geometry")

    for col in cols:
        table.add_column(col, overflow="fold")

    for feat in result.features:
        row = []
        for col in cols:
            if col == "has_geometry":
                row.append("yes" if feat.geometry else "no")
            else:
                val = feat.raw_attributes.get(col)
                row.append(str(val) if val is not None else "")
        table.add_row(*row)

    output_console.print(table)


def _get_format(fmt: str | None) -> str:
    if fmt:
        return fmt
    return "json" if _is_pipe() else "table"


@click.group()
@click.option("--host", default=None, help="ANCPI server URL")
@click.option("--format", "fmt", type=click.Choice(["json", "geojson", "kml", "table"]), default=None)
@click.option("--output", "-o", "output_file", default=None, help="Write output to file")
@click.option("--no-geometry", is_flag=True, help="Omit geometry from output")
@click.option("--verbose", "-v", is_flag=True, help="Show debug info")
@click.pass_context
def cli(ctx: click.Context, host: str | None, fmt: str | None, output_file: str | None, no_geometry: bool, verbose: bool) -> None:
    """ANCPI GIS Client — query Romania's cadastral data."""
    import logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    ctx.ensure_object(dict)
    kwargs = {}
    if host:
        kwargs["host"] = host
    ctx.obj["client"] = ANCPIClient(**kwargs)
    ctx.obj["fmt"] = fmt
    ctx.obj["output_file"] = output_file
    ctx.obj["no_geometry"] = no_geometry


@cli.command()
@click.argument("cadastral_ref", required=False)
@click.option("--inspire-id", default=None, help="Look up by INSPIRE local ID")
@click.option("--at", "at_coord", default=None, help="Spatial query at lat,lon")
@click.option("--bbox", default=None, help="Spatial query in lat_min,lon_min,lat_max,lon_max")
@click.pass_context
def parcel(ctx: click.Context, cadastral_ref: str | None, inspire_id: str | None, at_coord: str | None, bbox: str | None) -> None:
    """Query cadastral parcels.

    CADASTRAL_REF can be a bare number (105966) or full ref (AB.1017.70112).

    Note: attribute lookups on CP are slow/unreliable. Spatial queries (--at, --bbox) tend to work better.
    """
    client: ANCPIClient = ctx.obj["client"]
    fmt = _get_format(ctx.obj["fmt"])

    try:
        if cadastral_ref:
            result = client.get_parcel(cadastral_ref)
        elif inspire_id:
            result = client.get_parcel_by_inspire_id(inspire_id)
        elif at_coord:
            lon, lat = _parse_coords(at_coord)
            result = client.get_parcels_at(lon, lat)
        elif bbox:
            coords = _parse_bbox(bbox)
            result = client.get_parcels_in_bbox(*coords)
        else:
            raise click.UsageError("Provide a cadastral reference, --inspire-id, --at, or --bbox")

        _output_result(result, fmt, ctx.obj["output_file"], ctx.obj["no_geometry"], "CP")
    except ANCPIError as e:
        console.print(f"[red]Error:[/] {e}")
        if cadastral_ref or inspire_id:
            console.print(
                "[dim]Tip: CP attribute queries are often unreliable. "
                "Try a spatial query instead:[/]\n"
                "[dim]  ancpi parcel --at <lat>,<lon>[/]"
            )
        raise SystemExit(1)


@cli.command()
@click.option("--at", "at_coord", default=None, help="Spatial query at lat,lon")
@click.option("--bbox", default=None, help="Spatial query in lat_min,lon_min,lat_max,lon_max")
@click.pass_context
def building(ctx: click.Context, at_coord: str | None, bbox: str | None) -> None:
    """Query buildings."""
    client: ANCPIClient = ctx.obj["client"]
    fmt = _get_format(ctx.obj["fmt"])

    try:
        if at_coord:
            lon, lat = _parse_coords(at_coord)
            result = client.get_buildings_at(lon, lat)
        elif bbox:
            coords = _parse_bbox(bbox)
            result = client.get_buildings_in_bbox(*coords)
        else:
            raise click.UsageError("Provide --at or --bbox")

        _output_result(result, fmt, ctx.obj["output_file"], ctx.obj["no_geometry"], "BU")
    except ANCPIError as e:
        console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1)


@cli.command()
@click.option("--at", "at_coord", required=True, help="Spatial query at lat,lon")
@click.pass_context
def address(ctx: click.Context, at_coord: str) -> None:
    """Query addresses."""
    client: ANCPIClient = ctx.obj["client"]
    fmt = _get_format(ctx.obj["fmt"])

    try:
        lon, lat = _parse_coords(at_coord)
        result = client.get_addresses_at(lon, lat)
        _output_result(result, fmt, ctx.obj["output_file"], ctx.obj["no_geometry"], "AD")
    except ANCPIError as e:
        console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1)


@cli.command()
@click.argument("nuts_code")
@click.pass_context
def admin(ctx: click.Context, nuts_code: str) -> None:
    """Query administrative units by NUTS code."""
    client: ANCPIClient = ctx.obj["client"]
    fmt = _get_format(ctx.obj["fmt"])

    try:
        result = client.get_admin_unit(nuts_code)
        _output_result(result, fmt, ctx.obj["output_file"], ctx.obj["no_geometry"], "AU")
    except ANCPIError as e:
        console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1)


@cli.command()
@click.argument("theme")
@click.pass_context
def info(ctx: click.Context, theme: str) -> None:
    """Show layer metadata for a theme (CP, BU, AD, AU)."""
    client: ANCPIClient = ctx.obj["client"]

    try:
        data = client.get_layer_info(theme)

        table = Table(title=f"{theme.upper()} Layer Info")
        table.add_column("Property", style="bold")
        table.add_column("Value")

        table.add_row("Name", str(data.get("name", "")))
        table.add_row("Type", str(data.get("type", "")))
        table.add_row("Geometry", str(data.get("geometryType", "")))
        table.add_row("Max Records", str(data.get("maxRecordCount", "")))

        sr = data.get("spatialReference") or data.get("extent", {}).get("spatialReference", {})
        table.add_row("Spatial Ref", f"EPSG:{sr.get('wkid', '?')}")

        ext = data.get("extent", {})
        if ext:
            table.add_row("Extent", f"({ext.get('xmin', '')}, {ext.get('ymin', '')}) - ({ext.get('xmax', '')}, {ext.get('ymax', '')})")

        caps = data.get("capabilities", "")
        table.add_row("Capabilities", caps)

        output_console.print(table)

        # Fields
        fields = data.get("fields", [])
        if fields:
            ft = Table(title="Fields")
            ft.add_column("Name")
            ft.add_column("Type")
            ft.add_column("Alias")
            for f in fields:
                ft.add_row(f["name"], f["type"].replace("esriFieldType", ""), f.get("alias", ""))
            output_console.print(ft)

    except ANCPIError as e:
        console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1)


def _parse_coords(s: str) -> tuple[float, float]:
    """Parse 'lat,lon' string, return (lon, lat) for internal use."""
    parts = s.split(",")
    if len(parts) != 2:
        raise click.BadParameter(f"Expected lat,lon but got '{s}'")
    lat = float(parts[0].strip())
    lon = float(parts[1].strip())
    return lon, lat


def _parse_bbox(s: str) -> tuple[float, float, float, float]:
    """Parse 'lat_min,lon_min,lat_max,lon_max' string, return (xmin,ymin,xmax,ymax)."""
    parts = s.split(",")
    if len(parts) != 4:
        raise click.BadParameter(f"Expected lat_min,lon_min,lat_max,lon_max but got '{s}'")
    lat_min, lon_min, lat_max, lon_max = (float(p.strip()) for p in parts)
    return lon_min, lat_min, lon_max, lat_max


if __name__ == "__main__":
    cli()
