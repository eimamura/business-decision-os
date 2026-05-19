# ADR-0006: Terraform Pipeline Split into Independent State Modules

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

Infrastructure-as-code for this project covers multiple concerns with different change cadences: container image builds, pushing images to a registry, deploying containerized applications, and managing shared stateful resources (PostgreSQL, Key Vault, networking). A monolithic Terraform state would require a full plan/apply for any change, increasing blast radius and slowing iteration.

## Decision

Split the Terraform configuration into **four independent state modules**, each with its own backend state:

| Stage | Path | Purpose |
|---|---|---|
| 1 | `infra/terraform/image-build/` | Build container images |
| 2 | `infra/terraform/acr-push/` | Tag and push images to ACR |
| 3 | `infra/terraform/aca/` | Azure Container Apps deployment; receives image tag as input |
| Cross-stage | `infra/terraform/shared/` | PostgreSQL, Key Vault, Azure OpenAI, Monitor, networking |
| Library | `infra/terraform/modules/` | Reusable modules shared across stages |

## Rationale

- **Decoupled change cadence:** Application deploys (ACA) happen on every merge to `main`. Shared infrastructure (PostgreSQL, Key Vault) changes rarely. Separating them prevents an application deploy from touching stateful infrastructure.
- **Blast radius isolation:** A failed plan/apply in `aca/` cannot corrupt the `shared/` state. Stateful resources are protected in their own state file.
- **Faster plan/apply cycles:** Each stage plans only the resources it owns. A full `shared/` plan is not required for routine application deploys.
- **Parallel pipeline stages:** `image-build` and `acr-push` can run as a sequence while `shared/` changes are gated separately. The `aca/` stage depends on outputs from both `acr-push/` and `shared/`.
- **Easy teardown:** `prevent_destroy = false` on all resources and no resource locks; `terraform destroy` on `aca/` tears down the application layer without touching shared infrastructure.

## Trade-offs

- **Multiple state files to manage:** Four state backends require four backend configurations and four sets of output variables passed between stages. Cross-stage references use Terraform remote state data sources.
- **Coordination overhead:** Changes that span multiple stages (e.g., adding a new environment variable backed by a Key Vault secret) must be applied in the correct order. The CI pipeline enforces the order.
- **More CI configuration:** The GitHub Actions workflow must explicitly sequence `shared/` apply before `aca/` apply, and pass image tags as inputs.

## Consequences

- GitHub Actions pipeline: `lint-test → image-build → acr-push → terraform plan/apply (shared) → terraform plan/apply (aca)`.
- PRs run `lint-test` + `terraform plan` on all relevant stages. Merges to `main` run the full deploy chain.
- The `shared/` state is treated as the most sensitive; changes to it require an explicit PR review.
- `infra/terraform/modules/` contains reusable modules (e.g., ACA app definition, Key Vault secret reference) consumed by `aca/` and `shared/`.
- All resources use `prevent_destroy = false` and have no resource locks, enabling clean `terraform destroy` for MVP iteration.
