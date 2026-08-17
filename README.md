# Azure DevOps Multi-Environment Pipeline

A release pipeline built in Azure DevOps demonstrating environment
promotion (dev → staging → prod), least-privilege service connections,
and Key Vault-backed secret management via Managed Identity — the pattern
described, not just claimed.

> **Status: in progress.** Build and Dev deployment stages are live.
> Staging/prod deployment, approval gates, rollback, and observability are
> being added next — see [Roadmap](#roadmap).

## Why this project

Most CI/CD portfolio pieces show a single environment and a single
deploy step. This one exists to demonstrate three things that only show
up in real multi-environment operations:

- **Environment promotion** — the same artifact moves dev → staging → prod
  without being rebuilt, with approval gates before staging and prod
- **Least-privilege RBAC in practice** — three separate service
  connections, each scoped to a single resource group, not one broad
  connection reused everywhere
- **Secret management via Key Vault + Managed Identity** — no secrets
  stored as pipeline variables or in source control

## Stack

- **App:** Python 3.12 / Flask
- **Tests:** pytest, published as Azure DevOps test results
- **CI/CD:** Azure DevOps Pipelines (YAML)
- **Secrets:** Azure Key Vault, accessed via Workload-Identity-federated
  service connections
- **Cloud:** Azure (resource groups per environment)

## Project structure

```
azure-devops-multienv-pipeline/
├── app/
│   ├── main.py            # Flask app: / and /health (reports ENVIRONMENT)
│   ├── test_main.py       # unit tests for both endpoints
│   └── requirements.txt
├── docs/
│   └── azure-devops-setup.md   # service connections, RBAC, Key Vault setup
├── azure-pipelines.yml     # currently: Build, DeployDev stages
└── .gitignore
```

## Running locally

```bash
cd app
python -m pip install -r requirements.txt
pytest test_main.py -v
python main.py
```

`http://localhost:5000/health` returns `{"status": "ok", "environment": "unknown"}`
locally (the `ENVIRONMENT` variable is only set once deployed via the pipeline).

## Azure setup

Three resource groups, three Key Vaults, three service connections — one
per environment, each scoped only to its own resource group. Full setup
steps, including the exact `az` commands and the RBAC reasoning, are in
[`docs/azure-devops-setup.md`](docs/azure-devops-setup.md).

## Pipeline

`azure-pipelines.yml` currently runs two stages on every push to `main`:

**`Build`**
1. Sets up Python 3.12
2. Installs dependencies from `app/requirements.txt`
3. Runs the pytest suite, publishing results in JUnit format so Azure
   DevOps shows pass/fail history natively rather than just pipeline logs
4. Publishes the `app/` folder as a pipeline artifact, so later deploy
   stages consume the exact code that was tested — not a fresh checkout
   that could drift

**`DeployDev`** — runs automatically after a successful build, no approval required
1. Authenticates via the `sc-dev` service connection (Workload Identity federation)
2. Fetches the `AppInsightsKey` secret from `kv-app-dev-rs01` via Azure CLI
3. Marks the fetched value as a secret pipeline variable (`issecret=true`), so it's masked in logs even where referenced
4. Deploys using the artifact published by `Build` — not a fresh checkout, so what's deployed is exactly what was tested

Staging (with approval) and Prod (with approval + rollback) are not yet
added — see Roadmap.

**`DeployStaging`** — requires manual approval before running
1. Pipeline pauses after `DeployDev` succeeds, waiting for an approver
   (configured via Environments → staging → Approvals and checks)
2. Once approved, authenticates via `sc-staging`, fetches `AppInsightsKey`
   from the staging Key Vault, and deploys the same artifact `Build`
   published — no rebuild between environments

## Roadmap
- [ ] Add Prod deployment stage with a manual approval gate and a
      documented rollback strategy
- [ ] Wire up Application Insights telemetry and a basic Azure Monitor
      alert rule
- [ ] Write up environment promotion flow and RBAC design decisions in full

## Notes / issues hit along the way

- **Key Vault created, but even the account that created it got
  `ForbiddenByRbac` when setting a secret** — the vault uses RBAC
  authorization mode, which requires an explicit role assignment even for
  the creating user. Fixed by granting the signed-in user's own account
  `Key Vault Secrets Officer` scoped to the vault, separately from the
  service connection's `Key Vault Secrets User` role.
- **Azure DevOps "Pipelines" page showed no pipeline at all** — the
  service connections and resource groups had been set up, but the actual
  "Create Pipeline → connect to GitHub repo" step had never been run.
  These are separate setup steps in Azure DevOps and neither implies the
  other.
- **`DeployDev` job failed: "Environment dev could not be found"** — Azure
  DevOps Environments must be created manually in advance; they are not
  auto-created the first time a `deployment` job references one. Fixed by
  creating the `dev` environment via Pipelines → Environments before
  re-running.
- **`DeployStaging` paused with "This pipeline needs permission to access
  a resource"** — distinct from the approval check configured on the
  environment. Azure DevOps requires a one-time authorization the first
  time a pipeline references a given Environment, separate from the
  per-run approval gate. Resolved by clicking View → Permit; the approval
  prompt then appeared as expected.