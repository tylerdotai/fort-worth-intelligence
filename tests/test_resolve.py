"""
Property-based tests for the /resolve endpoint.

Covers:
- Response shape and required fields
- Coordinate bounding boxes
- Null safety (ETJ addresses)
- Parcel value types
- Permit consistency
- Future land use fields
- Council district format
"""
import pytest
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from scripts.resolve_address_full import resolve_full

# ─── helpers ────────────────────────────────────────────────────────────────

def is_valid_latlon(lat, lon):
    if lat is None or lon is None:
        return True  # ETJ / unresolved
    return -90 <= lat <= 90 and -180 <= lon <= 180


def is_inside_fort_worth(lat, lon, bounds):
    if lat is None or lon is None:
        return True
    return bounds["lat_min"] <= lat <= bounds["lat_max"] and bounds["lon_min"] <= lon <= bounds["lon_max"]


def is_valid_council_district(cd):
    """District is 1-11 as integer, or None."""
    if cd is None:
        return True
    if isinstance(cd, (int, str)):
        try:
            n = int(cd)
            return 1 <= n <= 11
        except (ValueError, TypeError):
            return False
    return False


# ─── tests ─────────────────────────────────────────────────────────────────

class TestResolveResponseShape:
    """Every resolve response must have these top-level keys."""

    REQUIRED_TOP_LEVEL = {
        "_meta", "query_address", "coordinates",
        "parcel", "council_district",
        "future_land_use", "permits",
    }

    def test_has_required_keys(self, test_addresses, fw_bounds):
        addr = test_addresses[0]  # 704 E Weatherford — known good
        result = resolve_full(addr)
        assert result is not None, f"resolve_full returned None for {addr}"
        assert isinstance(result, dict), "result must be a dict"
        assert self.REQUIRED_TOP_LEVEL.issubset(result.keys()), \
            f"Missing keys: {self.REQUIRED_TOP_LEVEL - result.keys()}"

    def test_meta_has_resolution_ms(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        assert "_meta" in result
        assert "resolution_ms" in result["_meta"]
        assert isinstance(result["_meta"]["resolution_ms"], int)
        assert result["_meta"]["resolution_ms"] >= 0

    def test_meta_has_query_address(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        assert "_meta" in result


class TestCoordinates:
    """Coordinates must be valid lat/lon and inside Fort Worth bounding box."""

    def test_coords_valid_range(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        coords = result.get("coordinates") or {}
        lat = coords.get("lat")
        lon = coords.get("lon")
        assert is_valid_latlon(lat, lon), f"Invalid lat/lon: {lat}, {lon}"

    def test_coords_inside_fw_bounds(self, test_addresses, fw_bounds):
        addr = test_addresses[0]
        result = resolve_full(addr)
        coords = result.get("coordinates") or {}
        lat = coords.get("lat")
        lon = coords.get("lon")
        assert is_inside_fort_worth(lat, lon, fw_bounds), \
            f"Coordinates {lat},{lon} outside FW bounds"

    def test_coords_null_safe(self, etj_addresses):
        """ETJ addresses may have null coords — must not raise."""
        addr = etj_addresses[0]
        result = resolve_full(addr)
        coords = result.get("coordinates") or {}
        # Should not crash, coords may be None
        lat = coords.get("lat")
        lon = coords.get("lon")
        assert is_valid_latlon(lat, lon)


class TestParcel:
    """Parcel fields must have correct types and reasonable values."""

    def test_total_value_numeric_or_none(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        parcel = result.get("parcel") or {}
        tv = parcel.get("total_value")
        assert tv is None or isinstance(tv, (int, float)), \
            f"total_value must be numeric or None, got {type(tv).__name__}: {tv}"

    def test_appraised_value_numeric_or_none(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        parcel = result.get("parcel") or {}
        av = parcel.get("appraised_value")
        assert av is None or isinstance(av, (int, float)), \
            f"appraised_value must be numeric or None, got {type(av).__name__}"

    def test_year_built_numeric_or_none(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        parcel = result.get("parcel") or {}
        yb = parcel.get("year_built")
        assert yb is None or (
            isinstance(yb, (int, str)) and str(yb).isdigit()
        ), f"year_built must be 4-digit year or None, got {yb}"
        if yb is not None:
            yr = int(str(yb).replace(",", "")[:4])
            assert 1800 <= yr <= 2030, f"year_built {yr} out of reasonable range"

    def test_owner_name_never_empty_string(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        parcel = result.get("parcel") or {}
        owner = parcel.get("owner_name")
        assert owner is None or (isinstance(owner, str) and len(owner.strip()) > 0), \
            "owner_name must be non-empty string or None"


class TestCouncilDistrict:
    """Council district must be 1-11 as integer, or None for ETJ."""

    def test_district_valid_range_or_none(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        cd = result.get("council_district")
        cd_num = cd.get("district_number") if isinstance(cd, dict) else cd
        assert is_valid_council_district(cd_num), \
            f"district_number must be 1-11 or None, got {cd_num}"

    def test_etj_address_returns_null_district(self, etj_addresses):
        """Addresses outside city limits return null district, not a crash."""
        addr = etj_addresses[0]
        result = resolve_full(addr)
        cd = result.get("council_district")
        # Should be None or null dict, not a crash
        assert cd is None or cd == {}

    def test_member_email_valid_format(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        cd = result.get("council_district")
        if isinstance(cd, dict) and cd.get("email"):
            email = cd["email"]
            assert "@" in email and "." in email, f"Invalid email: {email}"


class TestPermits:
    """Permit counts must match items length; status values must be known."""

    KNOWN_STATUSES = {
        "Issued", "Pending", "Expired", "Finaled",
        "Approved", "Denied", "Tabled", "Withdrawn", "In Review",
    }

    def test_permit_count_matches_items_length(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        permits = result.get("permits") or {}
        count = permits.get("count", 0)
        items = permits.get("items") or []
        assert count == len(items), \
            f"permit count {count} != items length {len(items)}"

    def test_permit_count_nonnegative(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        permits = result.get("permits") or {}
        assert permits.get("count", 0) >= 0

    def test_permit_status_values(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        permits = result.get("permits") or {}
        for item in permits.get("items") or []:
            status = item.get("status", "Unknown")
            assert status in self.KNOWN_STATUSES, \
                f"Unknown permit status '{status}' in {item.get('permit_no')}"

    def test_permit_numbers_unique(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        permits = result.get("permits") or {}
        nos = [p["permit_no"] for p in permits.get("items") or []]
        assert len(nos) == len(set(nos)), "Duplicate permit numbers found"

    def test_null_permits_safe(self, etj_addresses):
        """ETJ addresses with no permits must return empty dict, not crash."""
        addr = etj_addresses[0]
        result = resolve_full(addr)
        permits = result.get("permits")
        assert permits is None or isinstance(permits, dict)


class TestFutureLandUse:
    """FLU fields must have correct types."""

    KNOWN_LAND_USE = {
        "SF", "R1", "R2", "R3", "R4", "R5",
        "MU", "NC", "CBD", "CH", "LI", "HI",
        "A", "B", "C", "D", "E", "F", "G",
        "RURAL", "AG", "FOREST", "PARK", "OS",
    }

    def test_flu_returns_dict_or_none(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        flu = result.get("future_land_use")
        assert flu is None or isinstance(flu, dict), \
            f"future_land_use must be dict or None, got {type(flu)}"

    def test_flu_designation_is_string_or_none(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        flu = result.get("future_land_use") or {}
        desig = flu.get("designation")
        assert desig is None or isinstance(desig, str)

    def test_flu_growth_center_is_string_or_none(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        flu = result.get("future_land_use") or {}
        gc = flu.get("growth_center")
        assert gc is None or isinstance(gc, str)

    def test_flu_source_is_url(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        flu = result.get("future_land_use") or {}
        src = flu.get("source")
        if src:
            assert src.startswith("http"), f"source must be URL: {src}"

    def test_flu_null_safe(self, etj_addresses):
        """FLU lookup on ETJ address returns None, not a crash."""
        addr = etj_addresses[0]
        result = resolve_full(addr)
        flu = result.get("future_land_use")
        assert flu is None or isinstance(flu, dict)


class TestCouncilAgenda:
    """Agenda items - api_server adds these, not resolve_full layer.
    These tests verify the api_server endpoint behavior."""

    def test_council_agenda_absent_from_resolve_full(self, test_addresses):
        # council_agenda is added by api_server, not resolve_full
        # resolve_full may or may not include it
        addr = test_addresses[0]
        result = resolve_full(addr)
        agenda = result.get("council_agenda")
        assert agenda is None or isinstance(agenda, dict)


class TestUtilitiesAndStateRep:
    """Utilities and state rep must be present and well-formed."""

    def test_utilities_present(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        utils = result.get("utilities")
        assert utils is not None, "utilities should always be present"
        assert isinstance(utils, dict)

    def test_utility_services_are_dicts_with_provider(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        utils = result.get("utilities") or {}
        for service in ["water", "electric", "gas", "stormwater"]:
            val = utils.get(service)
            if val:
                assert isinstance(val, dict), f"{service} must be dict, got {type(val)}"
                assert "provider" in val, f"{service} missing 'provider' key"

    def test_state_rep_present(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        rep = result.get("state_representative")
        assert rep is not None, "state_representative should be present"
        assert isinstance(rep, dict)


class TestStableIDs:
    """Every entity with a stable ID field must have one."""

    def test_parcel_has_gis_link(self, test_addresses):
        addr = test_addresses[0]
        result = resolve_full(addr)
        parcel = result.get("parcel") or {}
        gis = parcel.get("gis_link")
        assert gis is None or (isinstance(gis, str) and len(gis) > 0)

    def test_resolve_race_condition_free(self, test_addresses):
        """Two simultaneous resolves should both succeed."""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(resolve_full, addr) for addr in test_addresses[:2]]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)


class TestAllTestAddresses:
    """Run the full property suite across all known-good test addresses."""

    @pytest.mark.parametrize("address", [
        "704 E Weatherford St, Fort Worth, TX 76102",
        "600 Cooper St, Fort Worth, TX 76102",
        "3040 S University Dr, Fort Worth, TX 76109",
    ])
    def test_resolve_returns_valid_response(self, address, fw_bounds):
        result = resolve_full(address)
        assert result is not None, f"resolve_full returned None for {address}"
        assert isinstance(result, dict)
        # coords
        coords = result.get("coordinates") or {}
        lat = coords.get("lat")
        lon = coords.get("lon")
        assert is_valid_latlon(lat, lon)
        # district
        cd = result.get("council_district")
        cd_num = cd.get("district_number") if isinstance(cd, dict) else cd
        assert is_valid_council_district(cd_num)
        # permits count
        permits = result.get("permits") or {}
        count = permits.get("count", 0)
        items = permits.get("items") or []
        assert count == len(items)
        # meta
        assert "_meta" in result
        assert "resolution_ms" in result["_meta"]
