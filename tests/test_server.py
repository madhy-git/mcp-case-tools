import asyncio
import json

import pytest
from mcp import Client

from mcp_case_tools.server import create_server


def data(r):
    return json.loads(r.content[0].text)


def call(role, tool, args):
    async def go():
        server = create_server(role)
        async with Client(server) as c:
            try:
                return await c.call_tool(tool, args), server
            finally:
                pass

    return asyncio.run(go())


def test_lists_tools():
    async def go():
        async with Client(create_server("viewer")) as c:
            return {t.name for t in (await c.list_tools()).tools}

    assert asyncio.run(go()) == {"get_case", "search_cases", "add_note", "progress_case"}


def test_viewer_can_read_but_not_write():
    r, _ = call("viewer", "get_case", {"case_id": "CASE-1"})
    assert not r.is_error and data(r)["provider"] == "Sunrise Care"
    r, server = call("viewer", "add_note", {"case_id": "CASE-1", "note": "x"})
    assert r.is_error
    assert server.audit[-1]["allowed"] is False and server.audit[-1]["missing_scope"] == "case:write"


def test_officer_progress_and_invalid_transition():
    r, _ = call("officer", "progress_case", {"case_id": "CASE-1", "new_status": "assessment"})
    assert data(r)["status"] == "assessment"
    r, server = call("officer", "progress_case", {"case_id": "CASE-1", "new_status": "enforcement"})
    assert r.is_error and server.audit[-1]["reason"] == "invalid_transition"


def test_enforcement_needs_manager_approval():
    args = {"case_id": "CASE-2", "new_status": "enforcement", "approved_by_manager": True}
    r, server = call("officer", "progress_case", args)  # flag alone is not enough without scope
    assert r.is_error and server.audit[-1]["reason"] == "approval_required"
    r, _ = call("manager", "progress_case", args)
    assert not r.is_error and data(r)["status"] == "enforcement"


def test_search_filters():
    r, _ = call("viewer", "search_cases", {"status": "compliance_review"})
    assert [c["id"] for c in (data(r) if isinstance(data(r), list) else [data(r)])] == ["CASE-2"]
