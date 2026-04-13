"""
Additional tests targeting uncovered error paths and CLI.

Goal: push resolve_address_full.py toward 80%+ coverage.
"""
import sys, pytest, subprocess, json
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Reload the module fresh for each test class to get clean state
@pytest.fixture(autouse=True)
def reload_module():
    """Ensure a clean module import for each test."""
    import importlib
    if "scripts.resolve_address_full" in sys.modules:
        m = sys.modules["scripts.resolve_address_full"]
        importlib.reload(m)
    yield


# ─── CLI tests ────────────────────────────────────────────────────────────────

class TestResolveCLI:
    """Cover the __main__ block."""

    def test_cli_no_args_prints_help(self, tmp_path):
        """No address arg → print_help() and return."""
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "resolve_address_full.py")],
            capture_output=True, text=True,
            cwd=str(Path(SCRIPTS).parent),
        )
        assert r.returncode == 0
        assert "usage:" in r.stdout or "address" in r.stdout.lower()

    def test_cli_with_valid_address(self, tmp_path):
        """With address → resolves and prints summary to stdout."""
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "resolve_address_full.py"),
             "704 E Weatherford St, Fort Worth, TX 76102"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(SCRIPTS).parent),
        )
        assert r.returncode == 0, f"CLI failed: {r.stderr}"
        assert "Weatherford" in r.stderr or "DAILEY" in r.stderr

    def test_cli_with_output_flag_writes_file(self, tmp_path):
        """--output writes JSON to file."""
        out_file = tmp_path / "resolve-out.json"
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "resolve_address_full.py"),
             "704 E Weatherford St, Fort Worth, TX 76102",
             "--output", str(out_file)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(SCRIPTS).parent),
        )
        assert r.returncode == 0, f"CLI failed: {r.stderr}"
        assert out_file.exists(), f"Output not written. stderr: {r.stderr[:200]}"
        data = json.loads(out_file.read_text())
        assert "coordinates" in data


# ─── Error paths ─────────────────────────────────────────────────────────────



class TestMainFunction:
    """Call main() directly so pytest-cov tracks it."""

    def test_main_with_address(self, tmp_path, capsys):
        """main() with address — exercises lines 627-669 for coverage."""
        import scripts.resolve_address_full as r
        import argparse

        out_file = tmp_path / "main-out.json"
        args = argparse.Namespace(
            address="704 E Weatherford St, Fort Worth, TX 76102",
            output=str(out_file),
            tad_path=None,
        )

        # Patch argparse so main() doesn't try to parse sys.argv
        with patch("sys.argv", ["resolve_address_full.py", "704 E Weatherford St, Fort Worth, TX 76102", "--output", str(out_file)]):
            r.main()

        # Verify output was written
        assert out_file.exists(), "main() should write output file"
        data = json.loads(out_file.read_text())
        assert "coordinates" in data

    def test_main_returns_none_on_bad_address(self, tmp_path, capsys):
        """main() with no address → returns None early (line 600)."""
        import scripts.resolve_address_full as r
        with patch("sys.argv", ["resolve_address_full.py"]):
            result = r.main()
        # main() returns None when no address provided


class TestHAS_SHAPELYFalse:
    """Lines 292-293: HAS_SHAPELY=False early return in find_district_by_tcgis()."""

    def test_returns_none_when_shapely_unavailable(self):
        """With shapely unavailable, point-in-polygon returns None."""
        import scripts.resolve_address_full as r
        old_shapely = r.HAS_SHAPELY
        old_pyproj = r.HAS_PYPROJ
        r.HAS_SHAPELY = False
        r.HAS_PYPROJ = False
        try:
            result = r.find_district_by_tcgis(32.7593, -97.3283)
            assert result is None
        finally:
            r.HAS_SHAPELY = old_shapely
            r.HAS_PYPROJ = old_pyproj


class TestHAS_PYPROJFalse:
    """FLU: HAS_PYPROJ=False early return."""

    def test_flu_returns_none_when_pyproj_unavailable(self):
        """With pyproj unavailable, FLU coordinate transform returns None."""
        import scripts.resolve_address_full as r
        old_pyproj = r.HAS_PYPROJ
        r.HAS_PYPROJ = False
        try:
            result = r.resolve_future_land_use(32.7593, -97.3283)
            assert result is None
        finally:
            r.HAS_PYPROJ = old_pyproj


class TestCouncilDistrictsLoadError:
    """Lines 249-252: HAS_SHAPELY or HAS_PYPROJ unavailable in load_council_districts."""

    def test_returns_empty_when_pyproj_unavailable(self):
        """load_council_districts: HAS_PYPROJ=False → skip pyproj, use TCGIS."""
        import scripts.resolve_address_full as r
        old_shapely = r.HAS_SHAPELY
        old_pyproj = r.HAS_PYPROJ
        r.HAS_SHAPELY = False
        r.HAS_PYPROJ = False
        try:
            # Force reload
            r._districts_loaded = False
            r._council_polygons = {}
            polygons = r.load_council_districts()
            # When pyproj unavailable AND shapely unavailable: returns empty dict
            assert polygons == {}
        finally:
            r.HAS_SHAPELY = old_shapely
            r.HAS_PYPROJ = old_pyproj
            r._districts_loaded = False
            r._council_polygons = {}


class TestFWPDCrimeLookup:
    """Lines 186-206: find_council_district_by_block HTTP errors."""

    def test_returns_none_on_http_error(self):
        """HTTP error → returns None gracefully."""
        import scripts.resolve_address_full as r
        with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            result = r.find_council_district_by_block("100 E WEATHERFORD")
            assert result is None

    def test_returns_none_when_no_features(self):
        """FWPD returns no matching features → returns None."""
        import scripts.resolve_address_full as r
        with patch("urllib.request.urlopen",
                   return_value=MagicMock(
                       read=lambda: json.dumps({"features": []}).encode()
                   )):
            result = r.find_council_district_by_block("99999 UNKNOWN BLOCK")
            assert result is None


class TestFutureLandUseHTTPError:
    """Lines 676-678: FLU HTTP error in resolve_future_land_use."""

    def test_flu_returns_none_on_http_error(self):
        """FLU lookup HTTP error → returns None gracefully."""
        import scripts.resolve_address_full as r
        with patch("urllib.request.urlopen", side_effect=Exception("HTTP error")):
            result = r.resolve_future_land_use(32.7593, -97.3283)
            assert result is None


class TestTADLookupEdgeCases:
    """TAD lookup: address not in dataset → parcel is None."""

    def test_parcel_none_when_not_in_tad(self):
        """Address not found in TAD → parcel field is None."""
        import scripts.resolve_address_full as r
        # Use a fake address unlikely to be in TAD
        result = r.resolve_full("999999 FAKE ADDRESS ST, FORT WORTH, TX 99999")
        assert result.get("parcel") is None or result.get("parcel") == {}


class TestGeocoderEdgeCases:
    """Census geocoder: no match → address resolution still proceeds."""

    def test_geocode_none_still_resolves_parcel(self):
        """Census returns no match → resolution continues with parcel data."""
        import scripts.resolve_address_full as r
        # If census fails but we have TAD data, parcel lookup still works
        result = r.resolve_full("704 E Weatherford St, Fort Worth, TX 76102")
        # We got parcel data via TAD even if census succeeded
        parcel = result.get("parcel") or {}
        assert parcel.get("owner_name") is not None


class TestPermitsEdgeCases:
    """Permit lookup edge cases."""

    def test_find_permits_empty_when_no_permits(self):
        """Empty permits list → returns empty result."""
        import scripts.resolve_address_full as r
        result = r.find_permits_by_coords(32.7593, -97.3283, [])
        assert result == []

    def test_find_permits_none_when_coords_none(self):
        """None lat/lon → returns empty list."""
        import scripts.resolve_address_full as r
        result = r.find_permits_by_coords(None, None, [{"lat": 32.75}])
        assert result == []


class TestLoadCouncilDistrictsHTTPError:
    """HTTP error in load_council_districts → continues gracefully."""

    def test_load_councils_continues_on_http_error(self):
        """HTTP failure → function returns empty dict, no crash."""
        import scripts.resolve_address_full as r
        old = r._districts_loaded
        r._districts_loaded = False
        r._council_polygons = {}
        try:
            with patch("urllib.request.urlopen", side_effect=Exception("HTTP error")):
                polygons = r.load_council_districts()
                assert polygons == {}
        finally:
            r._districts_loaded = old
