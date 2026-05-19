variable "resource_group_name" {
  description = "Name of the Azure Resource Group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus2"
}

variable "acr_name" {
  description = "Azure Container Registry name (must be globally unique, alphanumeric)"
  type        = string
}
