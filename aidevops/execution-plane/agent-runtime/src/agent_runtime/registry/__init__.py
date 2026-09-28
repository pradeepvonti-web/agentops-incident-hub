"""Reusable Asset Registry: extracting and applying enterprise conventions.

Generic bundle knowledge comes free from the official Databricks skills
(ADR-0004). What makes an agent's output acceptable on first read is that it
looks like *this customer's* repository -- their naming, their file splits,
their variable habits. That is what this package extracts, and it is the part
that compounds.
"""

from agent_runtime.registry.conventions import (
    Convention,
    ConventionSet,
    extract_conventions,
    render_registry_assets,
)
from agent_runtime.registry.scanner import RepoFacts, scan_bundle_repo

__all__ = [
    "Convention",
    "ConventionSet",
    "RepoFacts",
    "extract_conventions",
    "render_registry_assets",
    "scan_bundle_repo",
]
