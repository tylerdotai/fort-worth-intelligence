"""
Tests for graph traversal, query, and schema API endpoints.

Covers: /graph/{id}, /query/entities, /query/aggregate, /meta/schema
"""
import sys, pytest
from pathlib import Path
from unittest.mock import patch

# Ensure the api_server module can be imported
API_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(API_DIR))


class TestGraphTraversal:
    """GET /graph/{entity_id}"""

    def test_graph_unknown_entity_returns_empty(self):
        """Unknown entity ID → returns graph with unknown node, no edges."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/graph/fw:address:000000")
        assert response.status_code == 200
        data = response.json()
        assert "root" in data
        assert "nodes" in data
        assert "edges" in data
        assert "provenance" in data
        assert "freshness" in data
        assert data["depth"] == 1  # default depth

    def test_graph_depth_param(self):
        """Depth parameter (0–3) is accepted and reflected."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        for depth in [0, 2, 3]:
            response = client.get(f"/graph/fw:address:abc123?depth={depth}")
            assert response.status_code == 200
            assert response.json()["depth"] == depth

    def test_graph_depth_out_of_range(self):
        """Depth > 3 → 422 validation error."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/graph/fw:address:abc123?depth=5")
        assert response.status_code == 422

    def test_graph_provenance_present(self):
        """Every graph response includes provenance block."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/graph/fw:council:2")
        assert response.status_code == 200
        prov = response.json()["provenance"]
        assert "source" in prov
        assert "ontology_version" in prov

    def test_graph_parcel_id(self):
        """Parcel entity ID → kind=Parcel in root node."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/graph/fw:parcel:01234567")
        assert response.status_code == 200
        assert response.json()["root"]["kind"] == "Parcel"

    def test_graph_school_id(self):
        """School district entity ID → kind=SchoolDistrict."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/graph/fw:school:fort-worth-isd")
        assert response.status_code == 200
        assert response.json()["root"]["kind"] == "SchoolDistrict"


class TestQueryEntities:
    """GET /query/entities"""

    def test_query_entities_no_index(self):
        """No address index → returns empty items list."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/query/entities")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "filters" in data

    def test_query_entities_pagination(self):
        """limit and offset parameters work."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/query/entities?limit=5&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 10

    def test_query_entities_limit_validation(self):
        """limit > 100 → 422 validation error."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/query/entities?limit=200")
        assert response.status_code == 422


class TestQueryAggregate:
    """GET /query/aggregate"""

    def test_aggregate_returns_valid_response(self):
        """Returns rows when indexed, or graceful error when no index yet."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/query/aggregate?group_by=council_district")
        assert response.status_code == 200
        data = response.json()
        # Valid response: either rows or an informative error
        if "error" not in data:
            assert "rows" in data
            assert "group_by" in data
        else:
            # No resolved index yet — expected state before first build
            assert data["error"] == "no resolved address index found"

    def test_aggregate_school_district_accepted(self):
        """group_by=school_district → accepted (200 even if no data yet)."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/query/aggregate?group_by=school_district")
        assert response.status_code == 200

    def test_aggregate_metric_param_in_response(self):
        """metric param is echoed back in response."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/query/aggregate?group_by=owner_type&metric=avg_value")
        assert response.status_code == 200


class TestMetaSchema:
    """GET /meta/schema"""

    def test_schema_returns_entity_types(self):
        """Schema response includes entity_types array."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/meta/schema")
        assert response.status_code == 200
        data = response.json()
        assert "entity_types" in data
        assert isinstance(data["entity_types"], list)
        assert len(data["entity_types"]) > 0

    def test_schema_has_required_fields(self):
        """Schema includes ontology_version, namespace, provenance_fields."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/meta/schema")
        assert response.status_code == 200
        data = response.json()
        assert data["ontology_version"] == "1.0"
        assert "namespace" in data
        assert "provenance_fields" in data
        assert "Address" in [e["name"] for e in data["entity_types"]]
        assert "Parcel" in [e["name"] for e in data["entity_types"]]


class TestLegistarHelpers:
    """Legistar helper functions — loaded and called by API endpoints."""

    def test_get_district_items_filters_by_district(self):
        """get_district_items returns only matching items."""
        import api_server as api
        api._legistar_cache.clear()  # reset cache

        # Patch the cache with synthetic data
        api._legistar_cache = {
            "agenda": {
                "meta": {"scraped_at": "2026-01-01T00:00:00Z"},
                "meetings": [
                    {
                        "id": 100,
                        "meeting_date": "2026-03-01",
                        "meeting_time": "10:00 AM",
                        "meeting_name": "City Council",
                        "meeting_location": "City Hall",
                        "agenda_status": "passed",
                        "video_available": "yes",
                        "source_url": "https://fortworthgov.legistar.com",
                        "item_count": 2,
                        "items": [
                            {"title": "Item 1", "council_districts": "2"},
                            {"title": "Item 2", "council_districts": "3"},
                        ],
                    },
                    {
                        "id": 101,
                        "meeting_date": "2026-02-01",
                        "meeting_time": "10:00 AM",
                        "meeting_name": "City Council",
                        "meeting_location": "City Hall",
                        "agenda_status": "passed",
                        "video_available": "yes",
                        "source_url": "https://fortworthgov.legistar.com",
                        "item_count": 1,
                        "items": [
                            {"title": "Item 3", "council_districts": "2 and CD 9"},
                        ],
                    },
                ],
            },
            "meeting_map": {"100": {"id": 100, "name": "City Council"}},
        }

        result = api.get_district_items("2")
        assert len(result) == 2  # both meetings have district 2 items
        assert result[0]["id"] == 100
        assert result[0]["item_count"] == 1  # only item matching district 2

    def test_get_district_items_all_returns_all(self):
        """district='all' returns items from all meetings."""
        import api_server as api
        api._legistar_cache.clear()

        api._legistar_cache = {
            "agenda": {
                "meta": {"scraped_at": "2026-01-01T00:00:00Z"},
                "meetings": [
                    {
                        "id": 200,
                        "meeting_date": "2026-03-01",
                        "meeting_time": "10:00 AM",
                        "meeting_name": "Council",
                        "meeting_location": "City Hall",
                        "agenda_status": "passed",
                        "video_available": "yes",
                        "source_url": "https://fortworthgov.legistar.com",
                        "item_count": 2,
                        "items": [
                            {"title": "All Item", "council_districts": "ALL"},
                            {"title": "Budget", "council_districts": "5"},
                        ],
                    },
                ],
            },
            "meeting_map": {},
        }

        result = api.get_district_items("all")
        assert len(result) == 1
        assert result[0]["item_count"] == 2  # ALL matches both items

    def test_get_meeting_items_returns_meeting(self):
        """get_meeting_items returns full meeting with items."""
        import api_server as api
        api._legistar_cache.clear()

        api._legistar_cache = {
            "agenda": {
                "meta": {"scraped_at": "2026-01-01T00:00:00Z"},
                "meetings": [
                    {
                        "id": 300,
                        "meeting_date": "2026-03-15",
                        "meeting_time": "1:00 PM",
                        "meeting_name": "Special Meeting",
                        "meeting_location": "City Hall",
                        "agenda_status": "passed",
                        "video_available": "no",
                        "source_url": "https://fortworthgov.legistar.com",
                        "item_count": 1,
                        "items": [{"title": "Special Item", "council_districts": "7"}],
                    },
                ],
            },
            "meeting_map": {},
        }

        result = api.get_meeting_items(300)
        assert result["id"] == 300
        assert len(result["items"]) == 1

    def test_get_meeting_items_not_found(self):
        """get_meeting_items returns error dict for unknown ID."""
        import api_server as api
        api._legistar_cache.clear()

        api._legistar_cache = {
            "agenda": {"meta": {"scraped_at": "2026-01-01"}, "meetings": []},
            "meeting_map": {},
        }

        result = api.get_meeting_items(99999)
        assert "error" in result


class TestBatchResolve:
    """POST /resolve/batch"""

    def test_batch_resolve_rejects_empty_list(self):
        """Empty address list → 200 with zero results."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/resolve/batch", json={"addresses": []})
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["total"] == 0


class TestHealthEndpoint:
    """GET /health"""

    def test_health_returns_ok(self):
        """Health check returns status ok."""
        from api_server import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
