"""
Tests for the snapshot diff tool (scripts/snapshot_diff.py).

The diff tool compares two TAD appraisal snapshots and categorises
parcels into: added, removed, changed, unchanged.
"""
import json, subprocess, sys, pytest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Import the module for unit testing
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "snapshot_diff", SCRIPTS / "snapshot_diff.py"
)
snapshot_diff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(snapshot_diff)


SNAP_A = {
    "0000001": {"account_num": "0000001", "total_value": 150000, "owner_name": "Smith"},
    "0000002": {"account_num": "0000002", "total_value": 200000, "owner_name": "Jones"},
    "0000003": {"account_num": "0000003", "total_value": 300000, "owner_name": "Brown"},
}

SNAP_B = {
    # 0000001: unchanged
    # 0000002: changed value
    "0000001": {"account_num": "0000001", "total_value": 150000, "owner_name": "Smith"},
    "0000002": {"account_num": "0000002", "total_value": 225000, "owner_name": "Jones"},
    # 0000003: removed
    # 0000004: added
    "0000004": {"account_num": "0000004", "total_value": 500000, "owner_name": "Garcia"},
}

SNAP_C = {
    "0000001": {"account_num": "0000001", "total_value": 150000, "owner_name": "Smith"},
}


class TestDiffSnapshots:
    """Core diff logic."""

    def test_added(self):
        result = snapshot_diff.diff_snapshots(SNAP_A, SNAP_B, field="total_value")
        assert len(result["added"]) == 1
        assert result["added"][0]["pidn"] == "0000004"

    def test_removed(self):
        result = snapshot_diff.diff_snapshots(SNAP_A, SNAP_B, field="total_value")
        assert len(result["removed"]) == 1
        assert result["removed"][0]["pidn"] == "0000003"

    def test_changed(self):
        result = snapshot_diff.diff_snapshots(SNAP_A, SNAP_B, field="total_value")
        assert len(result["changed"]) == 1
        assert result["changed"][0]["pidn"] == "0000002"
        assert result["changed"][0]["delta"] == 25000  # 225000 - 200000

    def test_unchanged(self):
        result = snapshot_diff.diff_snapshots(SNAP_A, SNAP_B, field="total_value")
        assert len(result["unchanged"]) == 1
        assert result["unchanged"][0]["pidn"] == "0000001"

    def test_identical_snapshots(self):
        result = snapshot_diff.diff_snapshots(SNAP_C, SNAP_C, field="total_value")
        assert len(result["added"]) == 0
        assert len(result["removed"]) == 0
        assert len(result["changed"]) == 0
        assert len(result["unchanged"]) == 1

    def test_empty_before_is_all_added(self):
        result = snapshot_diff.diff_snapshots({}, SNAP_C, field="total_value")
        assert len(result["added"]) == 1
        assert len(result["removed"]) == 0

    def test_empty_after_is_all_removed(self):
        result = snapshot_diff.diff_snapshots(SNAP_C, {}, field="total_value")
        assert len(result["removed"]) == 1
        assert len(result["added"]) == 0

    def test_custom_field(self):
        result = snapshot_diff.diff_snapshots(SNAP_A, SNAP_B, field="owner_name")
        # 0000002 changed owner_name? No — same "Jones"
        # Actually none changed by owner_name
        changed_by_name = [r for r in result["changed"] if r["pidn"] == "0000002"]
        # owner_name didn't change so it's unchanged or changed
        assert len(result["changed"]) == 0  # no owner_name changed

    def test_numeric_diff_returns_none_for_same_value(self):
        assert snapshot_diff._numeric_diff(100, 100) is None

    def test_numeric_diff_returns_delta(self):
        assert snapshot_diff._numeric_diff(100, 150) == 50

    def test_numeric_diff_handles_none(self):
        assert snapshot_diff._numeric_diff(None, 100) == 100
        assert snapshot_diff._numeric_diff(100, None) == -100

    def test_numeric_diff_handles_non_numeric(self):
        assert snapshot_diff._numeric_diff("abc", "def") == 0
        assert snapshot_diff._numeric_diff("abc", "abc") is None


class TestLoadSnapshot:
    """Loading snapshots from JSON and JSONL files."""

    def test_load_json_array(self, tmp_path):
        path = tmp_path / "snap.json"
        path.write_text(json.dumps([SNAP_C["0000001"]]))
        result = snapshot_diff.load_snapshot(str(path))
        assert "0000001" in result

    def test_load_jsonl(self, tmp_path):
        path = tmp_path / "snap.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in SNAP_C.values()))
        result = snapshot_diff.load_snapshot(str(path))
        assert len(result) == 1
        assert "0000001" in result

    def test_load_missing_file(self, tmp_path):
        result = snapshot_diff.load_snapshot(str(tmp_path / "nonexistent.json"))
        assert result == {}


class TestSnapshotDiffCLI:
    """CLI entry point via subprocess."""

    def test_cli_json_format(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text(json.dumps(list(SNAP_A.values())))
        b.write_text(json.dumps(list(SNAP_B.values())))
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "snapshot_diff.py"),
             str(a), str(b), "--format=json"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "added" in data
        assert "removed" in data
        assert "changed" in data
        assert "unchanged" in data

    def test_cli_table_format(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text(json.dumps(list(SNAP_A.values())))
        b.write_text(json.dumps(list(SNAP_B.values())))
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "snapshot_diff.py"),
             str(a), str(b), "--format=table"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "added:" in result.stdout
        assert "removed:" in result.stdout
        assert "changed:" in result.stdout

    def test_cli_missing_file_graceful(self, tmp_path):
        """Missing files produce an empty diff (not an error)."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "snapshot_diff.py"),
             str(tmp_path / "missing.json"), str(tmp_path / "also-missing.json")],
            capture_output=True, text=True,
        )
        # Graceful: exits 0 with an empty diff
        assert result.returncode == 0
        assert "added:          0" in result.stdout
        assert "removed:        0" in result.stdout

    def test_cli_custom_field(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text(json.dumps(list(SNAP_A.values())))
        b.write_text(json.dumps(list(SNAP_B.values())))
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "snapshot_diff.py"),
             str(a), str(b), "--field=land_value"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "land_value" in result.stdout
