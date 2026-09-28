"""Read an existing bundle repository and count what is actually there.

Deterministic on purpose. The temptation is to hand the whole repository to the
model and ask "what are their conventions" -- which produces a confident answer
that may or may not describe the repository. Counting first means every
convention we later write down is traceable to a number, and a claim the model
makes that the facts do not support is visible as a claim the facts do not
support.

It is also cheap. A repository with four hundred job files becomes a page of
counts, which fits in a prompt; the repository does not.

The scan doubles as a small audit. `hardcoded_catalogs` and `unpaused_schedules`
are places the repository violates its own conventions, and those are worth
handing back to the customer in week one regardless of what the agent does with
them.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

log = structlog.get_logger(__name__)

#: ${var.name} and ${bundle.name} references.
_VAR_RE = re.compile(r"\$\{(var|bundle|workspace|resources)\.([a-zA-Z0-9_.]+)\}")

#: A catalog.schema.table written literally where a variable belongs.
_QUALIFIED_RE = re.compile(r"\b([a-z][a-z0-9_]{2,})\.([a-z][a-z0-9_]+)\.([a-z][a-z0-9_]+)\b")

#: Sampled rather than exhaustive: the model needs the shape of a naming
#: convention, not four hundred instances of it.
_SAMPLE_LIMIT = 25

#: CI/CD definitions live beside the bundle but are not part of it. Counting
#: them adds phantom "resource files with 0 jobs" and drags their contents --
#: install URLs, shell snippets -- into the findings.
_NOT_BUNDLE_FILES = frozenset(
    {
        "azure-pipelines.yml",
        "azure-pipelines.yaml",
        ".gitlab-ci.yml",
        "docker-compose.yml",
        "docker-compose.yaml",
    }
)

#: Enough to recognise a hostname. A three-part lowercase dotted name is a
#: perfectly good catalog reference and also a perfectly good domain, so the
#: last segment decides.
_TLDS = frozenset(
    {"com", "org", "net", "io", "dev", "ai", "co", "gov", "edu", "sh", "cloud"}
)


@dataclass
class RepoFacts:
    """What the repository demonstrably contains."""

    bundle_name: str | None = None
    targets: list[str] = field(default_factory=list)
    declared_variables: list[str] = field(default_factory=list)

    resource_files: int = 0
    jobs_total: int = 0
    pipelines_total: int = 0
    jobs_per_file: Counter = field(default_factory=Counter)

    job_name_samples: list[str] = field(default_factory=list)
    resource_key_samples: list[str] = field(default_factory=list)
    file_name_samples: list[str] = field(default_factory=list)
    task_key_samples: list[str] = field(default_factory=list)

    variables_used: Counter = field(default_factory=Counter)
    job_fields: Counter = field(default_factory=Counter)
    tag_keys: Counter = field(default_factory=Counter)

    schedules: int = 0
    unpaused_schedules: int = 0

    source_files: int = 0
    source_imports: Counter = field(default_factory=Counter)
    explicit_schema_reads: int = 0
    inferred_schema_reads: int = 0

    #: Audit findings, not conventions. Somewhere the repo contradicts itself.
    hardcoded_catalogs: list[str] = field(default_factory=list)

    errors: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return self.resource_files == 0 and self.source_files == 0

    def summary(self) -> str:
        """The fact sheet handed to the model. Counts, not code.

        Deliberately excludes file contents. What crosses into a prompt -- and
        from there into the registry -- is the shape of their conventions, never
        their pipelines. A convention is ours to describe; their code is theirs.
        """
        lines: list[str] = []
        add = lines.append

        add(f"Bundle name: {self.bundle_name or 'not declared'}")
        add(f"Targets: {', '.join(self.targets) or 'none'}")
        add(f"Declared variables: {', '.join(self.declared_variables) or 'none'}")
        add("")
        add(f"Resource files: {self.resource_files}")
        add(f"Jobs: {self.jobs_total}   Pipelines: {self.pipelines_total}")
        if self.jobs_per_file:
            dist = ", ".join(
                f"{n} job(s) in {count} file(s)"
                for n, count in sorted(self.jobs_per_file.items())
            )
            add(f"Jobs per file: {dist}")
        add("")

        if self.file_name_samples:
            add("Resource file names (sample):")
            for name in self.file_name_samples:
                add(f"  {name}")
            add("")

        if self.resource_key_samples:
            add("Resource keys (sample):")
            for key in self.resource_key_samples:
                add(f"  {key}")
            add("")

        if self.job_name_samples:
            add("Job display names (sample):")
            for name in self.job_name_samples:
                add(f"  {name}")
            add("")

        if self.task_key_samples:
            add(f"Task keys (sample): {', '.join(self.task_key_samples)}")
            add("")

        if self.variables_used:
            add("Variable references, by frequency:")
            for name, count in self.variables_used.most_common(20):
                add(f"  {name}  x{count}")
            add("")

        if self.job_fields:
            add("Job-level fields, by how many jobs use them:")
            for name, count in self.job_fields.most_common(20):
                add(f"  {name}  {count}/{self.jobs_total}")
            add("")

        if self.tag_keys:
            add("Tag keys: " + ", ".join(f"{k} x{v}" for k, v in self.tag_keys.most_common()))
            add("")

        add(f"Scheduled jobs: {self.schedules} ({self.unpaused_schedules} deploy unpaused)")
        add("")

        add(f"Source files: {self.source_files}")
        if self.source_imports:
            add("Imports, by frequency:")
            for name, count in self.source_imports.most_common(15):
                add(f"  {name}  x{count}")
        add(
            f"Reads with an explicit schema: {self.explicit_schema_reads}; "
            f"relying on inference: {self.inferred_schema_reads}"
        )

        if self.hardcoded_catalogs:
            add("")
            add("Literal catalog.schema.table references found where a variable")
            add("would be expected (sample):")
            for ref in self.hardcoded_catalogs[:15]:
                add(f"  {ref}")

        return "\n".join(lines)


def _sample(target: list[str], value: Any) -> None:
    if isinstance(value, str) and value and len(target) < _SAMPLE_LIMIT:
        target.append(value)


def _collect_variables(node: Any, facts: RepoFacts) -> None:
    """Walk a parsed YAML tree counting ${...} references and literal targets."""
    if isinstance(node, dict):
        for value in node.values():
            _collect_variables(value, facts)
    elif isinstance(node, list):
        for item in node:
            _collect_variables(item, facts)
    elif isinstance(node, str):
        for namespace, name in _VAR_RE.findall(node):
            facts.variables_used[f"{namespace}.{name}"] += 1

        # A literal three-part name that is not inside a ${...} is a catalog
        # someone hard-coded. Skip anything already carrying a variable: a
        # string like "${var.catalog}.curated.orders" is correct, not a finding.
        if "${" in node or "://" in node:
            return
        for match in _QUALIFIED_RE.finditer(node):
            ref = match.group(0)
            # raw.githubusercontent.com is a hostname, not a catalog. The
            # pattern cannot tell them apart; the last segment can.
            if match.group(3) in _TLDS:
                continue
            if ref not in facts.hardcoded_catalogs:
                facts.hardcoded_catalogs.append(ref)


def _scan_root(path: Path, facts: RepoFacts) -> None:
    try:
        root = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        facts.errors.append(f"{path.name}: {exc}")
        return

    facts.bundle_name = (root.get("bundle") or {}).get("name")
    facts.targets = sorted((root.get("targets") or {}).keys())
    facts.declared_variables = sorted((root.get("variables") or {}).keys())


def _scan_resource_file(path: Path, facts: RepoFacts) -> None:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        facts.errors.append(f"{path.name}: {exc}")
        return

    facts.resource_files += 1
    _sample(facts.file_name_samples, path.name)
    _collect_variables(doc, facts)

    resources = doc.get("resources") or {}
    jobs = resources.get("jobs") or {}
    facts.pipelines_total += len(resources.get("pipelines") or {})
    facts.jobs_total += len(jobs)
    facts.jobs_per_file[len(jobs)] += 1

    for key, job in jobs.items():
        _sample(facts.resource_key_samples, key)
        if not isinstance(job, dict):
            continue

        _sample(facts.job_name_samples, job.get("name"))
        for field_name in job:
            facts.job_fields[field_name] += 1

        for tag in (job.get("tags") or {}):
            facts.tag_keys[tag] += 1

        for task in job.get("tasks") or []:
            if isinstance(task, dict):
                _sample(facts.task_key_samples, task.get("task_key"))

        schedule = job.get("schedule")
        if isinstance(schedule, dict):
            facts.schedules += 1
            if schedule.get("pause_status") != "PAUSED":
                facts.unpaused_schedules += 1


def _scan_source_file(path: Path, facts: RepoFacts) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        facts.errors.append(f"{path.name}: {exc}")
        return

    facts.source_files += 1

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            parts = stripped.split()
            if len(parts) >= 2:
                facts.source_imports[parts[1].split(".")[0]] += 1

    # Crude but honest: a read carrying a schema argument versus one that does
    # not. Schema inference in a scheduled job is how a pipeline silently
    # changes shape when a source adds a column, so the ratio is worth knowing.
    facts.explicit_schema_reads += len(re.findall(r"\.schema\s*\(", text))
    facts.explicit_schema_reads += len(re.findall(r"schema\s*=", text))
    facts.inferred_schema_reads += len(re.findall(r"inferSchema", text))


def scan_bundle_repo(root: Path) -> RepoFacts:
    """Scan a Databricks Asset Bundle repository.

    Tolerant of a layout that is not ours: resource files are found anywhere,
    not only under `resources/`. A customer who has been running bundles for two
    years has their own arrangement, and refusing to read it would defeat the
    point of extracting their conventions.
    """
    facts = RepoFacts()
    root = Path(root)

    if not root.exists():
        facts.errors.append(f"{root} does not exist")
        return facts

    for name in ("databricks.yml", "databricks.yaml"):
        candidate = root / name
        if candidate.exists():
            _scan_root(candidate, facts)
            break
    else:
        facts.errors.append("no databricks.yml found at the repository root")

    for path in sorted(root.rglob("*.y*ml")):
        if path.name in ("databricks.yml", "databricks.yaml"):
            continue
        if path.name in _NOT_BUNDLE_FILES:
            continue
        # Pipeline definitions are the platform team's, not the agent's, and
        # they would skew every count.
        if any(part in (".azure", ".github", ".git") for part in path.parts):
            continue
        _scan_resource_file(path, facts)

    for path in sorted(root.rglob("*.py")):
        if any(part in (".git", "tests", "__pycache__") for part in path.parts):
            continue
        _scan_source_file(path, facts)

    log.info(
        "bundle_repo_scanned",
        root=str(root),
        resource_files=facts.resource_files,
        jobs=facts.jobs_total,
        source_files=facts.source_files,
        hardcoded_catalogs=len(facts.hardcoded_catalogs),
    )
    return facts
