# Agent identity provisioning. Implements ADR-0002.
#
# One invocation of this module == one agent's identity in one tenant in one
# environment. Identity count grows as agents x tenants x environments, so this
# has to be fully automated -- manual creation does not survive the second customer.
#
# The security review reads this file. Keep it readable.

terraform {
  required_providers {
    azuread    = { source = "hashicorp/azuread", version = "~> 3.0" }
    azurerm    = { source = "hashicorp/azurerm", version = "~> 4.0" }
    databricks = { source = "databricks/databricks", version = "~> 1.50" }
  }
}

locals {
  # Must match AgentPrincipal.name in packages/adp-contracts/identity.py.
  # A mismatch here is silent: tokens are issued to a principal that has no grants,
  # and every tool call fails with a confusing 403.
  agent_name = "agent-${var.agent_type}-${var.tenant_id}-${var.environment}"
}

resource "azuread_application" "agent" {
  display_name = local.agent_name
  description  = "AI DevOps Platform ${var.agent_type} agent for ${var.tenant_id} (${var.environment}). Managed by Terraform - do not edit in the portal."

  # No password, no certificate. Federation only (ADR-0002 section 2).
  # There is deliberately no azuread_application_password resource in this module.
}

resource "azuread_service_principal" "agent" {
  client_id = azuread_application.agent.client_id

  feature_tags {
    enterprise = true
    hide       = true # not a user-facing app; keep it out of the app gallery
  }
}

# Workload identity federation: the runtime's Kubernetes service account exchanges
# its projected token for an Entra token for this principal. No secret exists to
# leak, rotate, or commit.
resource "azuread_application_federated_identity_credential" "agent" {
  application_id = azuread_application.agent.id
  display_name   = "${local.agent_name}-federation"
  description    = "Workload identity federation from the agent runtime"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = var.oidc_issuer_url
  subject        = "system:serviceaccount:${var.runtime_namespace}:${local.agent_name}"
}

# ---------------------------------------------------------------- Unity Catalog
#
# The real boundary. Even if the gateway policy engine were bypassed entirely,
# these grants are what an agent can actually touch.

resource "databricks_service_principal" "agent" {
  application_id = azuread_application.agent.client_id
  display_name   = local.agent_name

  # Explicitly denied. An agent that can create clusters can size its way around
  # the policy engine's worker cap, and an agent with SQL access can read data the
  # metadata-only tool surface is designed to keep out of traces (ADR-0003).
  allow_cluster_create  = false
  databricks_sql_access = false
  workspace_access      = true
}

resource "databricks_grants" "read_catalogs" {
  for_each = toset(var.read_catalogs)
  catalog  = each.value

  grant {
    principal  = databricks_service_principal.agent.application_id
    privileges = ["USE_CATALOG", "USE_SCHEMA", "SELECT"]
  }
}

resource "databricks_grants" "write_schemas" {
  for_each = toset(var.write_schemas)
  schema   = each.value

  grant {
    principal = databricks_service_principal.agent.application_id
    # MODIFY and CREATE_TABLE, but never MANAGE: an agent must not be able to
    # change the grants that constrain it.
    privileges = ["USE_SCHEMA", "SELECT", "MODIFY", "CREATE_TABLE"]
  }
}

# ------------------------------------------------------------------ Azure RBAC

resource "azurerm_role_assignment" "key_vault_secrets" {
  count = var.key_vault_id == null ? 0 : 1

  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User" # read-only; not Officer
  principal_id         = azuread_service_principal.agent.object_id
}
