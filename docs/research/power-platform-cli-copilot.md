# Power Platform CLI (`pac`) and Copilot Studio agents (R3)

Consulted: 2026-11-22. Max 3 official Microsoft sources. "⚠ not confirmed" = not stated in the cited sources.

## Question
Does the Power Platform CLI (`pac`) let us create, import or export Copilot Studio agents today, or only solutions? Does it work with a Copilot Studio trial/developer environment? Which agent parts (instructions, knowledge, tools/connectors, topics) can be authored as files/solutions, and which only in the UI?

## Answer
- A `pac copilot` command group exists and is documented (page dated 2026-10-25). Commands: `clone`, `create`, `delete`, `extract-template`, `extract-translation`, `init`, `list`, `mcp`, `merge-translation`, `model list|predict|prepare-fetch`, `pack`, `publish`, `pull`, `push`, `quarantine`, `status`.
- Create: `pac copilot init --name ... --publisher-prefix ... [--instructions ...] [--environment <id>]` scaffolds a workspace; with `--environment` it also packs, imports the solution and creates the live agent. `pac copilot create` needs a YAML template produced by `extract-template`.
- Export / import: `clone` / `pull` / `push` sync a workspace with Dataverse; `pack` builds a solution `.zip` (local, no auth); then `pac solution import --path x.zip` deploys it. `pac solution export --name <sol> --path x.zip [--managed]` exports the solution that contains the agent.
- Auth: sync commands need a profile from `pac auth create`; `pack` and local `init` need none. Only Dataverse environments are targeted.
- Trial / developer environment: the docs do not say whether `pac copilot` works against a trial-licence environment. ⚠ not confirmed. Technical prerequisite is a Dataverse environment where the user can import solutions; a university tenant may block sign-in or import (⚠ tenant-dependent).
- File-authorable parts (VS Code extension / workspace layout): `agent.mcs.yaml` (main definition), `settings.mcs.yml`, `topics/*.mcs.yaml`, `actions/` (tools: prompts, flows, custom connectors, REST APIs, MCP connectors), `workflows/` (Power Automate flows), `trigger/`, `knowledge/files` (local files uploaded on apply), `connectionreferences.mcs.yml`. `push` also uploads knowledge files, cloud flows and connection references.
- UI-only parts: ⚠ not confirmed; the cited pages do not list UI-only limits. Likely UI steps (inference, not documented): binding/authenticating real connections and publishing to channels (`pac copilot publish` exists, but publishing needs a paid licence, see R4). Where the instructions text lives in the YAML is ⚠ not confirmed; `init --instructions` shows it is settable at creation.
- There is no documented CLI import of our `integrations/copilot_studio/*.md` or `openapi.json`; they must be translated into those YAML files or pasted in the UI.

## Recommended decision
Do NOT depend on `pac` for the deliverable. Build the agent in the UI (the repo's `instructions.md`, topics and `openapi.json` are the source of truth to paste). Treat `pac copilot clone` + `pac solution export` as an optional bonus to version the resulting agent in Git, only if the environment and tenant allow `pac auth create`. Verify with `pac copilot list` right after sign-in (PowerShell 5.1) before investing time.

## Sources
| Title | URL | Consulted |
| --- | --- | --- |
| Microsoft Power Platform CLI copilot command group | https://learn.microsoft.com/en-us/power-platform/developer/cli/reference/copilot | 2026-11-22 |
| Microsoft Power Platform CLI solution command group | https://learn.microsoft.com/en-us/power-platform/developer/cli/reference/solution | 2026-11-22 |
| Edit your Microsoft Copilot Studio agent in Microsoft Visual Studio Code | https://learn.microsoft.com/en-us/microsoft-copilot-studio/visual-studio-code-extension-edit-agent-components | 2026-11-22 |
