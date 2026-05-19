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

# Shared infrastructure: Postgres, Key Vault, OpenAI, Monitor, networking
# Region: eastus2
# Secrets via Azure Key Vault + Managed Identity — no hardcoded credentials
# Phase 0 scaffold — implementation added in Phase 1
