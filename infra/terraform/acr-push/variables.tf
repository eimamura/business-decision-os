variable "acr_login_server" {
  description = "ACR login server (e.g. myregistry.azurecr.io)"
  type        = string
}

variable "image_name" {
  description = "Docker image name (e.g. bdos-api)"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag (e.g. git SHA)"
  type        = string
}

variable "context_path" {
  description = "Build context path relative to repo root"
  type        = string
  default     = "."
}
