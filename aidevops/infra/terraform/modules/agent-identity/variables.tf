variable "agent_type" {
  type        = string
  description = "Agent type. Must match AgentType in adp_contracts.identity."

  validation {
    # Mirrors the three-agent cap in ADR-0002. Adding a fourth is a product
    # decision with identity, policy and evaluation cost -- not a Terraform edit.
    condition     = contains(["data-engineering", "data-quality", "orchestrator"], var.agent_type)
    error_message = "agent_type must be one of: data-engineering, data-quality, orchestrator."
  }
}

variable "tenant_id" {
  type        = string
  description = "Customer tenant slug. Must match the control plane's tenant_id."

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$", var.tenant_id))
    error_message = "tenant_id must be a lowercase slug of 3-40 characters."
  }
}

variable "environment" {
  type        = string
  description = "dev, test or prod. Each gets its own principal."

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment must be dev, test or prod."
  }
}

variable "oidc_issuer_url" {
  type        = string
  description = "OIDC issuer of the cluster running the agent runtime."
}

variable "runtime_namespace" {
  type        = string
  description = "Kubernetes namespace of the agent runtime."
  default     = "adp-runtime"
}

variable "read_catalogs" {
  type        = list(string)
  description = "Unity Catalog catalogs this agent may read. Keep this tight; it is the real boundary, and it should match the catalog_allowlist in policy/agents.yaml."
  default     = []
}

variable "write_schemas" {
  type        = list(string)
  description = "Schemas this agent may write, as catalog.schema. Never include gold for a data-engineering agent."
  default     = []
}

variable "key_vault_id" {
  type        = string
  description = "Key Vault the agent may read secrets from. Null for no access."
  default     = null
}
