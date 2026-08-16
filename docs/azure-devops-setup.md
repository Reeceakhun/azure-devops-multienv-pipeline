# Azure DevOps Setup: Service Connections & RBAC

This project uses **three separate resource groups** (one per environment)
and **three separate service connections**, each scoped only to its own
resource group. No single credential in this pipeline can touch more than
one environment — a deliberate choice, not an oversight.

## 1. Create the resource groups

```bash
az group create --name rg-app-dev --location eastus
az group create --name rg-app-staging --location eastus
az group create --name rg-app-prod --location eastus
```

## 2. Create a service connection per environment

In Azure DevOps: **Project Settings → Service connections → New service
connection → Azure Resource Manager → Workload Identity federation
(automatic)**.

Workload Identity federation is used instead of a client-secret-based
service principal — same reasoning as the OIDC setup in
[`aks-ephemeral-infra`](https://github.com/Reeceakhun/aks-ephemeral-infra):
no long-lived secret is stored anywhere, Azure DevOps and Azure AD handle
trust via short-lived tokens issued per pipeline run.

Repeat this three times:

| Service connection name | Scope level | Resource group |
|---|---|---|
| `sc-dev` | Resource Group | `rg-app-dev` |
| `sc-staging` | Resource Group | `rg-app-staging` |
| `sc-prod` | Resource Group | `rg-app-prod` |

Critically: set **Scope level = Resource Group**, not Subscription, for
each one. This is what makes the "least privilege" claim actually true
rather than aspirational — the dev service connection's identity has no
access at all to the staging or prod resource groups, and vice versa.

## 3. Verify least-privilege RBAC

After creating each service connection, confirm its role assignment:

```bash
az role assignment list --scope /subscriptions/<sub-id>/resourceGroups/rg-app-dev -o table
```

Should show the `sc-dev` service connection's identity with `Contributor`
scoped to `rg-app-dev` only — not the subscription. Repeat for staging and
prod against their respective resource groups.

## Why this matters

This mirrors a real production concern: a compromised or misconfigured dev
pipeline should never be able to touch production infrastructure. Scoping
each service connection to a single resource group makes that structurally
true, rather than relying on convention or trust.
