output "agent_principals" {
  value = { for k, m in module.agent_identity : k => {
    name      = m.agent_name
    client_id = m.client_id
    object_id = m.object_id
  } }
  description = "Provisioned agent identities. Hand this to the security review as the definitive list of non-human principals."
}

output "key_vault_uri" {
  value       = azurerm_key_vault.agent_secrets.vault_uri
  description = "Customer-owned Key Vault. No secret here ever reaches the control plane."
}

output "trace_workspace_id" {
  value       = azurerm_log_analytics_workspace.traces.workspace_id
  description = "Where full traces live, in the customer's own subscription."
}
