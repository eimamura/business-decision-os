terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# -------------------------------------------------------------------
# Container Apps Environment
# -------------------------------------------------------------------
resource "azurerm_container_app_environment" "main" {
  name                = "bdos-cae"
  location            = var.location
  resource_group_name = var.resource_group_name

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# Container App: api
# -------------------------------------------------------------------
resource "azurerm_container_app" "api" {
  name                         = "bdos-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  template {
    container {
      name   = "api"
      image  = "${var.container_registry_url}/bdos-api:${var.image_tag}"
      cpu    = 0.5
      memory = "1Gi"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# Container App: web
# -------------------------------------------------------------------
resource "azurerm_container_app" "web" {
  name                         = "bdos-web"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  template {
    container {
      name   = "web"
      image  = "${var.container_registry_url}/bdos-web:${var.image_tag}"
      cpu    = 0.5
      memory = "1Gi"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 3000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# Container App Job: simulation-worker
# -------------------------------------------------------------------
resource "azurerm_container_app_job" "simulation_worker" {
  name                         = "bdos-simulation-worker"
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.main.id

  replica_timeout_in_seconds = 300
  replica_retry_limit        = 0

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name   = "simulation-worker"
      image  = "${var.container_registry_url}/bdos-simulation-worker:${var.image_tag}"
      cpu    = 1.0
      memory = "2Gi"

      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
      env {
        name  = "APP_ENV"
        value = "prod"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
    }
  }

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# Container App Job: optimization-worker
# -------------------------------------------------------------------
resource "azurerm_container_app_job" "optimization_worker" {
  name                         = "bdos-optimization-worker"
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.main.id

  replica_timeout_in_seconds = 600
  replica_retry_limit        = 0

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name   = "optimization-worker"
      image  = "${var.container_registry_url}/bdos-optimization-worker:${var.image_tag}"
      cpu    = 2.0
      memory = "4Gi"

      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
      env {
        name  = "APP_ENV"
        value = "prod"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
    }
  }

  lifecycle {
    prevent_destroy = false
  }
}
