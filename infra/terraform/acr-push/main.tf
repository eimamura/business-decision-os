terraform {
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

# -------------------------------------------------------------------
# Build and push image to ACR using az acr build
# -------------------------------------------------------------------
resource "null_resource" "acr_build" {
  triggers = {
    image_tag    = var.image_tag
    context_path = var.context_path
  }

  provisioner "local-exec" {
    command = <<-EOT
      az acr build \
        --registry ${var.acr_login_server} \
        --image ${var.image_name}:${var.image_tag} \
        ${var.context_path}
    EOT
  }
}
