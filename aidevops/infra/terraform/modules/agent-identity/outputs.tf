output "agent_name" {
  value       = local.agent_name
  description = "Entra display name. Matches AgentPrincipal.name."
}

output "client_id" {
  value       = azuread_application.agent.client_id
  description = "Entra application (client) id."
}

output "object_id" {
  value       = azuread_service_principal.agent.object_id
  description = "Service principal object id, for RBAC assignments."
}

output "databricks_application_id" {
  value       = databricks_service_principal.agent.application_id
  description = "Databricks service principal id, for Unity Catalog grants."
}
