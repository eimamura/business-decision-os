# ADR-0007: Azure OIDC Federated Credentials for GitHub Actions

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

GitHub Actions workflows need to authenticate to Azure to run Terraform plans, push container images to ACR, and deploy to Azure Container Apps. The conventional approach of storing a long-lived service principal client secret in GitHub Secrets creates a credential rotation burden and introduces the risk of secret leakage via log exposure or repository access.

## Decision

Use **Azure OIDC federated credentials** (Workload Identity Federation) for all GitHub Actions authentication to Azure. No long-lived client secrets are stored in GitHub Secrets. Authentication uses `azure/login@v2` with `client-id`, `tenant-id`, and `subscription-id` only.

Three subject claims are configured:

| Subject claim | Purpose |
|---|---|
| `repo:eimamura/<repo>:ref:refs/heads/main` | Production deploys on merge to main |
| `repo:eimamura/<repo>:pull_request` | PR-scoped Terraform plans and lint/test runs |
| `repo:eimamura/<repo>:environment:prod` | Environment-gated production deploys |

Least-privilege RBAC: `Contributor` on the resource group, `AcrPush` on ACR, `Key Vault Secrets User` granted to the runtime Managed Identity (not the GitHub Actions service principal).

## Rationale

- **No secrets to rotate:** OIDC tokens are short-lived (minutes) and issued per workflow run by GitHub's OIDC provider. There is no static credential that can be leaked, expired, or forgotten.
- **Reduced attack surface:** Even if workflow logs are exposed, there is no credential value to extract. The trust relationship is controlled by the subject claim, scoped to specific refs or environments.
- **Environment-gated deploys:** The `environment:prod` subject claim enables GitHub's environment protection rules (required reviewers, deployment branches) to gate production access at the identity level, not just the workflow level.
- **Principle of least privilege:** The runtime Managed Identity (used by ACA containers to access Key Vault) is separate from the GitHub Actions service principal. The GHA SP has no access to application secrets at runtime.

## Trade-offs

- **One-time Azure AD configuration:** The federated credential trust must be configured in Azure AD before any workflow can authenticate. This is a one-time setup cost, not ongoing maintenance.
- **Azure AD dependency:** OIDC federation requires an Azure AD application (app registration) and service principal. This adds an Azure AD object to manage alongside the resource group.
- **Subject claim precision:** Subject claims must exactly match the workflow context. Renaming the repository or changing branch protection rules requires updating the federated credential subject claims.

## Consequences

- GitHub Actions workflows use `azure/login@v2` with `client-id`, `tenant-id`, `subscription-id`; no `client-secret` parameter.
- The Azure AD app registration and federated credential subjects are documented in `infra/terraform/shared/` and provisioned via Terraform.
- All Terraform state backends and ACR operations use the same federated identity.
- Local developer access to Azure uses separate developer credentials (`az login`), not the GitHub Actions service principal.
- If the repository is renamed or transferred, the federated credential subject claims must be updated before CI/CD will function.
