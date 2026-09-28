"""Policy evaluation. Implements ADR-0002 section 3.

Design rule: **default deny**. Every path that does not explicitly allow must return
a denial, and the denial must carry a reason that is safe to show an agent and
useful to a human reading the audit log.

This engine is the fine-grained layer. It is not the security boundary -- Unity
Catalog grants and Azure RBAC are. Treat a bug here as a usability bug with security
significance, not as the only thing standing between an agent and production.
"""

from __future__ import annotations

import fnmatch
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from adp_contracts import AgentType, Environment, ToolDecision


@dataclass(frozen=True)
class PolicyResult:
    decision: ToolDecision
    reason: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision is ToolDecision.ALLOW


@dataclass
class _ToolRule:
    name: str
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class _AgentRule:
    description: str
    tools: dict[str, _ToolRule]
    rate_limit_per_hour: int


class PolicyEngine:
    """Evaluates whether an agent may make a specific tool call.

    Not thread-safe by design; one engine per gateway process, and the gateway is
    single-writer per run. If that changes, the rate-limit deques need a lock.
    """

    def __init__(self, policy_path: Path | str) -> None:
        self._path = Path(policy_path)
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))

        self._defaults: dict[str, Any] = raw.get("defaults", {})
        self._never_expose: set[str] = set(raw.get("never_expose", []))
        self._agents: dict[str, _AgentRule] = {}

        for agent_name, spec in (raw.get("agents") or {}).items():
            tools = {
                t["name"]: _ToolRule(name=t["name"], constraints=t.get("constraints") or {})
                for t in (spec.get("tools") or [])
            }
            self._agents[agent_name] = _AgentRule(
                description=spec.get("description", ""),
                tools=tools,
                rate_limit_per_hour=spec.get(
                    "rate_limit_per_hour", self._defaults.get("rate_limit_per_hour", 200)
                ),
            )

        # agent_principal -> timestamps of recent calls, for the sliding window
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    # ---------------------------------------------------------------- inspection

    def tools_for(self, agent_type: AgentType | str) -> list[str]:
        """Tool names this agent may call.

        Used to build the MCP tool list, so an agent never even sees a tool it
        cannot use. Unusable tools in the list waste context and invite retries.
        """
        rule = self._agents.get(str(agent_type))
        return sorted(rule.tools) if rule else []

    @property
    def never_expose(self) -> set[str]:
        return set(self._never_expose)

    # ---------------------------------------------------------------- evaluation

    def evaluate(
        self,
        *,
        agent_type: AgentType | str,
        agent_principal: str,
        environment: Environment | str,
        tool_name: str,
        arguments: dict[str, Any],
        user_can: bool = True,
        run_has_approval: bool = False,
    ) -> PolicyResult:
        """Authorise one tool call.

        `user_can` is the ADR-0002 section 4 intersection: the caller resolves
        whether the *invoking human* could perform this action, and we refuse if
        they could not, regardless of what the agent principal is permitted. This is
        what stops an agent becoming a privilege-escalation path.
        """
        agent_key = str(agent_type)
        env = str(environment)

        if tool_name in self._never_expose:
            return PolicyResult(
                ToolDecision.DENY_NOT_ALLOWLISTED,
                f"{tool_name} is on the never-expose list and is not implemented",
            )

        rule = self._agents.get(agent_key)
        if rule is None:
            return PolicyResult(
                ToolDecision.DENY_NOT_ALLOWLISTED,
                f"no policy entry for agent {agent_key!r}; default is deny",
            )

        tool = rule.tools.get(tool_name)
        if tool is None:
            return PolicyResult(
                ToolDecision.DENY_NOT_ALLOWLISTED,
                f"agent {agent_key!r} is not allowlisted for {tool_name!r}",
            )

        if not user_can:
            return PolicyResult(
                ToolDecision.DENY_USER_PERMISSION,
                "invoking user lacks permission for this action; an agent may not "
                "exceed the permissions of the human who invoked it",
            )

        if not self._within_rate_limit(agent_principal, rule.rate_limit_per_hour):
            return PolicyResult(
                ToolDecision.DENY_RATE_LIMIT,
                f"agent exceeded {rule.rate_limit_per_hour} tool calls/hour",
            )

        return self._check_constraints(
            tool=tool,
            environment=env,
            arguments=arguments,
            run_has_approval=run_has_approval,
        )

    # ---------------------------------------------------------------- internals

    def _within_rate_limit(self, principal: str, limit: int) -> bool:
        now = time.monotonic()
        window = self._calls[principal]
        cutoff = now - 3600
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        return True

    def _check_constraints(
        self,
        *,
        tool: _ToolRule,
        environment: str,
        arguments: dict[str, Any],
        run_has_approval: bool,
    ) -> PolicyResult:
        c = tool.constraints

        envs = c.get("environments")
        if envs and environment not in envs:
            return PolicyResult(
                ToolDecision.DENY_CONSTRAINT,
                f"{tool.name} is not permitted in {environment!r}",
            )

        if environment in (c.get("require_approval_in") or []) and not run_has_approval:
            return PolicyResult(
                ToolDecision.DENY_APPROVAL_REQUIRED,
                f"{tool.name} in {environment!r} requires an approved step in this run",
            )

        allowlist = c.get("catalog_allowlist")
        if allowlist:
            catalog = arguments.get("catalog")
            if catalog is not None and catalog not in allowlist:
                return PolicyResult(
                    ToolDecision.DENY_CONSTRAINT,
                    f"catalog {catalog!r} is not in the allowlist for {tool.name}",
                )

        pattern = c.get("target_schema_pattern")
        if pattern:
            target = arguments.get("target")
            if target is not None and not re.match(pattern, str(target)):
                return PolicyResult(
                    ToolDecision.DENY_CONSTRAINT,
                    f"target {target!r} does not match the permitted pattern for "
                    f"{tool.name}",
                )

        max_workers = c.get("max_cluster_workers")
        if max_workers is not None:
            workers = arguments.get("num_workers")
            if workers is not None and int(workers) > int(max_workers):
                return PolicyResult(
                    ToolDecision.DENY_CONSTRAINT,
                    f"requested {workers} workers, limit is {max_workers}",
                )

        prefix = c.get("branch_prefix")
        if prefix:
            branch = arguments.get("branch")
            if branch is not None and not str(branch).startswith(prefix):
                return PolicyResult(
                    ToolDecision.DENY_CONSTRAINT,
                    f"branch must start with {prefix!r}; agents may not write to "
                    f"arbitrary branches",
                )

        denied = c.get("protected_branches_denied")
        if denied:
            # A PR *targeting* main is the whole point; an agent *writing to* main
            # is not. Only the source branch is checked here.
            branch = arguments.get("branch")
            if branch is not None and any(
                fnmatch.fnmatch(str(branch), pat) for pat in denied
            ):
                return PolicyResult(
                    ToolDecision.DENY_CONSTRAINT,
                    f"{branch!r} is a protected branch; agents open pull requests, "
                    f"humans merge them",
                )

        max_files = c.get("max_files_changed")
        if max_files is not None:
            files = arguments.get("files")
            if files is not None and len(files) > int(max_files):
                return PolicyResult(
                    ToolDecision.DENY_CONSTRAINT,
                    f"{len(files)} files changed, limit is {max_files}; split the "
                    f"change into smaller pull requests",
                )

        return PolicyResult(ToolDecision.ALLOW)
