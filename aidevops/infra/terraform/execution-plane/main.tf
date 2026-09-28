# Execution plane -- deployed into the CUSTOMER's Azure subscription (ADR-0001).
#
# This is shipped software running in someone else's cloud. It gets the same review
# and release discipline as application code, and it must be safe to apply by a
# customer's own platform team reading it for the first time.
#
# Onboarding a tenant is one `terraform apply` of this root module. If it ever takes
# more than that, the Month 5 milestone ("a second tenant provisioned by someone who
# isn't you") is not reachable.

terraform {
  required_version = ">= 1.9"
  required_providers {
    azuread    = { source = "hashicorp/azuread", version = "~> 3.0" }
    azurerm    = { source = "hashicorp/azurerm", version = "~> 4.0" }
    databricks = { source = "databricks/databricks", version = "~> 1.50" }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "databricks" {
  host = var.databricks_host
}

locals {
  name_prefix = "adp-${var.tenant_id}-${var.environment}"

  # Grants mirror policy/agents.yaml. They are duplicated on purpose -- Terraform is
  # the real boundary and the YAML is the fast-failing one -- but they must agree.
  # CI diffs them; see .github/workflows/policy-parity.yml.
  agents = {
    data-engineering = {
      read_catalogs = ["bronze", "silver", "raw"]
      write_schemas = ["bronze.staging", "silver.curated"]
    }
    data-quality = {
      read_catalogs = ["bronze", "silver", "gold"]
      write_schemas = []
    }
    orchestrator = {
      read_catalogs = []
      write_schemas = []
    }
  }
}

resource "azurerm_resource_group" "execution_plane" {
  name     = "${local.name_prefix}-rg"
  location = var.location

  tags = {
    product     = "ai-devops-platform"
    plane       = "execution"
    tenant      = var.tenant_id
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Customer's own Key Vault. Agent secrets never leave this subscription.
resource "azurerm_key_vault" "agent_secrets" {
  name                       = substr(replace("${local.name_prefix}-kv", "-", ""), 0, 24)
  resource_group_name        = azurerm_resource_group.execution_plane.name
  location                   = azurerm_resource_group.execution_plane.location
  tenant_id                  = var.azure_tenant_id
  sku_name                   = "standard"
  purge_protection_enabled   = true
  soft_delete_retention_days = 90
  rbac_authorization_enabled = true

  # No public access. The runtime reaches it over a private endpoint.
  public_network_access_enabled = false

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
  }
}

# One identity per agent (ADR-0002 section 1).
module "agent_identity" {
  source   = "../modules/agent-identity"
  for_each = local.agents

  agent_type  = each.key
  tenant_id   = var.tenant_id
  environment = var.environment

  oidc_issuer_url   = var.oidc_issuer_url
  runtime_namespace = var.runtime_namespace

  read_catalogs = each.value.read_catalogs
  write_schemas = each.value.write_schemas
  key_vault_id  = azurerm_key_vault.agent_secrets.id
}

# Full traces stay here (ADR-0003 section 3). The customer can query them with
# tooling they already have -- which is also our answer to "how do we support you
# if you cannot see our payloads".
resource "azurerm_log_analytics_workspace" "traces" {
  name                = "${local.name_prefix}-traces"
  resource_group_name = azurerm_resource_group.execution_plane.name
  location            = azurerm_resource_group.execution_plane.location
  sku                 = "PerGB2018"
  retention_in_days   = var.trace_retention_days
}

# STUB -- Month 1. The agent runtime and MCP gateway container apps.
# Outbound-only egress to the control plane; no ingress from the internet at all.
# See ADR-0001: the runtime polls, we never call in.
#
# resource "azurerm_container_app" "agent_runtime" { ... }
# resource "azurerm_container_app" "mcp_gateway"  { ... }
