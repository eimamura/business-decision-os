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

variable "database_url" {
  description = "PostgreSQL connection string for simulation worker"
  type        = string
  sensitive   = true
}

variable "acr_login_server" {
  description = "Azure Container Registry login server (e.g. bdosacr.azurecr.io)"
  type        = string
}

variable "redis_connection_string" {
  description = "Redis primary connection string for Celery broker and result backend"
  type        = string
  sensitive   = true
}
