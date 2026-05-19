terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

locals {
  location = "eastus2"
}

# -------------------------------------------------------------------
# Resource Group
# -------------------------------------------------------------------
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = local.location

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# Key Vault
# -------------------------------------------------------------------
data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                = "bdos-kv-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# Managed Identity (User-assigned)
# -------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "main" {
  name                = "bdos-identity-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# Azure OIDC Federated Credentials
# -------------------------------------------------------------------
resource "azurerm_federated_identity_credential" "github_main" {
  name                = "github-main"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.main.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repo}:ref:refs/heads/main"
}

resource "azurerm_federated_identity_credential" "github_pr" {
  name                = "github-pr"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.main.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repo}:pull_request"
}

resource "azurerm_federated_identity_credential" "github_prod" {
  name                = "github-prod"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.main.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repo}:environment:prod"
}

# -------------------------------------------------------------------
# Application Insights + Log Analytics Workspace (T-0091)
# -------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "bdos-law-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  lifecycle {
    prevent_destroy = false
  }
}

resource "azurerm_application_insights" "main" {
  name                = "bdos-appinsights-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  lifecycle {
    prevent_destroy = false
  }
}

# -------------------------------------------------------------------
# PostgreSQL Flexible Server (skeleton — needs real connection string)
# Uncomment and supply values once database credentials are in Key Vault.
# -------------------------------------------------------------------
# resource "azurerm_postgresql_flexible_server" "main" {
#   name                   = "bdos-postgres-${var.environment}"
#   location               = azurerm_resource_group.main.location
#   resource_group_name    = azurerm_resource_group.main.name
#   version                = "16"
#   administrator_login    = var.postgres_admin_user
#   administrator_password = var.postgres_admin_password  # supply via Key Vault reference
#   storage_mb             = 32768
#   sku_name               = "B_Standard_B1ms"
#
#   lifecycle {
#     prevent_destroy = false
#   }
# }
