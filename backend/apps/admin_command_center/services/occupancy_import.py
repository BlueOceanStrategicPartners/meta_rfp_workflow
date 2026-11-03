"""CSV import of historical occupancy with a row-by-row report."""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.inventory.models import HistoricalOccupancy, VenueProperty

from . import AdminInputError

REQUIRED_COLUMNS = ("target_date", "room_occupancy_pct", "adr", "revpar")
OPTIONAL_COLUMNS = ("hall_utilization_pct", "is_peak_season", "local_event_multiplier")
TRUE_WORDS = {"1", "true", "yes", "y"}
FALSE_WORDS = {"0", "false", "no", "n", ""}
MAX_ROWS = 5000


def _pct(row: dict, key: str, *, required: bool) -> float | None:
    raw = (row.get(key) or "").strip()
    if not raw:
        if required:
            raise ValueError(f"{key} is missing")
        return None
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{key} must be a number")
    if not 0 <= value <= 1:
        raise ValueError(f"{key} must be between 0 and 1")
    return value


def _money(row: dict, key: str) -> Decimal:
    raw = (row.get(key) or "").strip()
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"{key} must be a number")
    if value < 0:
        raise ValueError(f"{key} cannot be negative")
    return value


def _parse_row(row: dict) -> dict:
    try:
        target = date.fromisoformat((row.get("target_date") or "").strip())
    except ValueError:
        raise ValueError("target_date must look like 2026-06-01")
    values = {
        "room_occupancy_pct": _pct(row, "room_occupancy_pct", required=True),
        "adr": _money(row, "adr"),
        "revpar": _money(row, "revpar"),
    }
    hall = _pct(row, "hall_utilization_pct", required=False)
    if hall is not None:
        values["hall_utilization_pct"] = hall
    peak = (row.get("is_peak_season") or "").strip().lower()
    if peak in TRUE_WORDS:
        values["is_peak_season"] = True
    elif peak in FALSE_WORDS:
        if peak:
            values["is_peak_season"] = False
    else:
        raise ValueError("is_peak_season must be true or false")
    multiplier = (row.get("local_event_multiplier") or "").strip()
    if multiplier:
        try:
            m = float(multiplier)
        except ValueError:
            raise ValueError("local_event_multiplier must be a number")
        if m <= 0:
            raise ValueError("local_event_multiplier must be above 0")
        values["local_event_multiplier"] = m
    return {"target_date": target, "values": values}


def import_csv(uploaded_file, prop: VenueProperty) -> dict:
    if uploaded_file is None:
        raise AdminInputError("Choose a CSV file to upload.")
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if not name.endswith(".csv"):
        raise AdminInputError("Only .csv files can be imported. In Excel, use File → Save As → CSV.")
    try:
        text = io.TextIOWrapper(uploaded_file.file, encoding="utf-8-sig").read()
    except UnicodeDecodeError:
        raise AdminInputError("This file isn't readable text. Save it as a UTF-8 CSV and try again.")

    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise AdminInputError(
            f"The file is missing these columns: {', '.join(missing)}.",
            extra={"expected_header": ",".join(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)},
        )

    report = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
    with transaction.atomic():
        for index, raw in enumerate(reader):
            row_number = index + 2  # header is row 1, like a spreadsheet
            if index >= MAX_ROWS:
                report["errors"].append({"row": row_number, "error": f"Only the first {MAX_ROWS} rows are imported"})
                report["skipped"] += 1
                break
            row = {(k or "").strip().lower(): (v or "") for k, v in raw.items()}
            try:
                parsed = _parse_row(row)
            except ValueError as exc:
                report["skipped"] += 1
                report["errors"].append({"row": row_number, "error": str(exc)})
                continue
            _, created = HistoricalOccupancy.objects.update_or_create(
                property=prop, target_date=parsed["target_date"], defaults=parsed["values"]
            )
            report["created" if created else "updated"] += 1
    return report
