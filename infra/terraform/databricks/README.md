# Databricks Terraform Stage

Provisions the Databricks workspace, MLflow experiment, and ADLS Gen2 storage
for model artifacts. This stage is part of Phase 6 (Real Predictor).

## Prerequisites

This stage **must be applied after `shared/`** because it depends on the
resource group created there. The `shared/` stage must be applied successfully
before running any commands in this directory.

## Apply Order

The Databricks provider requires the workspace URL to authenticate against
workspace-level APIs. Because of this circular dependency, apply in two steps:

```bash
# Step 1: Provision the workspace and storage account only.
terraform apply \
  -target=azurerm_databricks_workspace.main \
  -target=azurerm_storage_account.models \
  -target=azurerm_storage_container.mlflow_artifacts

# Step 2: The provider now has a workspace URL. Apply the rest.
terraform apply
```

## Variables

| Variable              | Default                              | Description                        |
|-----------------------|--------------------------------------|------------------------------------|
| `subscription_id`     | (required)                           | Azure subscription ID              |
| `resource_group_name` | `bdos-rg`                            | Resource group (from shared/)      |
| `environment`         | `dev`                                | Deployment environment             |
| `location`            | `eastus2`                            | Azure region                       |
| `workspace_name`      | `bdos-databricks-${var.environment}` | Databricks workspace name          |

## Outputs

| Output                  | Description                                      |
|-------------------------|--------------------------------------------------|
| `workspace_url`         | Databricks workspace URL                         |
| `mlflow_experiment_id`  | MLflow experiment ID for `/bdos/predictor-training` |
| `storage_account_name`  | Storage account name for MLflow model artifacts  |

## Resources Created

- `azurerm_databricks_workspace` — Standard SKU workspace in East US 2
- `azurerm_storage_account` — `bdosmodels<env>` for MLflow artifact storage
- `azurerm_storage_container` — `mlflow-artifacts` container (private)
- `databricks_mlflow_experiment` — `/bdos/predictor-training` experiment
