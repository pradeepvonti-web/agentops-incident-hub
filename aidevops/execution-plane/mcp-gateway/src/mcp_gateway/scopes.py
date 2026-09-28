"""Entra token scopes the gateway acquires on an agent's behalf.

These are first-party Microsoft application ids and are the same in every Entra
tenant. They are constants, not configuration -- a scope that varies per customer
would mean the agent was talking to something other than what we think.

Each scope is a separate token with its own lifetime. A tool asks for the one it
needs and nothing else, so a compromised Databricks token is not also a
source-control token.
"""

from __future__ import annotations

from typing import Final

DATABRICKS: Final = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default"
"""Azure Databricks. Used by the Unity Catalog, jobs and bundle tools."""

AZURE_DEVOPS: Final = "499b84ac-1321-427f-aa17-267ca6975798/.default"
"""Azure DevOps. Used only by `git_open_pull_request`.

The agent principal needs `Contribute` and `Create pull request` on the target
repository and nothing else. It must NOT hold `Bypass policies when pushing`,
`Bypass policies when completing pull requests`, or `Contribute to pull requests
of others` -- any of those would let it route around the branch policy that makes
a human reviewer mandatory (ADR-0002 Amendment 1).
"""
