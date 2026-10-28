# MCP Case Tools

An MCP (Model Context Protocol) server that exposes case-management and workflow capabilities to AI assistants, with the controls a regulated environment expects: least-privilege scopes, enforced workflow transitions, human approval for high-impact steps, and an audit trail of every call.

## Tools

| Tool | Scope | Behaviour |
|---|---|---|
| `get_case` | `case:read` | Fetch a case |
| `search_cases` | `case:read` | Filter by status or provider |
| `add_note` | `case:write` | Append a note |
| `progress_case` | `case:write` (+ `case:approve` for enforcement) | Moves a case along `new -> assessment -> compliance_review -> enforcement -> closed`; invalid transitions are rejected |

Resource: `audit://log` returns every call, allowed or denied, with role, tool and reason.

## Roles

`viewer` (read), `officer` (read, write), `manager` (read, write, approve). Set with `MCP_ROLE`; default is `viewer`.

## Run

```bash
pip install -e ".[dev]"
pytest -q                          # 5 tests, in-memory MCP client
MCP_ROLE=officer python -m mcp_case_tools.server   # stdio server
```

MCP client config (e.g. Claude Desktop):

```json
{ "mcpServers": { "case-tools": { "command": "python", "args": ["-m", "mcp_case_tools.server"], "env": { "MCP_ROLE": "officer" } } } }
```

## Scope

Data is in-memory seed data and the role comes from an environment variable. A production deployment would back this with a real case store and take identity from OAuth/OIDC claims on the transport.
