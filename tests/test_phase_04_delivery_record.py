from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "planning" / "delivery" / "phase-04-live-site-provenance-ux.md"
LOG = ROOT / "planning" / "delivery-log.md"


def test_phase_04_delivery_record_captures_required_evidence() -> None:
    text = RECORD.read_text(encoding="utf-8")

    for value in (
        "#160",
        "#165",
        "#161, #163, #162, #164",
        "#166, #167, #168, #169",
        "29081901945",
        "29082778088",
        "29083425572",
        "29084860287",
        "https://8ft0-ai.github.io/crypto-pulse/",
        "`_site/` remains generated and uncommitted",
        "Delivery graph update: N/A",
    ):
        assert value in text


def test_phase_04_delivery_log_entry_is_present() -> None:
    text = LOG.read_text(encoding="utf-8")
    assert "## Phase 4 — Live-site provenance UX" in text
    assert "public live-site fetch requires external confirmation" in text
    assert "planning/delivery/phase-04-live-site-provenance-ux.md" in text
