variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the Azure Resource Group (must already exist — created by shared/ stage)"
  type        = string
  default     = "bdos-rg"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus2"
}

variable "workspace_name" {
  description = "Name of the Databricks workspace"
  type        = string
  default     = "bdos-databricks-${var.environment}"
}
