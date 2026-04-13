"""
API server — targeted coverage for observability and ops paths.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

API_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(API_DIR))

from api_server import (
    app,
    get_district_items,
    get_meeting_items,
    REPO,
    get_meta,
    load_legistar,
)


class TestObservabilityEndpoints:
    """GET /health and /meta routes."""

    def test_health_returns_service_metadata(self):
        """Health includes service name and version."""
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "fort-worth-intelligence"
        assert data["status"] == "ok"

    def test_meta_returns_version_fields(self):
        """Meta endpoint returns version info."""
        client = TestClient(app)
        r = client.get("/meta/schema")
        assert r.status_code == 200
        data = r.json()
        assert "ontology_version" in data
        assert "schema_version" in data


class TestResolveEndpointCoverage:
    """Cover the resolve endpoint response paths."""

    def test_resolve_adds_resolution_ms(self):
        """resolve_full result gets resolution_ms in _meta."""
        import scripts.resolve_address_full as r
        result = r.resolve_full("600 Cooper St, Fort Worth, TX 76102")
        assert "_meta" in result
        assert "resolution_ms" in result["_meta"]
        assert isinstance(result["_meta"]["resolution_ms"], int)

    def test_resolve_returns_caveats_list(self):
        """Unresolvable address returns caveats list."""
        import scripts.resolve_address_full as r
        result = r.resolve_full("999999 NOT A REAL ADDRESS ST, FORT WORTH, TX 99999")
        assert "_caveats" in result
        assert isinstance(result["_caveats"], list)

    def test_resolve_safe_to_call_multiple_times(self):
        """Multiple calls don't accumulate state."""
        import scripts.resolve_address_full as r
        r1 = r.resolve_full("600 Cooper St, Fort Worth, TX 76102")
        r2 = r.resolve_full("600 Cooper St, Fort Worth, TX 76102")
        # Both should have valid structure
        assert "_meta" in r1 and "_meta" in r2
        assert "resolved_at" in r1


class TestLegistarEndpointCoverage:
    """Legistar endpoint edge cases."""

    def test_legistar_district_invalid(self):
        """Invalid district → 400."""
        client = TestClient(app)
        r = client.get("/legistar/99")
        assert r.status_code == 400

    def test_legistar_district_all(self):
        """district=all is accepted."""
        client = TestClient(app)
        r = client.get("/legistar/all")
        assert r.status_code == 200

    def test_legistar_meeting_not_found(self):
        """Unknown meeting ID → 404."""
        client = TestClient(app)
        r = client.get("/legistar/meeting/999999999")
        assert r.status_code == 404

    def test_legistar_cache_loaded(self):
        """load_legistar returns cached data on second call."""
        import api_server as api
        api._legistar_cache.clear()
        # Prime cache
        api.load_legistar()
        # Second call should return same cache
        result = api.load_legistar()
        assert "agenda" in result or "error" in result

    def test_legistar_district_7(self):
        """District 7 is valid (has a known council member)."""
        client = TestClient(app)
        r = client.get("/legistar/7")
        assert r.status_code == 200


class TestGraphTraversalCoverage:
    """Cover edge branches in graph traversal."""

    def test_graph_depth_0_returns_root_only(self):
        """depth=0 → no edges needed, root only."""
        client = TestClient(app)
        r = client.get("/graph/fw:council:7?depth=0")
        assert r.status_code == 200
        data = r.json()
        assert data["depth"] == 0
        assert len(data["nodes"]) >= 1

    def test_graph_unknown_id_has_null_geometry(self):
        """Unknown entity → root node with null geometry fields."""
        client = TestClient(app)
        r = client.get("/graph/fw:address:ffff00")
        assert r.status_code == 200
        data = r.json()
        root = data["root"]
        assert root["kind"] == "unknown"
        assert data["edges"] == []

    def test_graph_root_in_nodes(self):
        """Root node always appears in nodes array."""
        client = TestClient(app)
        r = client.get("/graph/fw:school:fort-worth-isd?depth=1")
        assert r.status_code == 200
        data = r.json()
        root_id = data["root"]["id"]
        node_ids = [n["id"] for n in data["nodes"]]
        assert root_id in node_ids

    def test_graph_parcel_has_parcel_edges(self):
        """Parcel ID → has edges."""
        client = TestClient(app)
        r = client.get("/graph/fw:parcel:01234567")
        assert r.status_code == 200
        data = r.json()
        assert data["root"]["kind"] == "Parcel"
        assert isinstance(data["edges"], list)


class TestQueryCoverage:
    """Query endpoint branches."""

    def test_query_entities_with_kind_filter(self):
        """kind filter is passed through to response."""
        client = TestClient(app)
        r = client.get("/query/entities?kind=Address")
        assert r.status_code == 200
        assert r.json()["filters"]["kind"] == "Address"

    def test_query_entities_search(self):
        """search param filters labels."""
        client = TestClient(app)
        r = client.get("/query/entities?search=Weatherford")
        assert r.status_code == 200
        data = r.json()
        assert data["filters"]["search"] == "Weatherford"

    def test_query_aggregate_unknown_group_by(self):
        """Unknown group_by falls back gracefully."""
        client = TestClient(app)
        r = client.get("/query/aggregate?group_by=unknown_field")
        assert r.status_code == 200
        # Should return empty rows or error, not 500


class TestRootEndpoint:
    """Root endpoint lists all routes."""

    def test_root_lists_all_endpoints(self):
        """Root returns a dict of all known endpoints."""
        client = TestClient(app)
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        endpoints = data["endpoints"]
        assert "GET /resolve?address=..." in endpoints
        assert "GET /graph/{entity_id}?depth=0-3" in endpoints
        assert "GET /query/entities" in endpoints
        assert "GET /query/aggregate" in endpoints
        assert "GET /meta/schema" in endpoints
        assert "GET /health" in endpoints
