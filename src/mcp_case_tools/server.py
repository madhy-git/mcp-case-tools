"""MCP server exposing case-management capabilities to AI assistants.

Least-privilege scopes per role, state-transition rules, human-approval for
high-impact transitions, and an audit trail of every call (allowed or denied).
"""
from __future__ import annotations

import os
import time

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

ROLE_SCOPES = {
    "viewer": {"case:read"},
    "officer": {"case:read", "case:write"},
    "manager": {"case:read", "case:write", "case:approve"},
}
# Allowed workflow transitions; enforcement needs a manager's approval flag.
TRANSITIONS = {
    "new": {"assessment"},
    "assessment": {"compliance_review", "closed"},
    "compliance_review": {"enforcement", "closed"},
    "enforcement": {"closed"},
}
NEEDS_APPROVAL = {"enforcement"}


def _seed() -> dict[str, dict]:
    return {
        "CASE-1": {"provider": "Sunrise Care", "status": "new", "notes": []},
        "CASE-2": {"provider": "Harbour Aged Care", "status": "compliance_review", "notes": ["Complaint received"]},
        "CASE-3": {"provider": "Maple Lodge", "status": "assessment", "notes": []},
    }


def create_server(role: str | None = None) -> MCPServer:
    role = role or os.getenv("MCP_ROLE", "viewer")
    scopes = ROLE_SCOPES[role]
    cases = _seed()
    audit: list[dict] = []
    server = MCPServer("case-tools")

    def log(tool: str, allowed: bool, **data):
        audit.append({"ts": time.time(), "role": role, "tool": tool, "allowed": allowed, **data})

    def require(scope: str, tool: str, **data):
        if scope not in scopes:
            log(tool, False, missing_scope=scope, **data)
            raise ToolError(f"role '{role}' lacks scope '{scope}'")

    @server.tool()
    def get_case(case_id: str) -> dict:
        """Fetch a case by id."""
        require("case:read", "get_case", case_id=case_id)
        if case_id not in cases:
            raise ToolError(f"unknown case {case_id}")
        log("get_case", True, case_id=case_id)
        return {"id": case_id, **cases[case_id]}

    @server.tool()
    def search_cases(status: str | None = None, provider_contains: str | None = None) -> list[dict]:
        """List cases, optionally filtered by status or provider name."""
        require("case:read", "search_cases")
        out = [
            {"id": i, **c}
            for i, c in cases.items()
            if (status is None or c["status"] == status)
            and (provider_contains is None or provider_contains.lower() in c["provider"].lower())
        ]
        log("search_cases", True, status=status, count=len(out))
        return out

    @server.tool()
    def add_note(case_id: str, note: str) -> dict:
        """Append a note to a case (officer or manager)."""
        require("case:write", "add_note", case_id=case_id)
        cases[case_id]["notes"].append(note)
        log("add_note", True, case_id=case_id)
        return {"id": case_id, "notes": len(cases[case_id]["notes"])}

    @server.tool()
    def progress_case(case_id: str, new_status: str, approved_by_manager: bool = False) -> dict:
        """Move a case to the next workflow state. Enforcement requires manager approval."""
        require("case:write", "progress_case", case_id=case_id, to=new_status)
        cur = cases[case_id]["status"]
        if new_status not in TRANSITIONS.get(cur, set()):
            log("progress_case", False, case_id=case_id, reason="invalid_transition", frm=cur, to=new_status)
            raise ToolError(f"invalid transition {cur} -> {new_status}")
        if new_status in NEEDS_APPROVAL:
            if not (approved_by_manager and "case:approve" in scopes):
                log("progress_case", False, case_id=case_id, reason="approval_required", to=new_status)
                raise ToolError("enforcement requires manager approval")
        cases[case_id]["status"] = new_status
        log("progress_case", True, case_id=case_id, frm=cur, to=new_status)
        return {"id": case_id, "status": new_status}

    @server.resource("audit://log")
    def audit_log() -> str:
        """Audit trail of every tool call, allowed or denied."""
        import json

        return json.dumps(audit)

    server.audit = audit  # exposed for tests
    return server


if __name__ == "__main__":
    create_server().run()
