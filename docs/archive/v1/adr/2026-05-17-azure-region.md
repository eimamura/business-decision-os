# ADR-0005: Azure US East 2 as Cloud Platform and Region

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The project requires a cloud platform for container hosting (API, Web), managed PostgreSQL, container registry, key vault, and an embedding model endpoint (Azure OpenAI). A single region must be chosen for MVP to keep networking simple and costs predictable.

## Decision

Use **Microsoft Azure** as the cloud platform with **US East 2 (eastus2)** as the sole deployment region for all MVP resources.

## Rationale

- **Anthropic partnership:** Anthropic has a commercial partnership with Azure, which simplifies billing, support, and potential future access to Azure-hosted Claude endpoints.
- **Azure OpenAI availability:** `text-embedding-3-small` is available via Azure OpenAI in `eastus2`, aligning embedding calls with the same cloud and billing account as all other infrastructure.
- **Azure Container Apps:** ACA provides serverless container hosting with built-in scaling, suitable for the FastAPI backend and Next.js frontend without requiring full Kubernetes management.
- **Managed Identity + Key Vault:** Azure's Managed Identity model eliminates credential management for service-to-service calls, consistent with the zero-secrets-in-code policy.
- **GitHub Actions OIDC:** Azure supports GitHub Actions OIDC federated credentials, enabling secretless CI/CD (see `docs/adr/2026-05-17-azure-oidc.md`).
- **US East 2 service availability:** `eastus2` has broad availability for ACR, ACA, PostgreSQL Flexible Server, Key Vault, and Azure Monitor.

## Trade-offs

- **Azure vs AWS/GCP:** AWS and GCP offer comparable services. The decision favors Azure due to the Anthropic partnership and Azure OpenAI embedding availability. AWS and GCP alternatives remain viable if the partnership terms change.
- **Single region:** All resources in `eastus2` means users in Asia or Europe experience higher latency. Acceptable for MVP with a small user base; multi-region can be added in Phase 9+ if needed.
- **Region latency for non-US developers:** Developers outside North America may experience higher latency in local testing against deployed services. Local Docker Compose development mitigates this.

## Consequences

- All Terraform resources target `eastus2`. The region is parameterized in `infra/terraform/shared/` to enable future multi-region expansion.
- Azure OpenAI endpoint for `text-embedding-3-small` is provisioned in `eastus2` under the same resource group.
- Databricks workspace (Phase 8+) will also be provisioned in `eastus2` for data locality.
- If regulatory compliance requires data residency outside the US, this decision must be revisited with a new ADR.
