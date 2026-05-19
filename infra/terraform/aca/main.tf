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
