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

output "lakehouse_storage_account_name" {
  description = "ADLS Gen2 storage account for Bronze/Silver/Gold Delta tables"
  value       = azurerm_storage_account.lakehouse.name
}

output "lakehouse_storage_account_id" {
  description = "Resource ID of the lakehouse ADLS Gen2 storage account"
  value       = azurerm_storage_account.lakehouse.id
}

output "etl_cluster_id" {
  description = "ID of the Databricks ETL cluster"
  value       = databricks_cluster.etl.id
}

output "bronze_to_silver_job_id" {
  description = "Databricks job ID for Bronze → Silver pipeline"
  value       = databricks_job.bronze_to_silver.id
}

output "silver_to_gold_job_id" {
  description = "Databricks job ID for Silver → Gold pipeline"
  value       = databricks_job.silver_to_gold.id
}
