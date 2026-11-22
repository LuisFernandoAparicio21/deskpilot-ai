# Phase C automation plan (PL-13)

Branch: `chore/phase-c-plan` (the standard prefix for documentation per [branch-and-feature-naming.md](research/branch-and-feature-naming.md), Recommended decision 2; the requested name `docs/phase-c-plan` is not in Conventional Branch). Date: 2026-11-22. Status: plan only, no code. Roles and rules: `.claude/agents/planner.md`, `.claude/skills/feature-loop/SKILL.md`. Source of truth for steps: [MANUAL_STEPS.md](MANUAL_STEPS.md) (46 numbered steps plus 42b).

Conventions used below:
- "R1..R7" are the Phase C research notes in `docs/research/` (R1 `fabric-cli-and-rest`, R2 `fabric-sql-from-python`, R3 `power-platform-cli-copilot`, R4 `copilot-studio-trial-limits`, R5 `dev-tunnels`, R6 `power-bi-pbip`, R7 `demo-capture`).
- "⚠ not confirmed" is copied from the research: that detail is NOT verified, the plan has a plan B for it, and the feature must confirm it on a real tenant before claiming it.
- Minutes are estimates, not measurements.
- "Local" in the source column means a repo command or repo script that needs no external documentation.

## 1. Summary

1. Claude Code automates 22 of the 47 steps: local checks, Fabric provisioning with `fab`, data upload, 10 SQL queries, tunnel, OpenAPI export, results import, README and validation updates, PR.
2. Claude Code prepares and the user only runs 13 steps: interactive sign-ins, Copilot Studio paste-and-click, importing the evaluation CSV, Power BI build, video recording, video link.
3. 12 steps stay manual (tenant, trial, licences, learning log, skipped optional steps); none of them has an official automation source.
4. Order follows value: Copilot Studio plus the 30 cases, then the video, then Fabric and SQL, then Power BI; Copilot Studio runs first against the local mode, so a Fabric block cannot stop it.
5. Estimated manual time: about 2 h (112 min of checklist plus about 5 min of approvals), 2.5 to 3 h if plan B is needed, against about 6 h today.

## 2. Distribution of the 46 steps of MANUAL_STEPS.md

Legend: **A** = Claude Code automates; **P** = Claude Code prepares, user runs; **M** = Manual. Step 42b is the extra step that MANUAL_STEPS.md lists after 42. Totals: A 22, P 13, M 12 (47 rows).

| # | Step (short) | Class | Tool or script (feature) | Source in docs/research/ |
|---|---|---|---|---|
| 1 | Python and venv | A | `phase_c_preflight` (PC-1), read-only | Local (repo commands) |
| 2 | Data and local artifacts | A | `main.py generate-data`, `load-db`, `index`, one heavy process at a time | Local (repo commands) |
| 3 | ODBC Driver 18 | A | PC-1 checks `pyodbc.drivers()`; Driver 18 is already installed on this machine (seen with `pyodbc.drivers()`); if missing, `winget install Microsoft.msodbcsql.18` needs the user to accept the UAC prompt | fabric-sql-from-python.md, Answer (Driver on Windows) |
| 4 | Entra authentication | P | User runs `fab auth login` and `az login` (browser, interactive); the service principal option is not planned | fabric-cli-and-rest.md, Answer (Auth in `fab`, Service principals) |
| 5 | Docker Desktop | M | Skipped by design: Phase C runs `main.py serve` from the venv; Docker is not needed and RAM/disk are tight | docker-desktop-disk-location.md (⚠ option may not appear with WSL2) |
| 6 | Power BI Desktop install | M | User installs it; no researched automation | None (MANUAL_STEPS step 6: download not researched) |
| 7 | Fabric free trial | M | UI only (Account manager > Start trial, ⚠ exact name); PC-2 probes the result with one `fab create` | fabric-access-without-m365-devprogram.md, Answer (a); fabric-cli-and-rest.md, Recommended decision |
| 8 | Ask the university admin | M | Conditional; the message text already exists in MANUAL_STEPS step 8 | fabric-access-without-m365-devprogram.md, Answer (a); fabric-cli-and-rest.md (Tenant and permissions) |
| 9 | Own Entra tenant | M | Conditional plan B; route not confirmed | fabric-access-without-m365-devprogram.md, Answer (b) (⚠) |
| 10 | F SKU capacity in Azure | M | Conditional last resort; price and eligibility not confirmed | fabric-access-without-m365-devprogram.md, Answer (c) (⚠) |
| 11 | Workspace, lakehouse, warehouse | A | `fab create` in `fabric_provision` (PC-2), idempotent, `--dry-run` | fabric-cli-and-rest.md, Answer (Create); Warehouse example not run (⚠) |
| 12 | Upload the CSVs to `Files/raw/` | A | `fab cp` in PC-2 | fabric-cli-and-rest.md, Answer (Upload to OneLake) |
| 13 | Import and run the notebook | P | User imports the `.ipynb` and pins the lakehouse (UI); Claude runs `fab job run` and `fab job run-status` (PC-3) | fabric-cli-and-rest.md, Answer (Notebook); `fab` notebook import and the REST `jobType` are ⚠ not confirmed |
| 14 | DDL of `dbo.tickets_nuevos` | A | `fabric_sql_run` (PC-4) over pyodbc with a token; DDL never run on a real Warehouse (⚠) | fabric-sql-from-python.md, Answer (pyodbc with a token) |
| 15 | Run the 10 SQL queries | A | PC-4 runs each file, saves CSV results and compares with business-case figures | fabric-sql-from-python.md, Answer (pyodbc with a token, Server and port) |
| 16 | Copy SQL endpoint and Warehouse hosts | A | `fab get ... -q properties.sqlEndpointProperties.connectionString` or the Get Lakehouse REST field, in PC-2 (query path not run, ⚠) | fabric-sql-from-python.md, Answer (Getting the connection string; By CLI) |
| 17 | Fill `.env` | A | PC-2 writes hosts, names and a generated demo API key to the git-ignored `.env`; it never prints the key and writes no Azure secret | fabric-sql-from-python.md, Recommended decision; local `.env.example` |
| 18 | `check_fabric` and `--write-test` | A | Existing `scripts/check_fabric.py`, output saved as evidence by PC-4 (⚠ never run on a real tenant) | fabric-sql-from-python.md (token scope ⚠ and fallback) |
| 19 | API in fabric mode | A | `main.py serve` started in the background by the PC-5 and PC-11 scripts | Local (repo command) |
| 20 | Public tunnel | P | User signs in once with `devtunnel user login -d`; Claude runs `create`, `port create`, `host` and parses the URL (PC-5) | dev-tunnels.md, Exact commands and Scriptable URL |
| 21 | `check_public_url` | A | Existing `scripts/check_public_url.py`, called by PC-5 | Local (repo script) |
| 22 | `export-openapi --host` | A | Existing command, called by PC-5 with the parsed host | Local (repo command); dev-tunnels.md (Scriptable URL) |
| 23 | Rotate the key | A | PC-5 `rotate` and `down` (rewrite `.env`, restart `serve`, `devtunnel delete`); the key is never printed | dev-tunnels.md, Recommended decision and Exact commands (cleanup) |
| 24 | Sign in to Copilot Studio | M | UI with the university account | copilot-studio-access-and-steps.md, Respuesta (Acceso) |
| 25 | Create the agent | P | PC-6 prints name, description and language values; user creates it (UI). `pac copilot init` is not used | copilot-studio-access-and-steps.md (a); power-platform-cli-copilot.md, Recommended decision |
| 26 | Paste the instructions | P | PC-6 copies `instructions.md` to the clipboard and reports its size (character limit is ⚠ not confirmed) | copilot-studio-agent-limits.md, Respuesta (a) (⚠) |
| 27 | Knowledge (optional) | M | Skipped: file upload is not confirmed and `buscar_solucion` already returns cited answers | copilot-studio-access-and-steps.md (b) (⚠); copilot-studio-trial-limits.md (⚠ knowledge upload) |
| 28 | REST API tool | P | PC-6 produces the final `openapi.json`, validates it offline and prints the exact wizard values; user runs the wizard and pastes the key | copilot-studio-access-and-steps.md (c); copilot-studio-openapi-requirements.md, Respuesta |
| 29 | MCP (optional) | M | Skipped; procedure not confirmed | copilot-studio-access-and-steps.md (f) (⚠) |
| 30 | Topics | P | PC-6 prints descriptions and trigger phrases; user creates only the Escalate edit plus 2 topics first, the other 5 only if a case fails | copilot-studio-agent-limits.md, Respuesta (c), (d), Decision |
| 31 | Smoke test | M | User types 3 prompts in the test panel and takes 3 captures | copilot-studio-access-and-steps.md (d) |
| 32 | Run the 30 cases | P | PC-7 builds the import CSV (`Question`, `Expected response`); user imports it in the Evaluation tab, runs it and exports; plan B is the chat, one case at a time | copilot-studio-trial-limits.md, Answer (native agent evaluation) (⚠ availability on trial) |
| 33 | Register results in the T32 table | A | `copilot_eval_import` (PC-8), maps the exported CSV to the table, never invents a verdict | copilot-studio-trial-limits.md, Answer (Results: exportable to CSV; column names ⚠ not confirmed) |
| 34 | Update README | A | Existing `scripts/update_readme_results.py` | Local (repo script) |
| 35 | Clean test tickets | M | Not needed when the cases run in local mode; if Fabric mode was used, a filtered `DELETE` in the query editor | None (no research; repo has no script for it) |
| 36 | Connect Power BI Desktop | P | PC-9 gives host, database name and mode (Import); user signs in | power-bi-fabric-connection.md, Respuesta (Opción A) |
| 37 | Build the report | P | PC-9 gives DAX measures and the page design; user builds and saves as PBIP | power-bi-pbip.md, Recommended decision |
| 38 | Record the video | P | PC-10 script and PC-11 demo runner; user records with Snipping Tool (`Win + Shift + R`) | demo-capture.md, Answer (Video) and Recommended decision |
| 39 | Screenshots | P | PC-12 renders the local ones from captured output; user takes the 8 UI ones (`Win + Shift + S`) | demo-capture.md, Answer (Screenshots of local things) |
| 40 | Learning log | M | Only the user knows what he did; Claude only formats what he dictates | None |
| 41 | Video link in README | P | User uploads and gives the URL; PC-13 edits the README line | demo-capture.md (recording only; hosting not researched, ⚠) |
| 42 | `update_readme_results --check` | A | Existing script, run in PC-13 | Local (repo script) |
| 42b | `validation-status.json` | A | PC-13 edits it only when the evidence file exists, then runs the script | Local (repo schema in `update_readme_results.py`) |
| 43 | Hand over the evidence | A | Not needed: Claude Code works in the same repo and session | Local |
| 44 | Push by PR | A | feature-loop step f, branch `feat/t36-evidencia-real`, CI green, user says "merge" | Local (`feature-loop` SKILL.md) |
| 45 | Tag `v0.1.0` | A | Obsolete: tags `v0.1.0` and `v0.1.1` already exist (`git tag`, checked while planning); a new tag is a user decision after T36 | Local (`git tag`) |
| 46 | Rotate key, close tunnel, clean `git status` | A | PC-5 `down`, then `git status` | dev-tunnels.md, Exact commands (cleanup) |

## 3. Features to develop (cycle a to f of the feature-loop skill)

Each feature goes through a) branch and issue, b) development, c) independent tests by `qa-tester` (never the developer), d) verification (`pytest --cov=src`, `ruff check .`, `ruff format --check .`, `mypy`), e) documentation (`docs/features/<name>.md`, CHANGELOG, roadmap `documentada`, `scratch/pr-body.md`), f) PR, CI, merge. [ALTO RIESGO] adds `security-verifier` (read-only). Branches follow [branch-and-feature-naming.md](research/branch-and-feature-naming.md). Sizes: S up to about 150 lines, M up to about 400, L more than 400 split into several commits of 400 lines or fewer.

All scripts share these rules: no credentials in any file (interactive sign-in or git-ignored `.env`; `git check-ignore .env` is verified before any write); every provisioning or writing script is idempotent (it lists before it creates) and has `--dry-run`; external tools run as subprocesses behind an injectable runner, so the tests use doubles and never touch a real tenant (the same approach as `scripts/check_fabric.py`); heavy tools are imported lazily; nothing prints tokens, keys or full connection strings (`describe()` pattern of `check_fabric.py`).

| # | Feature | Branch | One-line description | Specs / RF | Developer | Risk | Depends on | Size |
|---|---|---|---|---|---|---|---|---|
| PC-1 | preflight-check | `feat/pc-1-preflight-check` | Read-only `scripts/phase_c_preflight.py`: venv and Python, ODBC drivers, `az`/`fab`/`devtunnel`/`winget` on PATH, free space on C: and D:, free RAM, `.env` ignored and variable names present | S18, S22 | repo-architect | - | - | S |
| PC-2 | fabric-provision | `feat/pc-2-fabric-provision` | `scripts/fabric_provision.py`: probe with one `fab create`, then workspace, lakehouse, Warehouse, `fab cp` of the CSVs, hosts into `.env`; idempotent, `--dry-run` | S6, S22, RF-18 | data-engineer | [ALTO RIESGO] | PC-1 | M |
| PC-3 | fabric-notebook-run | `feat/pc-3-fabric-notebook-run` | `scripts/fabric_run_notebook.py`: start the notebook with `fab job run`, poll `run-status`, save the result as evidence; starts with a researcher spike for the ⚠ items | S6, S22 | data-engineer | [ALTO RIESGO] | PC-2 | S |
| PC-4 | fabric-sql-run | `feat/pc-4-fabric-sql-run` | `scripts/fabric_sql_run.py`: run `warehouse_ddl.sql` and the 10 queries through `FabricConnectionFactory`, save one CSV per query and a comparison with business-case figures, then `check_fabric` output | S5, S6, RF-18 | data-engineer | [ALTO RIESGO] | PC-3 | M |
| PC-5 | public-tunnel | `feat/pc-5-public-tunnel` | `scripts/public_tunnel.py up/down/rotate`: persistent Dev Tunnel, URL parsing, `check_public_url`, `export-openapi --host`, key rotation without printing; Cloudflare quick tunnel as documented plan B | S8, S16, RF-25 | api-engineer | [ALTO RIESGO] | PC-1 | M |
| PC-6 | copilot-paste-package | `feat/pc-6-copilot-paste-package` | `scripts/prepare_copilot_package.py` and `integrations/copilot_studio/PASTE-GUIDE.md`: offline OpenAPI check against the Copilot Studio requirements, clipboard of instructions, exact wizard values, minimal topic set; no `pac` | S11, RF-25 | copilot-studio-designer | [ALTO RIESGO] | PC-5 | M |
| PC-7 | copilot-eval-csv | `feat/pc-7-copilot-eval-csv` | `scripts/copilot_eval_export.py`: writes `tests/eval/copilot_studio_import.csv` with `Question` and `Expected response` from `cases.csv`, plus a blank results template for plan B | S11, S12 | rag-engineer | - | - | S |
| PC-8 | copilot-eval-import | `feat/pc-8-copilot-eval-import` | `scripts/copilot_eval_import.py`: reads the exported results CSV, fills the T32 table in `docs/testing-procedure.md`, runs `update_readme_results --dry-run`; developed after the first real export | S11, S12 | rag-engineer | - | PC-7 (and a real export) | M |
| PC-9 | powerbi-dax-design | `chore/pc-9-powerbi-dax-design` | `integrations/powerbi/measures.dax` and `report-design.md`: measures and a page design with the figures of `business-case.md`; no generated report | S22, RF-21 | docs-writer | - | PC-4 (to match the real columns) | S |
| PC-10 | video-script | `chore/pc-10-video-script` | `docs/demo-script.md`: 3-minute storyboard with timings, case ids, copy-paste prompts, recording checklist (30 s microphone test) | S14, S22 | docs-writer | - | PC-6 | S |
| PC-11 | demo-runner | `feat/pc-11-demo-runner` | `scripts/demo_run.py`: starts `serve`, runs the local part of the demo (health, search ES and EN, ticket, escalation, `eval` summary) with pauses and `--dry-run` | S8, S14, S16 | api-engineer | [ALTO RIESGO] | PC-5 | M |
| PC-12 | local-captures | `feat/pc-12-local-captures` | `scripts/capture_local.py`: renders captured command output (check scripts, `eval` summary, SQL comparison) to HTML and screenshots it into `docs/screenshots/`; optional, cut first | S14, S22 | api-engineer | [ALTO RIESGO] | PC-4, PC-11 | M |
| PC-13 | evidence-final (T36) | `feat/t36-evidencia-real` | Real results into README, business-case, testing-procedure, `validation-status.json`, video link and learning log; update the learning-log test; PR | S22 | docs-writer + security-verifier | [ALTO RIESGO] | PC-4, PC-8, PC-9, PC-10 | M |

[ALTO RIESGO] reasons: PC-2/PC-3/PC-4 handle Entra authentication and Fabric connections; PC-5 exposes the API publicly and rotates the key; PC-6 and PC-11 configure or use the API key; PC-12 may install Playwright (a download) and may capture secrets; PC-13 publishes evidence (security-verifier scan before push).

### Decisions and plan B per feature (with sources)

- **PC-1** is worth it: several rows of MANUAL_STEPS "Si falla" (3, 4, 8) are environment problems, and measured facts support it: C: has 7.3 GB free of 238 GB, `fab` and `devtunnel` are not installed yet, `az` and ODBC Driver 18 are. Source for the driver check: R2 (`pyodbc.drivers()`); for the cache path option: R7 (`PLAYWRIGHT_BROWSERS_PATH`).
- **PC-2** (R1): `fab auth login` is the interactive path for a university user; service principals need tenant switches a non-admin cannot change. First action is a single `fab create` to learn whether "Users can create Fabric items" is on (R1, Recommended decision). `ms-fabric-cli` 1.9.0 stays out of `requirements.txt` (R1). Plan B: no trial or no create right, then MANUAL_STEPS steps 8 to 10 and the whole Fabric block is deferred; Copilot Studio and the video do not depend on it.
- **PC-3** (R1): `fab job run`, `run-status` are documented. ⚠ not confirmed: `fab` import of a notebook, the REST `jobType` for notebooks (`RunNotebook`), that `run-status` accepts the job instance id, and pinning the default lakehouse by code. First commit is a `researcher` spike (rule "doubt means research"); until confirmed, the user imports and pins the notebook (5 min). The notebook has never run in Spark (MANUAL_STEPS step 13), so a failure is reported, not fixed silently.
- **PC-4** (R2): token approach is already in `src/utils/fabric.py`; scope `https://database.windows.net/.default` is ⚠ not confirmed (fallback with the double slash is in R2). The DDL and query 07 (`CAST(... AS VARCHAR(19))`) were never run on a real engine; differences from `business-case.md` (1.90, 79.50% vs 60.57%) are recorded and never edited. Plan B: paste the files in the portal query editor (MANUAL_STEPS steps 14 and 15). `sqlcmd` is not used (R2: use on Fabric not confirmed).
- **PC-5** (R5): `devtunnel create deskpilot -a --expiration 30d`, `port create`, `host`; a persistent tunnel keeps the URL stable. ⚠ not confirmed: tenant policy blocking Dev Tunnels for the university account, behavior with real Copilot Studio calls, `show --json`. Plan B: Cloudflare quick tunnel, then ngrok ([public-https-url-options.md](research/public-https-url-options.md)). Anonymous access means the API key is the only barrier: key rotated by the same script, `/docs`, `/redoc`, `/openapi.json` stay 404 (already checked by `check_public_url`).
- **PC-6** (R3, R4, `copilot-studio-openapi-requirements.md`): **`pac copilot` is evaluated and not used for the deliverable.** R3 says do not depend on it: not confirmed on a trial environment, needs a Dataverse environment and `pac auth create` that a university tenant may block, no documented import of our `.md` or `openapi.json`, and the place of the instructions in the YAML is ⚠ not confirmed. The UI path is documented end to end (`copilot-studio-access-and-steps.md`). The feature validates the OpenAPI offline (Swagger 2.0 JSON, under 1 MB, `host`, https, `securityDefinitions` apiKey header, no blank descriptions) and gives paste-ready text. ⚠ not confirmed on screen: REST tool on a trial (R4), instruction character limit, accepting `.yaml`.
- **PC-7** (R4): native Evaluation tab, test sets up to 100 cases, CSV with `Question` and `Expected response`, so the 30 cases fit. `esperado` codes become natural-language expectations by fixed templates (cite KB-xxx, refuse and offer a ticket, P1 plus a person attends, ticket category and priority, do not repeat the sensitive datum), recorded in the file header. The test method (compare meaning, keyword match, tool use) is chosen on screen from the R4 list. The agent authentication must be "No authentication" or "Authenticate with Microsoft" (R4). Cases run against the local mode so `crear_ticket` writes to SQLite, not to Fabric.
- **PC-8** (R4): the export format of results is ⚠ not confirmed, so the importer is built from the first real export, refuses unknown headers listing them, and never guesses a pass or fail. Plan B: the blank template from PC-7, filled from the screen.
- **PC-9** (R6): generating the report by code is possible but costly and untested, so only measures and a design are delivered; the TMDL semantic model is dropped (optional in R6). Licences: Desktop screenshots need only the free Desktop plus workspace access (⚠ not explicit); no publishing.
- **PC-10, PC-11** (R7): Snipping Tool for the video; ⚠ microphone not confirmed, hence the 30 s test and OBS as fallback. The demo runner prints terminal output only; Copilot Studio is shown live by the user.
- **PC-12** (R7): Playwright with `channel="msedge"` needs no browser download; install and RAM cost are ⚠ not confirmed and measured by the feature. `/docs` is off, so it screenshots an HTML rendering of captured output, which is labelled as "rendered from captured output" and is never presented as a real UI capture. Plan B: drop the feature and keep the text evidence.
- **PC-13** (T36): the existing `test_learning_log_is_template_only` fails once the log is filled; `qa-tester` updates it with a written justification. `validation-status.json` changes only per section 5.

### Evaluated and discarded

| Candidate | Decision and reason | Source |
|---|---|---|
| Run the Copilot Studio evaluation through the Power Platform API | Discarded: needs an app registration and admin consent (tenant-dependent) and trial availability is ⚠ not confirmed | R4, Answer (Automation) |
| Test through Direct Line or the Microsoft 365 Agents SDK | Discarded: both need a published agent and the trial cannot publish | R4, Answer (Needs publishing) |
| `pac copilot` to create or import the agent | Discarded for the deliverable (see PC-6); optional `clone` to version the agent only if `pac copilot list` works | R3, Recommended decision |
| Knowledge package for Copilot Studio | Discarded: file upload ⚠ not confirmed and `buscar_solucion` already returns cited answers | `copilot-studio-access-and-steps.md` (b) |
| MCP tool in Copilot Studio | Discarded: procedure ⚠ not confirmed; the REST tool covers the demo | `copilot-studio-access-and-steps.md` (f) |
| Generate the Power BI report (PBIR) or a TMDL model | Discarded: costly, untested, can break Desktop | R6, Conclusion and Recommended decision |
| Terminal GIF with VHS | Discarded: needs `ttyd` and `ffmpeg` (disk on a tight C:), Windows reliability ⚠ not confirmed | R7, Answer (Terminal GIF) |
| Separate script for Cloudflare or ngrok | Discarded: documented as plan B commands inside PC-5, no automation source for their Windows install | `public-https-url-options.md` (⚠ install) |
| Service principal for Fabric | Discarded: needs tenant switches and app registration a non-admin cannot get | R1, Answer (Service principals) |
| Script to delete test tickets | Discarded: the cases run in local mode, so there is nothing to clean | MANUAL_STEPS step 35 |
| Moving the Docker disk image | Discarded: Docker is not used in Phase C | `docker-desktop-disk-location.md` |

### Execution order

Priority is the value for the vacancy: Copilot Studio plus the 30 cases first, then video, then Fabric and SQL, then Power BI.

```
PC-1 -> PC-5 -> PC-6 -> PC-7 -> [live: tunnel and Copilot Studio block] -> PC-8
PC-10 -> PC-11                                  (video, after PC-6 and PC-5)
PC-2 -> PC-3 -> PC-4 -> PC-9 -> PC-12           (Fabric and Power BI, after the trial exists)
PC-13 last (T36), needs PC-4, PC-8, PC-9, PC-10
```

One subagent at a time and no Docker or reranker in parallel (RAM 7.8 GB, feature-loop rule). The development phase needs no user time except permission prompts.

## 4. Reduced manual checklist (user), in exact order

Each row ends with the point where control returns to Claude Code. Nominal path, estimates only.

| Order | What the user does | Min | Return of control (type this) |
|---|---|---|---|
| U1 | Approve permission prompts during development (installs of `fab`, `devtunnel`, merges); no other action | 5 | Nothing; Claude continues |
| U2 | In PowerShell: `devtunnel user login -d`, `fab auth login`, `az login` (browser sign-ins with the university account, MFA if asked) | 6 | `sign-ins done: continue with PC-5` |
| U3 | Fabric portal: Account manager > Start trial; one screenshot (`01-fabric-trial-activo.png`). If there is no button: tell Claude, plan B | 6 | `trial ready: continue with PC-2` (or `no trial button`) |
| U4 | Copilot Studio: sign in with the university account and accept the trial | 3 | `copilot signed in: continue with PC-6` |
| U5 | Create the agent from the printed values; add Spanish as primary and English as secondary; paste the instructions from the clipboard | 7 | `agent created` |
| U6 | REST API tool wizard from the printed values; paste the key from the clipboard when creating the connection; one capture (`09`) | 8 | `tool added` |
| U7 | Edit Escalate and create the 2 minimal topics (the other 5 only if a case fails) | 10 | `topics done` |
| U8 | Smoke test: 3 prompts, captures `10`, `11`, `12` | 5 | `smoke test ok: continue with PC-7` |
| U9 | Evaluation tab: import `tests/eval/copilot_studio_import.csv`, pick the methods, run, export the results CSV, capture the result page (`13`) | 8 | `eval exported: continue with PC-8, file <path>` |
| U10 | Fabric: import `01_load_tickets_delta.ipynb`, pin the lakehouse as default; one capture of the workspace items (`02`) | 6 | `notebook imported: continue with PC-3` |
| U11 | Power BI Desktop: connect with Entra, build the report from `report-design.md`, save as PBIP, captures `14` and `15` | 25 | `powerbi done: continue with PC-9 review` |
| U12 | Video: 30 s microphone test, record the script (`Win + Shift + R`), upload unlisted, send the URL | 17 | `video at <url>: continue with PC-13` |
| U13 | Dictate in 3 lines what you really did for the learning log | 5 | `log facts: <text>` |
| U14 | Review the final PR diff and say `merge`; decide whether to tag `v0.2.0` | 6 | `merge` |

Total nominal: 112 min plus the 5 min of U1 is 117 min (about 2 h). Plan B adds: evaluation through the chat about 40 min, admin request or tenant about 15 min of the user's time (waiting not counted). Range 2 to 3 h.

Steps that disappear from the user's list (class A in section 2): 1 to 3, 11, 12, 14 to 19, 21 to 23, 33, 34, 42 to 46.

## 5. Checkpoints, evidence and `validation-status.json`

Evidence lives in `docs/evidence/` (new folder, text files, hosts and ids redacted, no tokens or keys) and `docs/screenshots/`. Creating these folders is recorded in the ODD Log by the first feature that adds them. `security-verifier` scans every evidence file before each push.

| Checkpoint | After | Verification | Evidence left | `validation-status.json` |
|---|---|---|---|---|
| CP-0 | PC-1 | Preflight exits 0 or lists each missing item with its fix | Console output (not committed) | No change |
| CP-1 | PC-5 live (U2) | `check_public_url` exits 0 on the tunnel URL; `openapi.json` has the real host | `docs/evidence/public-url-check.txt` | No change |
| CP-2 | PC-6 | Offline validator exits 0; instruction size printed | Validator output in the PR | No change |
| CP-3 | U5 to U8 | The 3 prompts reach `buscar_solucion` through the tool (answer with citation) | Captures `09` to `12` | `copilot_studio` stays `pendiente`; `que_falta` updated |
| CP-4 | U9 and PC-8 | 30 rows imported with a verdict; `update_readme_results --check` exits 0 | `tests/eval/copilot_studio_results.csv`, T32 table, capture `13` | `copilot_studio` becomes `validado` with date and evidence only if the REST tool answered and all 30 cases have a verdict; otherwise `que_falta` states what is left |
| CP-5 | PC-2 to PC-4 live | Items exist (`fab ls`), notebook job finished, 10 results compared with `business-case.md`, `check_fabric --write-test` exits 0 | `docs/evidence/fabric/` (provision, notebook run, one CSV per query, comparison, check output), capture `02` | `fabric` becomes `validado` only when all five hold; any difference from the business case is written in `que_falta` and in the ODD Log |
| CP-6 | U11 | Power BI figures equal the CP-5 comparison | Captures `14`, `15`, PBIP folder | `power_bi` becomes `validado` with the capture path |
| CP-7 | U12 | Anonymous `curl -I` of the video URL returns 200 (a login or consent redirect means not validated) | URL in README | `video` becomes `validado` with the URL |
| CP-8 | PC-13 | `update_readme_results --check` exits 0; `pytest --cov=src`, `ruff`, `mypy` clean; security-verifier scan; CI green | PR | The schema rejects `validado` without date and evidence; the README blocks RESULTS, VALIDATION and MSBADGES regenerate with `update_readme_results` |

Rule: Claude edits the JSON only after the evidence file exists; a captured-output rendering (PC-12) never counts as the evidence of a UI step.

## 6. Risks and plan B

| Risk | Signal | Plan B | Time effect |
|---|---|---|---|
| University account without tenant rights | `fab create` is refused, or no "Start trial" button | Admin message (MANUAL_STEPS step 8), own tenant (step 9), F SKU (step 10, may cost, ⚠); meanwhile Copilot Studio and the video run in local mode and the Fabric rows of the README stay `pendiente` (honest) | +15 min of the user, rest deferred |
| Fabric trial unavailable | R1 and R2 features fail at the probe | PC-3, PC-4, PC-9 and the Fabric scenes of the video are dropped; the local SQLite figures stay as the evidence of the business case | Saves about 40 min |
| Dev Tunnels blocked for the account, or unstable | `devtunnel` login fails, or `check_public_url` times out | Cloudflare quick tunnel, then ngrok; `check_public_url --timeout`; a dry run of the Copilot Studio call before recording (R5) | +5 min |
| Copilot Studio does not accept the OpenAPI | Wizard rejects the file | Re-export with `--host`; PC-6 validator names the failing rule; if the REST tool is unavailable on the trial (⚠ R4), keep the agent with instructions only and record the limit in the README | +10 min |
| Evaluation tab missing on the trial (⚠ R4) | No Evaluation tab | Run the 30 cases one by one in the test chat with the clipboard helper of PC-7; results by the blank template to PC-8 | +40 min |
| Poor space on C: | PC-1 reports under 2 GB free | Do not install optional tools; Playwright with `msedge` (no download); drop PC-12; no Docker; caches with `PLAYWRIGHT_BROWSERS_PATH` on D: (⚠ speed not measured, R7) | None |
| RAM 7.8 GB | Slow, swap, or the API fails to start | One heavy process at a time; `retrieval.rerank.enabled: false` in `config.yaml` only as a documented fallback, and then the "EV-16" rejection claim changes (it relies on the reranker veto) | None |
| `az login` and `fab` sessions do not share tokens | `check_fabric` fails the token step after `fab auth login` | Keep both logins (U2); fallback scope with the double slash (R2) | None |
| Learning-log test fails | `test_learning_log_is_template_only` red | `qa-tester` updates it with justification in PC-13 | None |

## 7. What cannot be automated, and why

| Item | Why | Source |
|---|---|---|
| Entra sign-ins and MFA (`fab`, `az`, `devtunnel`, portals, Power BI) | Interactive by design; the plan also forbids storing credentials in files | R1 (Auth in `fab`), R5 (Login) |
| Fabric trial and tenant switches | Controlled by the tenant or a Fabric admin; a non-admin cannot change them | R1 (Tenant and permissions); `fabric-access-without-m365-devprogram.md` |
| Notebook import and default lakehouse pin | No documented `fab` command; ⚠ not confirmed | R1 |
| Creating the agent, topics and REST tool in Copilot Studio | The UI is the documented path; `pac copilot` is not confirmed on a trial and cannot import our files | R3; `copilot-studio-access-and-steps.md` |
| Running the native evaluation | UI tab; the API route needs an app registration and consent, and chat routes need a published agent | R4 |
| Building the Power BI report | Generation by code is costly and untested | R6 |
| Recording the video and the microphone | A human action; microphone support ⚠ not confirmed | R7 |
| Screenshots of authenticated UIs (Fabric, Copilot Studio, Power BI) | No researched automation source | None |
| Video hosting and the learning log | Hosting not researched; the log must contain only what the user did | None; MANUAL_STEPS step 40 |
| Tenant admin requests | A person decides | R1 |
