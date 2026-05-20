output "workspace_url" {
  description = "URL of the Databricks workspace"
  value       = azurerm_databricks_workspace.main.workspace_url
}

output "mlflow_experiment_id" {
  description = "MLflow experiment ID for predictor training"
  value       = databricks_mlflow_experiment.predictor_training.id
}

output "storage_account_name" {
  description = "Name of the storage account holding MLflow model artifacts"
  value       = azurerm_storage_account.models.name
}
