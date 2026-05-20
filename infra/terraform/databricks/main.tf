terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    databricks = {
      source  = "hashicorp/databricks"
      version = "~> 1.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

# -------------------------------------------------------------------
# NOTE: The databricks provider must be configured AFTER the workspace
# is created. In a bootstrapped pipeline, apply azurerm resources first
# (terraform apply -target=azurerm_databricks_workspace.main), then
# configure the provider with the workspace URL and re-apply.
# Alternatively, use two separate Terraform states: one for the
# azurerm_databricks_workspace resource and one for databricks_* resources.
# -------------------------------------------------------------------
provider "databricks" {
  host = azurerm_databricks_workspace.main.workspace_url
}

# -------------------------------------------------------------------
# Databricks Workspace
# -------------------------------------------------------------------
resource "azurerm_databricks_workspace" "main" {
  name                = var.workspace_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "standard"

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# Storage Account for MLflow model artifacts
# -------------------------------------------------------------------
resource "azurerm_storage_account" "models" {
  name                     = "bdosmodels${var.environment}"
  location                 = var.location
  resource_group_name      = var.resource_group_name
  account_tier             = "Standard"
  account_replication_type = "LRS"

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# Storage Container for MLflow artifacts
# -------------------------------------------------------------------
resource "azurerm_storage_container" "mlflow_artifacts" {
  name                  = "mlflow-artifacts"
  storage_account_name  = azurerm_storage_account.models.name
  container_access_type = "private"
}

# -------------------------------------------------------------------
# MLflow Experiment
# Depends on workspace being fully provisioned before the Databricks
# provider can authenticate and create workspace-level resources.
# -------------------------------------------------------------------
resource "databricks_mlflow_experiment" "predictor_training" {
  name = "/bdos/predictor-training"

  depends_on = [azurerm_databricks_workspace.main]
}
