variable "resource_group_name" {
  description = "Name of the Azure Resource Group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus2"
}

variable "container_registry_url" {
  description = "Azure Container Registry login server URL"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag (e.g. git SHA)"
  type        = string
}
