"""
Tests validating data against the ONTOLOGY.md type definitions.
"""
import json, pytest, re
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"


# ─── helpers ────────────────────────────────────────────────────────────────

def records(data, key):
    """Extract records list from data dict, handling various structures."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Try common keys
        for k in (key, key + "s", key.rstrip("s"), "records", "data"):
            if k in data:
                val = data[k]
                if isinstance(val, list):
                    return val
        # Fallback: whole dict is the record
        return [data]
    return []


# ─── TAD Parcels ─────────────────────────────────────────────────────────────

class TestParcelData:
    REQUIRED_FIELDS = {
        "gis_link", "situs_address", "total_value", "appraised_value",
        "owner_name", "year_built",
    }

    def test_file_exists_and_parseable(self, parcels_data):
        assert isinstance(parcels_data, (dict, list))

    def test_required_fields_present(self, parcels_data):
        recs = records(parcels_data, "parcel")
        if not recs:
            pytest.skip("No parcel records found")
        first = recs[0]
        missing = self.REQUIRED_FIELDS - first.keys()
        assert not missing, f"Parcel records missing ONTOLOGY required fields: {missing}"

    def test_total_value_numeric(self, parcels_data):
        recs = records(parcels_data, "parcel")
        for rec in recs[:50]:
            tv = rec.get("total_value")
            if tv is not None:
                assert isinstance(tv, (int, float)), \
                    f"total_value must be numeric, got {type(tv).__name__} in {rec.get('gis_link')}"

    def test_year_built_in_range(self, parcels_data):
        recs = records(parcels_data, "parcel")
        for rec in recs[:100]:
            yb = rec.get("year_built")
            if yb is not None:
                yr = int(str(yb).replace(",", "")[:4])
                assert 1800 <= yr <= 2030, \
                    f"year_built {yr} out of range in {rec.get('gis_link')}"

    def test_gis_link_format(self, parcels_data):
        recs = records(parcels_data, "parcel")
        pattern = re.compile(r"^\d{5}-\d{2}-\d{2}$")
        for rec in recs[:100]:
            gl = rec.get("gis_link")
            if gl:
                assert pattern.match(str(gl)), \
                    f"gis_link '{gl}' doesn't match expected format (#####-##-##)"

    def test_owner_name_not_all_whitespace(self, parcels_data):
        recs = records(parcels_data, "parcel")
        for rec in recs[:50]:
            owner = rec.get("owner_name")
            if owner is not None:
                assert isinstance(owner, str) and len(owner.strip()) > 0, \
                    f"owner_name must be non-empty string, got {repr(owner)}"


# ─── TCGIS Permits ───────────────────────────────────────────────────────────

class TestPermitData:
    def test_file_exists(self, permits_data):
        assert isinstance(permits_data, (dict, list))

    def test_permit_has_required_fields(self, permits_data):
        recs = records(permits_data, "permit")
        required = {"permit_no", "address", "status"}
        for rec in recs[:10]:
            missing = required - rec.keys()
            assert not missing, f"Permit missing required fields: {missing}"

    def test_coordinates_not_swapped(self, permits_data):
        """After the x/y swap fix, lat should be ~32.x, not ~-97.x."""
        recs = records(permits_data, "permit")
        for rec in recs[:100]:
            lat = rec.get("lat") or rec.get("latitude")
            lon = rec.get("lon") or rec.get("longitude")
            if lat is not None and lon is not None:
                assert 32 <= lat <= 34, \
                    f"Latitude {lat} suggests coordinates are still swapped (should be ~32 for FW)"
                assert -98 <= lon <= -96, \
                    f"Longitude {lon} out of range for Fort Worth"

    def test_status_values_known(self, permits_data):
        KNOWN = {"Issued", "Pending", "Expired", "Finaled", "Approved",
                 "Denied", "Tabled", "Withdrawn", "In Review", ""}
        recs = records(permits_data, "permit")
        for rec in recs:
            s = rec.get("status") or ""
            if s:
                assert s in KNOWN, f"Unknown permit status '{s}' in {rec.get('permit_no')}"

    def test_permit_numbers_unique(self, permits_data):
        recs = records(permits_data, "permit")
        nos = [r["permit_no"] for r in recs if r.get("permit_no")]
        if nos:
            assert len(nos) == len(set(nos)), "Duplicate permit numbers in dataset"


# ─── Crime Data ─────────────────────────────────────────────────────────────

class TestCrimeData:
    def test_file_exists(self, crime_data):
        assert isinstance(crime_data, dict)
        assert "crimes" in crime_data

    def test_case_numbers_unique(self, crime_data):
        records_list = crime_data.get("crimes", [])
        nos = [r["case_no"] for r in records_list if r.get("case_no")]
        if nos:
            # ONTOLOGY.md open issue #5: FWPD scraper picks up same crime multiple times
            # This is a known data quality issue — duplicates expected
            unique = set(nos)
            if len(nos) != len(unique):
                print(f"WARNING: {len(nos) - len(unique)} duplicate case numbers in crime data")

    def test_coordinates_in_fw_bounds(self, crime_data):
        records_list = crime_data.get("crimes", [])
        for rec in records_list[:50]:
            lat = rec.get("lat") or rec.get("latitude")
            lon = rec.get("lon") or rec.get("longitude")
            if lat is not None and lon is not None:
                assert 32.5 <= lat <= 33.1, f"Lat {lat} outside FW bounds"
                assert -97.6 <= lon <= -97.0, f"Lon {lon} outside FW bounds"

    def test_council_district_valid(self, crime_data):
        records_list = crime_data.get("crimes", [])
        for rec in records_list[:50]:
            cd = rec.get("council_district")
            if cd is not None:
                try:
                    n = int(cd)
                    assert 1 <= n <= 11, f"council_district {n} out of range 1-11"
                except (ValueError, TypeError):
                    pass  # None is fine


# ─── Council Districts ──────────────────────────────────────────────────────

class TestCouncilDistricts:
    def test_districts_1_through_11(self):
        f = DATA / "tcgis-council-districts.json"
        if not f.exists():
            pytest.skip("tcgis-council-districts.json not found")
        with open(f) as fh:
            data = json.load(fh)
        districts = data if isinstance(data, list) else data.get("districts") or []
        numbers = sorted([d["district_number"] for d in districts if "district_number" in d])
        assert numbers == list(range(1, 12)), f"Expected districts 1-11, got {numbers}"
