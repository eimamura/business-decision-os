output "resource_group_id" {
  description = "Resource Group ID"
  value       = azurerm_resource_group.main.id
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.main.vault_uri
}

output "managed_identity_client_id" {
  description = "Client ID of the User-Assigned Managed Identity"
  value       = azurerm_user_assigned_identity.main.client_id
}

output "app_insights_connection_string" {
  description = "Application Insights connection string"
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}

output "redis_hostname" {
  value     = azurerm_redis_cache.main.hostname
  sensitive = false
}

output "redis_primary_connection_string" {
  value     = azurerm_redis_cache.main.primary_connection_string
  sensitive = true
}
