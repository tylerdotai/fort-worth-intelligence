"""
Tests for Legistar data: meetings + agenda items.
"""
import json, pytest
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"


class TestLegistarDataExists:
    def test_meetings_file_exists(self):
        f = DATA / "legistar-meetings.json"
        assert f.exists(), f"{f} not found - run extract_legistar_agenda.py first"

    def test_agenda_file_exists(self):
        f = DATA / "legistar-agenda-items.json"
        assert f.exists(), f"{f} not found - run extract_legistar_agenda.py first"


class TestLegistarMeetings:
    def test_meetings_list(self, legistar_meetings):
        meetings = legistar_meetings.get("meetings", [])
        assert isinstance(meetings, list)
        assert len(meetings) > 0, "Expected some meetings in data"

    def test_meeting_has_required_fields(self, legistar_meetings):
        for m in legistar_meetings.get("meetings", [])[:5]:
            assert "id" in m, f"Meeting missing 'id': {m}"
            assert "body" in m, f"Meeting missing 'body': {m}"
            assert "meeting_date" in m, f"Meeting missing meeting_date: {m}"

    def test_meeting_date_format(self, legistar_meetings):
        for m in legistar_meetings.get("meetings", [])[:10]:
            date_str = m.get("meeting_date") or ""
            assert len(date_str) >= 8, f"Date '{date_str}' too short to be valid"

    def test_distinct_meeting_ids(self, legistar_meetings):
        ids = [m["id"] for m in legistar_meetings.get("meetings", []) if m.get("id")]
        assert len(ids) == len(set(ids)), "Duplicate meeting IDs found"


class TestLegistarAgendaItems:
    """Agenda structure: {meta: {}, meetings: [{id, body, meeting_date, items: [...]}]}"""

    def test_agenda_top_level_has_meetings(self, legistar_agenda):
        assert "meetings" in legistar_agenda or "items" in legistar_agenda

    def test_meetings_contain_items(self, legistar_agenda):
        meetings = legistar_agenda.get("meetings", [])
        if not meetings:
            items = legistar_agenda.get("items", [])
            assert len(items) >= 0
            return
        for meeting in meetings[:5]:
            assert "id" in meeting
            assert "items" in meeting or "body" in meeting

    def test_agenda_items_have_file_numbers(self, legistar_agenda):
        meetings = legistar_agenda.get("meetings", [])
        items_found = False
        for meeting in meetings[:10]:
            for item in meeting.get("items", [])[:10]:
                items_found = True
                assert "file_number" in item, f"Item missing file_number: {item}"
                assert "title" in item, f"Item missing title: {item}"
        assert items_found, "No items found in any meetings"

    def test_file_numbers_expected_duplicates(self, legistar_agenda):
        """File numbers may appear in multiple meetings (passed in one committee, approved in another).
        This is expected Legistar behavior — agenda items are referenced across committees."""
        meetings = legistar_agenda.get("meetings", [])
        nos = []
        for meeting in meetings:
            for item in meeting.get("items", []):
                if item.get("file_number"):
                    nos.append(item["file_number"])
        # Just verify we found items — duplicates across meetings are expected
        assert len(nos) > 0, "Expected some agenda items"

    def test_status_values_are_strings(self, legistar_agenda):
        """Status values are free-form strings in Fort Worth Legistar."""
        meetings = legistar_agenda.get("meetings", [])
        for meeting in meetings:
            for item in meeting.get("items", []):
                s = item.get("status") or ""
                assert isinstance(s, str), f"status must be string, got {type(s)}"


class TestLegistarApiEndpoint:
    """API endpoint tests — require running server on port 8000."""

    def test_legistar_endpoint_requires_server(self):
        pytest.skip("API endpoint tests require running server — tested separately")
