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

# -------------------------------------------------------------------
# ADLS Gen2 — Lakehouse storage (Phase 8)
# Bronze (raw) → Silver (cleaned) → Gold (analytics-ready)
# -------------------------------------------------------------------
resource "azurerm_storage_account" "lakehouse" {
  name                     = "bdoslakehouse${var.environment}"
  location                 = var.location
  resource_group_name      = var.resource_group_name
  account_tier             = "Standard"
  account_replication_type = "LRS"
  is_hns_enabled           = true  # hierarchical namespace = ADLS Gen2

  lifecycle {
    prevent_destroy = false
  }
}

resource "azurerm_storage_container" "bronze" {
  name                  = "bronze"
  storage_account_name  = azurerm_storage_account.lakehouse.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "silver" {
  name                  = "silver"
  storage_account_name  = azurerm_storage_account.lakehouse.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "gold" {
  name                  = "gold"
  storage_account_name  = azurerm_storage_account.lakehouse.name
  container_access_type = "private"
}

# -------------------------------------------------------------------
# Databricks cluster for ETL pipelines (Bronze → Silver → Gold)
# -------------------------------------------------------------------
resource "databricks_cluster" "etl" {
  cluster_name            = "bdos-etl-${var.environment}"
  spark_version           = "14.3.x-scala2.12"
  node_type_id            = "Standard_DS3_v2"
  autotermination_minutes = 30

  autoscale {
    min_workers = 1
    max_workers = 4
  }

  spark_conf = {
    "spark.databricks.delta.preview.enabled" = "true"
  }

  depends_on = [azurerm_databricks_workspace.main]
}

# -------------------------------------------------------------------
# Databricks jobs — Bronze → Silver and Silver → Gold pipelines
# -------------------------------------------------------------------
resource "databricks_job" "bronze_to_silver" {
  name = "bdos-bronze-to-silver-${var.environment}"

  task {
    task_key = "bronze_to_silver"

    existing_cluster_id = databricks_cluster.etl.id

    python_wheel_task {
      package_name = "lakehouse"
      entry_point  = "packages.lakehouse.cli"
      parameters   = ["run-silver"]
    }
  }

  schedule {
    quartz_cron_expression = "0 0 * * * ?"
    timezone_id            = "UTC"
  }
}

resource "databricks_job" "silver_to_gold" {
  name = "bdos-silver-to-gold-${var.environment}"

  task {
    task_key = "silver_to_gold"

    existing_cluster_id = databricks_cluster.etl.id

    python_wheel_task {
      package_name = "lakehouse"
      entry_point  = "packages.lakehouse.cli"
      parameters   = ["run-gold"]
    }
  }

  schedule {
    quartz_cron_expression = "0 30 * * * ?"
    timezone_id            = "UTC"
  }
}
