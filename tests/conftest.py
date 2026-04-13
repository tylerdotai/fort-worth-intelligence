"""
Fixtures and helpers for Fort Worth Intelligence tests.
"""
import json, pytest
from pathlib import Path

FW_BOUNDS = {
    "lat_min": 32.55,
    "lat_max": 33.08,
    "lon_min": -97.60,
    "lon_max": -97.00,
}

TEST_ADDRESSES = [
    "704 E Weatherford St, Fort Worth, TX 76102",
    "600 Cooper St, Fort Worth, TX 76102",
    "3040 S University Dr, Fort Worth, TX 76109",
    "1200 Summit Ave, Fort Worth, TX 76102",
]

ETJ_ADDRESSES = [
    "10000 Alta Vista Rd, Fort Worth, TX 76244",
    "12000 Burns St, Fort Worth, TX 76126",
]


@pytest.fixture
def data_dir():
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def legistar_meetings(data_dir):
    f = data_dir / "legistar-meetings.json"
    if not f.exists():
        pytest.skip(f"{f} not found - run extract_legistar_agenda.py first")
    with open(f) as fh:
        return json.load(fh)


@pytest.fixture
def legistar_agenda(data_dir):
    f = data_dir / "legistar-agenda-items.json"
    if not f.exists():
        pytest.skip(f"{f} not found - run extract_legistar_agenda.py first")
    with open(f) as fh:
        return json.load(fh)


@pytest.fixture
def parcels_data(data_dir):
    f = data_dir / "tad-parcels.json"
    if not f.exists():
        pytest.skip(f"{f} not found - run extract_tad_parcels.py first")
    with open(f) as fh:
        return json.load(fh)


@pytest.fixture
def permits_data(data_dir):
    f = data_dir / "tcgis-permits-fixed.json"
    if not f.exists():
        pytest.skip(f"{f} not found")
    with open(f) as fh:
        return json.load(fh)


@pytest.fixture
def crime_data(data_dir):
    f = data_dir / "fw-crime.json"
    if not f.exists():
        pytest.skip(f"{f} not found")
    with open(f) as fh:
        return json.load(fh)


@pytest.fixture
def fw_bounds():
    return FW_BOUNDS


@pytest.fixture
def test_addresses():
    return TEST_ADDRESSES


@pytest.fixture
def etj_addresses():
    return ETJ_ADDRESSES
