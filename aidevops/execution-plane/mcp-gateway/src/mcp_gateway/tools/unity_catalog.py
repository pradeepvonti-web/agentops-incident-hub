"""Unity Catalog metadata tools -- the agent's read path into the lakehouse.

These two are read-only and are the only way an agent learns what exists. They
return *metadata*, never data: column names, types, comments, row counts. An agent
that needs to see values must go through a job submission whose output is reviewed,
not read rows through a tool.

That distinction is load-bearing. A metadata-only read path means the trace of a
planning step contains no customer data, which is what lets ADR-0003 keep payloads
in-tenant without the agent's reasoning becoming unauditable.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from mcp_gateway.tools.base import Tool, ToolContext, ToolError

log = structlog.get_logger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def _uc_get(ctx: ToolContext, path: str, params: dict[str, Any]) -> dict[str, Any]:
    """One authenticated Unity Catalog call, as the agent principal.

    The token is the agent's own (ADR-0002 section 1), so Unity Catalog's own grants
    are the real boundary -- if the policy engine were bypassed entirely, UC would
    still refuse a catalog the agent has no grant on.
    """
    url = f"{ctx.databricks_host.rstrip('/')}/api/2.1/unity-catalog/{path}"
    headers = {"Authorization": f"Bearer {ctx.access_token}"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, headers=headers, params=params)
    except httpx.TimeoutException as exc:
        raise ToolError(
            f"Unity Catalog did not respond within {_TIMEOUT.read}s",
            error_class="uc_timeout",
            retryable=True,
        ) from exc
    except httpx.HTTPError as exc:
        raise ToolError(
            "could not reach Unity Catalog",
            error_class="uc_unreachable",
            retryable=True,
        ) from exc

    if response.status_code == 403:
        # Surfaced to the agent as a permission problem it cannot retry its way out
        # of. The agent should report this to the human, not loop.
        raise ToolError(
            "the agent principal does not have a Unity Catalog grant for this object",
            error_class="uc_forbidden",
            retryable=False,
        )
    if response.status_code == 404:
        raise ToolError(
            "no such catalog, schema or table",
            error_class="uc_not_found",
            retryable=False,
        )
    if response.status_code >= 500:
        raise ToolError(
            "Unity Catalog returned a server error",
            error_class="uc_server_error",
            retryable=True,
        )
    if response.status_code >= 400:
        raise ToolError(
            f"Unity Catalog rejected the request ({response.status_code})",
            error_class="uc_bad_request",
            retryable=False,
        )

    return response.json()


async def uc_list_tables(
    ctx: ToolContext, *, catalog: str, schema: str, max_results: int = 200
) -> dict[str, Any]:
    """List tables in a schema. Metadata only."""
    log.info(
        "uc_list_tables",
        run_id=ctx.run_id,
        agent_principal=ctx.principal.agent.name,
        catalog=catalog,
        schema=schema,
    )

    payload = await _uc_get(
        ctx,
        "tables",
        {
            "catalog_name": catalog,
            "schema_name": schema,
            "max_results": min(max_results, 500),
            "omit_columns": "true",
        },
    )

    tables = payload.get("tables", [])
    return {
        "catalog": catalog,
        "schema": schema,
        "table_count": len(tables),
        "tables": [
            {
                "name": t.get("name"),
                "full_name": t.get("full_name"),
                "table_type": t.get("table_type"),
                "data_source_format": t.get("data_source_format"),
                "comment": t.get("comment"),
                "updated_at": t.get("updated_at"),
            }
            for t in tables
        ],
    }


async def uc_get_table_metadata(
    ctx: ToolContext, *, catalog: str, schema: str, table: str
) -> dict[str, Any]:
    """Column-level metadata for one table. Still no data values."""
    full_name = f"{catalog}.{schema}.{table}"
    log.info(
        "uc_get_table_metadata",
        run_id=ctx.run_id,
        agent_principal=ctx.principal.agent.name,
        table=full_name,
    )

    payload = await _uc_get(ctx, f"tables/{full_name}", {})

    return {
        "full_name": payload.get("full_name"),
        "table_type": payload.get("table_type"),
        "data_source_format": payload.get("data_source_format"),
        "comment": payload.get("comment"),
        "storage_location": payload.get("storage_location"),
        "columns": [
            {
                "name": c.get("name"),
                "type_text": c.get("type_text"),
                "nullable": c.get("nullable"),
                "comment": c.get("comment"),
                "partition_index": c.get("partition_index"),
            }
            for c in payload.get("columns", [])
        ],
        "properties": {
            # Row counts and sizes help the agent size a cluster. Deliberately a
            # narrow allowlist rather than passing the whole property bag through,
            # which can contain customer-meaningful strings.
            k: v
            for k, v in (payload.get("properties") or {}).items()
            if k in {"delta.lastCommitTimestamp", "numFiles", "sizeInBytes", "numRows"}
        },
    }


UC_LIST_TABLES = Tool(
    name="uc_list_tables",
    description=(
        "List the tables in a Unity Catalog schema. Returns names, types and "
        "comments -- metadata only, never row data. Use this to discover what "
        "exists before planning a pipeline."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "catalog": {"type": "string", "description": "Unity Catalog catalog name"},
            "schema": {"type": "string", "description": "Schema within the catalog"},
            "max_results": {
                "type": "integer",
                "description": "Maximum tables to return (capped at 500)",
                "default": 200,
            },
        },
        "required": ["catalog", "schema"],
    },
    handler=uc_list_tables,
    mutating=False,
)

UC_GET_TABLE_METADATA = Tool(
    name="uc_get_table_metadata",
    description=(
        "Get column-level metadata for one Unity Catalog table: column names, "
        "types, nullability, comments, partitioning and size. Metadata only, never "
        "row data. Use this before writing a transformation against a table."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "catalog": {"type": "string"},
            "schema": {"type": "string"},
            "table": {"type": "string"},
        },
        "required": ["catalog", "schema", "table"],
    },
    handler=uc_get_table_metadata,
    mutating=False,
)
