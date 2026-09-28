variable "tenant_id" {
  type        = string
  description = "Customer tenant slug, matching the control plane."
}

variable "environment" {
  type        = string
  description = "dev, test or prod."

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment must be dev, test or prod."
  }
}

variable "subscription_id" {
  type        = string
  description = "Customer's Azure subscription id. Their cloud, not ours."
}

variable "azure_tenant_id" {
  type        = string
  description = "Customer's Entra tenant id."
}

variable "location" {
  type        = string
  description = "Azure region. Customer's choice -- this is where their data stays."
  default     = "westeurope"
}

variable "databricks_host" {
  type        = string
  description = "Customer's Databricks workspace URL."
}

variable "oidc_issuer_url" {
  type        = string
  description = "OIDC issuer of the cluster running the agent runtime."
}

variable "runtime_namespace" {
  type        = string
  description = "Kubernetes namespace for the agent runtime."
  default     = "adp-runtime"
}

variable "trace_retention_days" {
  type        = number
  description = "How long full traces are retained in the customer's workspace."
  default     = 90
}

variable "control_plane_endpoint" {
  type        = string
  description = "Control plane URL the runtime polls. Outbound only."
}
