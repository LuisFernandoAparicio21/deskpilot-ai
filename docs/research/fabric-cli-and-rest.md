# Automating Microsoft Fabric from the terminal (Fabric CLI, REST, az)

Consulted: 2026-11-22. Branch: chore/phase-c-plan.

## Question
Which official tools automate Microsoft Fabric from a terminal today (Fabric CLI `fab`, Fabric REST APIs, az CLI)? Can they create a workspace, lakehouse and Warehouse, upload files to OneLake, run a notebook (Job Scheduler API) and read its status? Which authentication works with a trial capacity and a non-admin university Entra account, and what happens with service principals?

## Answer
- **Fabric CLI `fab`**: package `ms-fabric-cli`, latest 1.9.0 (released 2026-11-04; checked with `pip index versions` and the GitHub releases API). Requires Python 3.10 to 3.14. Install on Windows (PowerShell 5.1): `pip install ms-fabric-cli`, then `fab --version`. No winget package was checked (⚠ not confirmed).
- **Auth in `fab`**: `fab auth login` (interactive browser, the one for a university user); `fab auth login --azure-cli` reuses an existing `az login`; service principal (secret, certificate or federated token) and managed identity (`--identity`, documented as validated only on Azure VMs). Device code is not documented (⚠ not confirmed). `fab auth status` shows the session.
- **Create**: `fab create ws1.Workspace -P capacityname=<capacity>` (or `-P capacityname=none`), `fab create ws1.Workspace/lh1.Lakehouse`. `.Warehouse` is a supported item type (parameter `enableCaseInsensitive`), so `fab create ws1.Workspace/wh1.Warehouse` follows the same pattern (⚠ the docs show the example only for Lakehouse; not run).
- **Upload to OneLake**: `fab cp .\data.csv ws1.Workspace/lh1.Lakehouse/Files/upload/` (local to OneLake; also download and OneLake to OneLake).
- **Notebook**: `fab job run ws1.Workspace/nb1.Notebook` (waits; `--timeout`, `-P name:type=value` parameters), `fab job start ws1.Workspace/nb1.Notebook` (async), `fab job run-list ws1.Workspace/nb1.Notebook`, `fab job run-status ws1.Workspace/nb1.Notebook --id <id>` (the docs name the placeholder `<schedule_id>`; ⚠ confirm it accepts the job instance id).
- **REST**: base `https://api.fabric.microsoft.com/v1`. Run job: `POST /workspaces/{workspaceId}/items/{itemId}/jobs/{jobType}/instances` returns `202` with `Location` (job instance URL) and `Retry-After`; poll the `Location` with GET to read the status. Scope `Notebook.Execute.All` or `Item.Execute.All`; user, service principal and managed identity are supported. The `jobType` string for notebooks (`RunNotebook`) is ⚠ not shown on the cited page (its examples use `DefaultJob` and `Execute`). Token scope for direct calls: `https://api.fabric.microsoft.com/.default` (⚠ not on the cited pages).
- **az CLI**: not a Fabric data-plane automation tool. Its role here is signing in (`az login`) so `fab` or `azure-identity` reuse the session. Whether an `az fabric` group exists for capacities is ⚠ not confirmed.
- **Tenant and permissions**: creating Lakehouse, Warehouse and notebooks requires the tenant switch "Users can create Fabric items" (controlled by a Fabric administrator, can be limited to security groups and overridden per capacity) plus a Fabric capacity (trial, F or P SKU); Pro/PPU licenses give no capacity. A non-admin cannot change that switch.
- **Service principals**: the CLI docs say they need the tenant switch "Allow service principals to use Fabric APIs" enabled in the admin portal, plus an app registration with a secret. A non-admin university user can normally do neither, so service principals are likely unavailable. Whether a separate per-user "can call Fabric APIs" switch exists is ⚠ not found in the cited sources.

## Recommended decision
Use `fab` with `fab auth login` (interactive, the university user) for scripted setup: create the workspace on the trial capacity, create the lakehouse, `fab cp` the CSVs, `fab job run` the notebook, `fab job run-status` to confirm. Do not plan around service principals unless the tenant admin enables them. If "Users can create Fabric items" is off for the user, the only path is asking the admin (or using another tenant); verify first with a single `fab create` before writing scripts. Keep `ms-fabric-cli` out of `requirements.txt` (dev tool; note the pinned version 1.9.0 in docs).

## Sources
- Fabric CLI documentation (microsoft/fabric-cli, docs/examples: auth, workspace, item, onelake, job): https://github.com/microsoft/fabric-cli/tree/main/docs (rendered at https://microsoft.github.io/fabric-cli/), consulted 2026-11-22
- Job Scheduler - Run On Demand Item Job (Fabric REST API): https://learn.microsoft.com/en-us/rest/api/fabric/core/job-scheduler/run-on-demand-item-job, consulted 2026-11-22
- Enable Microsoft Fabric for your organization ("Users can create Fabric items"): https://learn.microsoft.com/en-us/fabric/admin/fabric-switch, consulted 2026-11-22

Confidence: medium (commands and endpoints confirmed in docs; nothing was run against a real tenant).
