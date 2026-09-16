"""The command line interface.

Exit codes are part of the contract:

* ``0`` an exact count was found
* ``2`` no exact count is available - a correct result, not a failure
* ``1`` something actually went wrong
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from camera_count import __version__
from camera_count.cli import render
from camera_count.core.errors import CameraCountError
from camera_count.core.messages import READ_ONLY_NOTICE
from camera_count.inspection import inspect_camera
from camera_count.registry import load_default_registry
from camera_count.usb.enumerate import detect as detect_devices

EXIT_FOUND = 0
EXIT_ERROR = 1
EXIT_UNAVAILABLE = 2

app = typer.Typer(
    name="camera-count",
    help=(
        "Read the exact shutter count of a connected camera or an original "
        "camera file. When no exact count can be obtained from an authoritative "
        "source, this tool says so instead of guessing."
    ),
    no_args_is_help=True,
    add_completion=False,
)

JsonFlag = Annotated[bool, typer.Option("--json", help="Print machine-readable JSON.")]


def _emit(payload: dict[str, Any] | list[Any], text: str, *, as_json: bool) -> None:
    typer.echo(json.dumps(payload, indent=2) if as_json else text)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"camera-count {__version__}")
        raise typer.Exit(EXIT_FOUND)


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show the version."
        ),
    ] = False,
) -> None:
    """Camera Count Tool."""


@app.command()
def detect(as_json: JsonFlag = False) -> None:
    """List connected cameras and how they are reachable."""
    report = detect_devices()
    _emit(render.detection_json(report), render.render_detection(report), as_json=as_json)
    raise typer.Exit(EXIT_FOUND if report.has_camera else EXIT_UNAVAILABLE)


@app.command()
def inspect(as_json: JsonFlag = False) -> None:
    """Identify the connected camera without reading any counter."""
    result = inspect_camera()
    payload = render.inspection_json(result)
    payload.pop("counters", None)
    _emit(
        payload,
        render.render_inspection(result, show_counts=result.failure is not None),
        as_json=as_json,
    )
    raise typer.Exit(EXIT_FOUND if result.identity.is_identified else EXIT_UNAVAILABLE)


@app.command()
def count(as_json: JsonFlag = False) -> None:
    """Read every documented counter from the connected camera."""
    result = inspect_camera()
    _emit(render.inspection_json(result), render.render_inspection(result), as_json=as_json)
    raise typer.Exit(result.exit_code)


@app.command()
def exif(
    files: Annotated[list[Path], typer.Argument(help="Original camera files to analyse.")],
    as_json: JsonFlag = False,
) -> None:
    """Read the exact historical count from original camera files."""
    from camera_count.metadata import analyze_files, historical_notice  # noqa: PLC0415

    analyses = analyze_files(files)
    notice = historical_notice(analyses)

    payload: dict[str, Any] = {
        "files": [render.file_analysis_json(analysis) for analysis in analyses],
        "exact_count_found": any(analysis.has_exact_count for analysis in analyses),
    }
    if notice:
        payload["notice"] = notice

    _emit(payload, render.render_analyses(analyses, notice=notice), as_json=as_json)
    raise typer.Exit(EXIT_FOUND if payload["exact_count_found"] else EXIT_UNAVAILABLE)


@app.command()
def supported(
    make: Annotated[str | None, typer.Option("--make", help="Only show this manufacturer.")] = None,
    as_json: JsonFlag = False,
) -> None:
    """Show which models have a documented exact-count method."""
    registry = load_default_registry()
    rows: list[dict[str, Any]] = []
    for entry, model in registry.iter_models():
        if make and make.casefold() not in entry.manufacturer.casefold():
            continue
        rows.append(
            {
                "manufacturer": entry.manufacturer,
                "model": model.model,
                "applies_to_any_model": model.is_wildcard,
                "exact_count_available": model.exact_count_available,
                "methods": [
                    {
                        "type": method.method_type.value,
                        "identifier": method.identifier,
                        "counter": method.count_type.value,
                        "verification_status": method.verification_status.value,
                        "citation": method.citation.reference,
                    }
                    for method in model.methods
                ],
            }
        )

    manufacturers = [
        entry.manufacturer
        for entry in registry.entries
        if not make or make.casefold() in entry.manufacturer.casefold()
    ]

    payload = {
        "manufacturers": manufacturers,
        "model_count": len(rows),
        "documented_model_count": sum(1 for row in rows if row["exact_count_available"]),
        "models": rows,
    }
    _emit(payload, _render_supported(manufacturers, rows), as_json=as_json)
    raise typer.Exit(EXIT_FOUND)


def _render_supported(manufacturers: list[str], rows: list[dict[str, Any]]) -> str:
    lines = ["Camera support", render.RULE]
    lines.append(f"Manufacturers in the registry: {', '.join(manufacturers) or 'none'}")
    lines.append("")
    if not rows:
        lines.append("No models are recorded yet.")
        lines.append("")
        lines.append(
            "A model is added only with a citation for its exact-count method. "
            "Until then, cameras of that make report EXACT SHUTTER COUNT NOT AVAILABLE."
        )
        return "\n".join(lines)

    for row in rows:
        mark = "yes" if row["exact_count_available"] else "no"
        label = (
            "(any model that writes the documented field)"
            if row["applies_to_any_model"]
            else row["model"]
        )
        lines.append(f"{row['manufacturer']} {label}  exact count: {mark}")
        for method in row["methods"]:
            lines.append(
                f"    {method['counter']:<15} {method['type']:<16} {method['identifier']:<24}"
                f" {method['verification_status']}"
            )
            lines.append(f"      cited: {method['citation']}")
    return "\n".join(lines)


@app.command()
def report(
    files: Annotated[
        list[Path] | None,
        typer.Argument(help="Original camera files. With none, the connected camera is inspected."),
    ] = None,
    report_format: Annotated[str, typer.Option("--format", help="html, pdf or json.")] = "html",
    out: Annotated[Path | None, typer.Option("--out", help="Where to write the report.")] = None,
    seller_notes: Annotated[str, typer.Option("--seller-notes", help="Optional note.")] = "",
    buyer_notes: Annotated[str, typer.Option("--buyer-notes", help="Optional note.")] = "",
    save: Annotated[
        bool, typer.Option("--save/--no-save", help="Record this inspection locally.")
    ] = True,
) -> None:
    """Produce a Used Camera Inspection Report."""
    from camera_count.report import (  # noqa: PLC0415
        ReportFormat,
        from_image_analyses,
        from_inspection,
    )
    from camera_count.report.builder import DEFAULT_STEMS, write_report  # noqa: PLC0415

    try:
        chosen = ReportFormat(report_format.lower())
    except ValueError:
        typer.echo(f"error: unknown format {report_format!r}. Use html, pdf or json.", err=True)
        raise typer.Exit(EXIT_ERROR) from None

    if files:
        from camera_count.metadata import analyze_files  # noqa: PLC0415

        analyses = analyze_files(files)
        data = from_image_analyses(analyses, seller_notes=seller_notes, buyer_notes=buyer_notes)
        found = any(analysis.has_exact_count for analysis in analyses)

        def persist(database: Any) -> int:
            return int(
                database.save_image_inspection(
                    analyses,
                    seller_notes=seller_notes or None,
                    buyer_notes=buyer_notes or None,
                )
            )
    else:
        result = inspect_camera()
        data = from_inspection(result, seller_notes=seller_notes, buyer_notes=buyer_notes)
        found = result.has_exact_count

        def persist(database: Any) -> int:
            return int(
                database.save_inspection(
                    result,
                    seller_notes=seller_notes or None,
                    buyer_notes=buyer_notes or None,
                )
            )

    destination = out or Path(DEFAULT_STEMS[chosen])
    written, digest = write_report(data, destination, chosen)
    typer.echo(f"Wrote {written}")
    typer.echo(f"Content SHA-256: {digest}")

    if save:
        from camera_count.db import Database  # noqa: PLC0415

        database = Database()
        inspection_id = persist(database)
        typer.echo(f"Recorded locally as inspection {inspection_id} in {database.path}")

    raise typer.Exit(EXIT_FOUND if found else EXIT_UNAVAILABLE)


@app.command()
def diagnostics(
    export: Annotated[
        Path | None, typer.Option("--export", help="Write the transaction log to this file.")
    ] = None,
    include_serials: Annotated[
        bool,
        typer.Option(
            "--include-serials",
            help="Include serial numbers in the export. They are redacted by default.",
        ),
    ] = False,
    as_json: JsonFlag = False,
) -> None:
    """Run an inspection and show or export the protocol transaction log."""
    result = inspect_camera()
    payload = result.log.export(include_serials=include_serials)
    payload["camera"] = {
        "manufacturer": result.identity.manufacturer,
        "model": result.identity.model,
        "firmware": result.identity.firmware,
    }

    if export is not None:
        export.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        typer.echo(f"Wrote {len(result.log)} transactions to {export}")
        if not include_serials:
            typer.echo("Serial numbers were redacted. Use --include-serials to keep them.")
        raise typer.Exit(EXIT_FOUND)

    _emit(payload, result.log.summary(), as_json=as_json)
    raise typer.Exit(EXIT_FOUND)


@app.command("read-only-notice")
def read_only_notice() -> None:
    """Print exactly what this program will and will not do to a camera."""
    typer.echo(READ_ONLY_NOTICE)
    raise typer.Exit(EXIT_FOUND)


def run() -> None:
    """Entry point that maps unexpected failures to exit code 1."""
    try:
        app()
    except CameraCountError as exc:
        typer.echo(f"error: {exc}", err=True)
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":  # pragma: no cover
    run()
