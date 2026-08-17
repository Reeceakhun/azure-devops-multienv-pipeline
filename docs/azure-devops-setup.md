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

## 4. Create a Key Vault per environment

```bash
az keyvault create --name kv-app-dev --resource-group rg-app-dev --location eastus
az keyvault create --name kv-app-staging --resource-group rg-app-staging --location eastus
az keyvault create --name kv-app-prod --resource-group rg-app-prod --location eastus
```

(Key Vault names must be globally unique across all of Azure — if these are
taken, append a short suffix, e.g. `kv-app-dev-rs01`, and use that name
consistently in the pipeline YAML later.)

## 5. Add a placeholder secret to each vault

```bash
az keyvault secret set --vault-name kv-app-dev --name AppInsightsKey --value "placeholder-dev"
az keyvault secret set --vault-name kv-app-staging --name AppInsightsKey --value "placeholder-staging"
az keyvault secret set --vault-name kv-app-prod --name AppInsightsKey --value "placeholder-prod"
```

This gets replaced with a real Application Insights instrumentation key once observability is wired up later — seeded now so the pipeline has something real to fetch from the deploy stage onward, rather than failing on a missing secret.

## 6. Grant each service connection's identity least-privilege Key Vault access

Each service connection already has a Workload-Identity-federated app
registration behind it (created automatically in step 2). Grant that
identity the **Key Vault Secrets User** role — read-only access to secret
*values*, not Key Vault management, not Owner, not Contributor:

```bash
az role assignment create \
  --assignee <sc-dev-app-id> \
  --role "Key Vault Secrets User" \
  --scope /subscriptions/<sub-id>/resourceGroups/rg-app-dev/providers/Microsoft.KeyVault/vaults/kv-app-dev
```

Repeat for staging and prod, each scoped to its own vault only.

Find each service connection's underlying app ID: **Project Settings →
Service connections → click the connection → Manage service principal**
(opens the Azure AD app registration).

## Why Key Vault Secrets User specifically

`Contributor` or `Key Vault Administrator` would let the pipeline modify
access policies or delete the vault itself — far more than a deployment
pipeline should ever need. `Key Vault Secrets User` can only *read* secret
values, which is the entire scope of what a deployment actually requires.

## 7. Create Application Insights per environment

```bash
az monitor app-insights component create \
  --app appinsights-dev --location eastus --resource-group rg-app-dev \
  --application-type web

az monitor app-insights component create \
  --app appinsights-staging --location eastus --resource-group rg-app-staging \
  --application-type web

az monitor app-insights component create \
  --app appinsights-prod --location eastus --resource-group rg-app-prod \
  --application-type web
```

## 8. Replace the placeholder Key Vault secret with the real instrumentation key

```bash
KEY=$(az monitor app-insights component show --app appinsights-dev --resource-group rg-app-dev --query instrumentationKey -o tsv)
az keyvault secret set --vault-name kv-app-dev-rs01 --name AppInsightsKey --value "$KEY"
```

Repeat for staging and prod, using each environment's own Application
Insights resource and its own Key Vault. This overwrites the
`placeholder-dev`/`placeholder-staging`/`placeholder-prod` values seeded
earlier — same secret name, same access pattern, so nothing else in the
pipeline needs to change to pick up the real key.

## 9. Add an Azure Monitor alert rule

```bash
az monitor metrics alert create \
  --name "no-requests-alert-prod" \
  --resource-group rg-app-prod \
  --scopes $(az monitor app-insights component show --app appinsights-prod --resource-group rg-app-prod --query id -o tsv) \
  --condition "count requests/count < 1" \
  --window-size 15m \
  --evaluation-frequency 5m \
  --description "Alerts if the app receives zero requests in 15 minutes — likely indicates a dead deployment"
```

Scoped to prod only for this demo — the same pattern extends to dev/staging
by repeating against their own Application Insights resource IDs.