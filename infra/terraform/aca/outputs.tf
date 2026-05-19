output "api_fqdn" {
  description = "FQDN of the API Container App"
  value       = azurerm_container_app.api.ingress[0].fqdn
}

output "web_fqdn" {
  description = "FQDN of the Web Container App"
  value       = azurerm_container_app.web.ingress[0].fqdn
}

output "simulation_job_resource_id" {
  description = "Azure Resource ID of the simulation Container App Job"
  value       = azurerm_container_app_job.simulation_worker.id
}
