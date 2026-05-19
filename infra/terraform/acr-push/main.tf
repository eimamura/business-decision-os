terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

# Tag and push images to Azure Container Registry
# Phase 0 scaffold — implementation added in Phase 1
