# Copilot Studio trial limits and automated testing (R4)

Consulted: 2026-11-22. Max 3 official Microsoft sources. "⚠ not confirmed" = not stated in the cited sources.

## Question
What does the Copilot Studio trial allow or not (publish, test, REST/OpenAPI or MCP tools, knowledge files, solution export)? Can we run our test cases automatically WITHOUT publishing the agent, and can we run a batch of questions and export results?

## Answer
- Trial (work/school account only): create agents and test them in the test chat panel; "you can't publish the agent". The trial can be extended by 30 days; agents keep working up to 90 days after expiry. Premium connectors and any channel need the standalone subscription.
- Not confirmed for the trial: REST/OpenAPI tool, MCP tool, uploading knowledge files, exporting a solution, and running agent evaluation. ⚠ not confirmed (the licensing page only ties premium connectors to the standalone plan).
- Native agent evaluation (Evaluation tab): test set of up to 100 cases; CSV/TXT import with columns `Question`, `Expected response` (question max 1,000 chars; expected response optional but needed for match/similarity/compare-meaning). Methods: general quality, compare meaning, keyword match, tool use, text similarity, exact match, custom, content safety. Runs as the signed-in user.
- Results: pass/fail per case, kept 89 days in the UI, exportable to CSV. Our 30 cases in `tests/eval/cases.csv` fit the limit but need column mapping to `Question` / `Expected response`.
- Automation: Power Platform API (`api.powerplatform.com/copilotstudio/environments/{env}/bots/{bot}/api/makerevaluation/testsets` and `.../testsets/{id}/run`, `.../testruns`) starts a run and returns per-case results. It needs a Microsoft Entra user token from an app registration with Power Platform API permission; on a university tenant this may need admin consent (⚠ tenant-dependent). The cited pages do not state that evaluation requires publishing. Whether evaluation is available on a trial licence: ⚠ not confirmed.
- Needs publishing (read on two further official pages, not counted in the 3-source cap): the Microsoft 365 Agents SDK client and Direct Line require a published agent; Copilot Agent Kit tests run against the published agent, while Copilot Studio evaluations "don't require the agent to be published". With a trial that cannot publish, these routes are unavailable. Add those two pages to sources if the lead allows a 4th/5th source.
- Evaluation limits: agents set to "Authenticate manually" and Fabric data agents are unsupported; tools needing authentication require a working connection for the signed-in user.

## Recommended decision
Use the native Evaluation tab with the 30 cases imported as CSV (map `tests/eval/cases.csv` to `Question`, `Expected response`) and export results to CSV into `tests/eval/` as evidence. Set agent authentication to "No authentication" or "Authenticate with Microsoft". Keep REST/CI automation optional, only if app-registration consent is obtainable. The repo's Python `eval` against the FastAPI API stays the main reproducible metric; the Copilot Studio run is the demo-facing check. Confirm on screen that the trial shows the Evaluation tab and accepts the REST tool before the demo.

## Sources
| Title | URL | Consulted |
| --- | --- | --- |
| Get access to Copilot Studio | https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-licensing-subscriptions | 2026-11-22 |
| Create a single response test set (agent evaluation) | https://learn.microsoft.com/en-us/microsoft-copilot-studio/analytics-agent-evaluation-create | 2026-11-22 |
| Automate evaluations with the Power Platform API | https://learn.microsoft.com/en-us/microsoft-copilot-studio/analytics-agent-evaluation-rest-api | 2026-11-22 |
