"""Registry extractor tests.

The scanner is deterministic, so these assert exact counts against a synthetic
repository rather than approximating.

`test_summary_carries_no_file_contents` is the one to keep. The fact sheet goes
into a prompt and from there into the registry, and the line it holds is that we
describe the shape of a customer's conventions but never carry their code.
"""

from __future__ import annotations

from pathlib import Path

from agent_runtime.registry.conventions import (
    Convention,
    ConventionSet,
    render_registry_assets,
)
from agent_runtime.registry.scanner import scan_bundle_repo

SECRET = "PROPRIETARY_JOIN_LOGIC_THEY_WOULD_NOT_WANT_SHARED"

ROOT_YML = """\
bundle:
  name: acme-platform
variables:
  catalog:
    default: bronze
  spark_version:
    default: "15.4.x-scala2.12"
targets:
  dev:
    mode: development
  prod:
    mode: production
"""

GOOD_JOB = """\
resources:
  jobs:
    silver_sales_orders:
      name: "[${bundle.target}] Silver - sales_orders"
      tags:
        layer: silver
        owner: data-eng
      max_concurrent_runs: 1
      tasks:
        - task_key: transform
          spark_python_task:
            python_file: ../source/sales_orders.py
            parameters:
              - ${var.catalog}.curated.sales_orders
      schedule:
        quartz_cron_expression: "0 0 6 * * ?"
        pause_status: PAUSED
"""

SLOPPY_JOB = """\
resources:
  jobs:
    silver_returns:
      name: "[${bundle.target}] Silver - returns"
      tags:
        layer: silver
      tasks:
        - task_key: transform
          spark_python_task:
            python_file: ../source/returns.py
            parameters:
              - gold.finance.returns_fact
      schedule:
        quartz_cron_expression: "0 0 7 * * ?"
"""

CI_YML = """\
steps:
  - script: |
      curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/install.sh | sh
"""

SOURCE_PY = f"""\
from pyspark.sql import functions as F
from pyspark.sql.types import StructType

def transform(spark, catalog):
    schema = StructType([])
    df = spark.read.schema(schema).table(f"{{catalog}}.raw.orders")
    # {SECRET}
    return df.filter(F.col("amount") > 0)
"""


def _make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "their-repo"
    (root / "resources").mkdir(parents=True)
    (root / "source").mkdir()

    (root / "databricks.yml").write_text(ROOT_YML, encoding="utf-8")
    (root / "resources" / "silver_sales_orders.yml").write_text(GOOD_JOB, encoding="utf-8")
    (root / "resources" / "silver_returns.yml").write_text(SLOPPY_JOB, encoding="utf-8")
    (root / "azure-pipelines.yml").write_text(CI_YML, encoding="utf-8")
    (root / "source" / "sales_orders.py").write_text(SOURCE_PY, encoding="utf-8")
    return root


# ---------------------------------------------------------------- the privacy line

def test_summary_carries_no_file_contents(tmp_path: Path) -> None:
    """The fact sheet describes shape, never code.

    It goes into a prompt and from there into the registry. A convention is ours
    to describe; their pipelines are theirs.
    """
    facts = scan_bundle_repo(_make_repo(tmp_path))
    summary = facts.summary()

    assert SECRET not in summary
    assert "StructType" not in summary
    assert "def transform" not in summary
    assert "quartz_cron_expression" not in summary


# --------------------------------------------------------------------- counts

def test_scans_root_configuration(tmp_path: Path) -> None:
    facts = scan_bundle_repo(_make_repo(tmp_path))

    assert facts.bundle_name == "acme-platform"
    assert facts.targets == ["dev", "prod"]
    assert facts.declared_variables == ["catalog", "spark_version"]


def test_counts_jobs_and_files(tmp_path: Path) -> None:
    facts = scan_bundle_repo(_make_repo(tmp_path))

    assert facts.resource_files == 2
    assert facts.jobs_total == 2
    assert facts.jobs_per_file[1] == 2


def test_samples_names_for_pattern_inference(tmp_path: Path) -> None:
    facts = scan_bundle_repo(_make_repo(tmp_path))

    assert "silver_sales_orders" in facts.resource_key_samples
    assert any("Silver - sales_orders" in n for n in facts.job_name_samples)
    assert "transform" in facts.task_key_samples


def test_counts_variable_usage(tmp_path: Path) -> None:
    facts = scan_bundle_repo(_make_repo(tmp_path))

    assert facts.variables_used["var.catalog"] == 1
    assert facts.variables_used["bundle.target"] == 2


def test_counts_job_fields_and_tags(tmp_path: Path) -> None:
    """How many jobs carry a field is what separates a convention from a habit."""
    facts = scan_bundle_repo(_make_repo(tmp_path))

    assert facts.job_fields["tags"] == 2
    assert facts.job_fields["max_concurrent_runs"] == 1
    assert facts.tag_keys["layer"] == 2
    assert facts.tag_keys["owner"] == 1


def test_counts_source_patterns(tmp_path: Path) -> None:
    facts = scan_bundle_repo(_make_repo(tmp_path))

    assert facts.source_files == 1
    assert facts.source_imports["pyspark"] == 2
    assert facts.explicit_schema_reads >= 1


# ------------------------------------------------------------------- findings

def test_flags_a_hardcoded_catalog(tmp_path: Path) -> None:
    """A literal catalog.schema.table where a variable belongs. This is the
    finding worth handing back in week one."""
    facts = scan_bundle_repo(_make_repo(tmp_path))
    assert "gold.finance.returns_fact" in facts.hardcoded_catalogs


def test_does_not_flag_a_variable_reference(tmp_path: Path) -> None:
    facts = scan_bundle_repo(_make_repo(tmp_path))
    assert not any("sales_orders" in ref for ref in facts.hardcoded_catalogs)


def test_does_not_flag_a_hostname(tmp_path: Path) -> None:
    """raw.githubusercontent.com matches the catalog pattern exactly. The last
    segment is what tells them apart."""
    facts = scan_bundle_repo(_make_repo(tmp_path))
    assert not any("github" in ref for ref in facts.hardcoded_catalogs)


def test_flags_an_unpaused_schedule(tmp_path: Path) -> None:
    """A scheduled job that deploys running is how a bad pipeline runs forty
    times overnight."""
    facts = scan_bundle_repo(_make_repo(tmp_path))

    assert facts.schedules == 2
    assert facts.unpaused_schedules == 1


# ------------------------------------------------------------ not-bundle files

def test_ci_definitions_are_not_counted_as_resources(tmp_path: Path) -> None:
    """azure-pipelines.yml sits beside the bundle and is not part of it.
    Counting it added a phantom resource file with zero jobs."""
    facts = scan_bundle_repo(_make_repo(tmp_path))

    assert facts.resource_files == 2
    assert "azure-pipelines.yml" not in facts.file_name_samples
    assert facts.jobs_per_file[0] == 0


# -------------------------------------------------------------- empty / broken

def test_missing_repository_is_reported_not_raised(tmp_path: Path) -> None:
    facts = scan_bundle_repo(tmp_path / "nope")
    assert facts.is_empty
    assert any("does not exist" in e for e in facts.errors)


def test_missing_root_config_is_reported(tmp_path: Path) -> None:
    root = tmp_path / "partial"
    (root / "resources").mkdir(parents=True)
    (root / "resources" / "j.yml").write_text(GOOD_JOB, encoding="utf-8")

    facts = scan_bundle_repo(root)
    assert any("no databricks.yml" in e for e in facts.errors)
    assert facts.jobs_total == 1


def test_malformed_yaml_is_reported_not_fatal(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    (root / "resources" / "broken.yml").write_text("{{{ not yaml", encoding="utf-8")

    facts = scan_bundle_repo(root)
    assert any("broken.yml" in e for e in facts.errors)
    # The good files are still counted: one bad file must not lose the scan.
    assert facts.jobs_total == 2


# ------------------------------------------------------------ registry assets

def _conventions() -> ConventionSet:
    rule = Convention(
        rule="Name resource files after the target table.",
        evidence="2 of 2 files",
        confidence="observed",
    )
    return ConventionSet(
        naming=[rule],
        structure=[rule],
        variables=[],
        code_style=[],
        inconsistencies=["gold.finance.returns_fact is hard-coded"],
        prompt_block="Name resource files after the target table.",
    )


def test_registry_assets_are_one_per_category() -> None:
    """One asset per rule would make a registry nobody browses."""
    assets = render_registry_assets(_conventions())
    names = {a["name"] for a in assets}

    assert "conventions/naming" in names
    assert "conventions/structure" in names
    assert "conventions/agent-prompt" in names
    # Empty categories produce no asset rather than an empty one.
    assert "conventions/variables" not in names


def test_registry_assets_are_filed_as_prompts() -> None:
    """They condition a model; they are not pipeline templates. Filing them as
    templates would make a template search return prose."""
    assets = render_registry_assets(_conventions())
    assert {a["kind"] for a in assets} == {"prompt"}


def test_inconsistencies_never_reach_the_agent_prompt() -> None:
    """Teaching an agent to hard-code catalogs because thirty files do would be
    learning the wrong lesson precisely."""
    assets = render_registry_assets(_conventions())
    prompt = next(a for a in assets if a["name"] == "conventions/agent-prompt")

    assert "hard-coded" not in prompt["body"]
    assert "gold.finance.returns_fact" not in prompt["body"]
