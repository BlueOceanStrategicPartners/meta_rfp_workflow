import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.inventory.models import HistoricalOccupancy


def _csv(text: str, name: str = "occ.csv"):
    return SimpleUploadedFile(name, text.encode("utf-8-sig"), content_type="text/csv")


@pytest.mark.django_db
def test_upload_reports_created_updated_and_row_errors(admin_client, demo_property):
    HistoricalOccupancy.objects.create(
        property=demo_property, target_date="2026-07-01", room_occupancy_pct=0.1, adr=1, revpar=1
    )
    text = (
        "Target_Date,room_occupancy_pct,adr,revpar,is_peak_season\n"
        "2026-07-01,0.8,220,176,true\n"  # updates existing row
        "2026-07-02,0.7,210,147,no\n"
        "2026-07-03,1.4,210,147,no\n"  # bad pct
        "not-a-date,0.7,210,147,no\n"
        "2026-07-04,0.7,abc,147,no\n"
    )
    res = admin_client.post(
        "/api/admin-center/occupancy/upload/",
        {"file": _csv(text), "property": str(demo_property.id)},
        format="multipart",
    )
    assert res.status_code == 200, res.json()
    report = res.json()
    assert (report["created"], report["updated"], report["skipped"]) == (1, 1, 3)
    assert [e["row"] for e in report["errors"]] == [4, 5, 6]
    assert "between 0 and 1" in report["errors"][0]["error"]
    row = HistoricalOccupancy.objects.get(property=demo_property, target_date="2026-07-01")
    assert row.room_occupancy_pct == 0.8 and row.is_peak_season is True


@pytest.mark.django_db
def test_upload_rejects_missing_columns_and_non_csv(admin_client, demo_property):
    res = admin_client.post(
        "/api/admin-center/occupancy/upload/",
        {"file": _csv("target_date,adr\n2026-07-01,200\n"), "property": str(demo_property.id)},
        format="multipart",
    )
    assert res.status_code == 400
    assert "room_occupancy_pct" in res.json()["detail"]
    assert res.json()["expected_header"].startswith("target_date")

    res = admin_client.post(
        "/api/admin-center/occupancy/upload/",
        {"file": _csv("x", name="data.xlsx"), "property": str(demo_property.id)},
        format="multipart",
    )
    assert res.status_code == 400

    res = admin_client.post("/api/admin-center/occupancy/upload/", {"property": str(demo_property.id)}, format="multipart")
    assert res.status_code == 400


@pytest.mark.django_db
def test_list_filters_and_summary(admin_client, demo_property):
    for day in ("2026-06-01", "2026-06-15", "2026-07-01"):
        HistoricalOccupancy.objects.create(property=demo_property, target_date=day, room_occupancy_pct=0.5, adr=100, revpar=50)
    rows = admin_client.get(
        f"/api/admin-center/occupancy/?property={demo_property.id}&from=2026-06-10&to=2026-06-30"
    ).json()
    assert [r["target_date"] for r in rows] == ["2026-06-15"]
    summary = admin_client.get("/api/admin-center/occupancy/summary/").json()
    assert summary["engine"] == "sqlite" and summary["vendor"] == "sqlite"
    assert summary["tables"]["occupancy"] == 3
    assert summary["occupancy_range"] == {"from": "2026-06-01", "to": "2026-07-01"}
