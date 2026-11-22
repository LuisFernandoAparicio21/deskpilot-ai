# Dev Tunnels CLI: persistent public HTTPS URL for the local API

Consulted: 2026-11-22. Branch chore/phase-c-plan. Extends `public-https-url-options.md` (which only had the quick `host` command).

## Question
How do I install and use the Microsoft Dev Tunnels CLI (`devtunnel`) on Windows to expose the local API (port 8000) through a persistent public HTTPS URL, with anonymous access, and how stable is it for Copilot Studio calls (limits, expiration, login, anti-phishing page)?

## Answer
- **Install** (PowerShell 5.1): `winget install Microsoft.devtunnel`, then reopen the terminal. Check with `devtunnel --version`. (winget id is from the earlier get-started page; the CLI reference only says to keep the CLI updated.)
- **Login** is required to create and host. `devtunnel user login` accepts a Microsoft account or a Microsoft Entra ID (organization) account; `-g` uses GitHub; `-d` uses device-code login. A university Entra account should work as an "organization" account, but a tenant policy that blocks the Dev Tunnels app is possible: ⚠ not confirmed.
- **Persistent tunnel**: `devtunnel host` with no tunnel ID creates a temporary tunnel deleted on exit. `devtunnel create` makes a persistent one; reusing it keeps the web-forwarding URL stable. Expiration is a sliding window of inactivity, from 1h to 30d (`--expiration 30d`). The 30-day default is from the FAQ page, which is outside the 3 cited sources (⚠ not re-verified there).
- **Access**: private by default (only the creating account). `--allow-anonymous` (`-a` on `create`) adds an anonymous access entry; anyone with the URL can connect. Alternative without anonymous access: `devtunnel token <id> --scopes connect` and send header `X-Tunnel-Authorization: tunnel <TOKEN>` (tokens last about 24 hours; whether Copilot Studio can send that header: ⚠ not confirmed).
- **Limits** (reset monthly): 5 GB bandwidth per user, 10 tunnels per user, 1000 active connections per port, 10 ports per tunnel, 1500 HTTP requests/min per port, up to 20 MB/s per tunnel, 16 MB max request body. No request timeout value is published: ⚠ not confirmed. The service is in public preview with no SLA, and the tunnel only works while `devtunnel host` is running on your PC (sleep or network loss drops it).
- **Anti-phishing page**: shown only on the first visit to the URL and skipped when the method is not `GET`, the `Accept` header lacks `text/html`, or the request has `X-Tunnel-Skip-AntiPhishing-Page` or `X-Tunnel-Authorization`. So JSON API calls (POST, or GET with `Accept: application/json`) are not affected; opening the URL in a browser is. Behavior with Copilot Studio's real requests: ⚠ not tested.
- TLS: HTTP is upgraded to HTTPS (HSTS), TLS 1.2 minimum, terminated at the Microsoft ingress.

## Exact commands (PowerShell 5.1)
```powershell
devtunnel user login -d                         # once; add -g for GitHub
devtunnel create deskpilot -a --expiration 30d  # persistent, anonymous access
devtunnel port create deskpilot -p 8000 --protocol http
devtunnel host deskpilot                         # keep this window open
```
- `devtunnel show deskpilot` lists details; `devtunnel list` lists yours; cleanup: `devtunnel delete deskpilot`.
- Does `devtunnel host <id>` accept `--allow-anonymous` on an existing tunnel? Not documented: use `-a` on `create`, or `devtunnel access create deskpilot --anonymous`.
- Port protocol: `http` for the local uvicorn server (`https` only if the local server itself uses TLS).

## Scriptable URL
`host` prints a line like `Hosting port 3000 at https://l3rs99qw-3000.usw2.devtunnels.ms/` (documented format). Parse it:
```powershell
$p = Start-Process devtunnel -ArgumentList 'host','deskpilot' -NoNewWindow -PassThru `
     -RedirectStandardOutput "$env:TEMP\dt.out"
Start-Sleep 8
$url = (Select-String -Path "$env:TEMP\dt.out" -Pattern 'https://\S+devtunnels\.ms/?').Matches[0].Value
```
Then put `$url`'s host in `integrations/copilot_studio/openapi.json`. Whether `devtunnel show <id>` has a machine-readable `--json` option: ⚠ not confirmed in the cited pages (check `devtunnel show -h`). The exact output text of `host` beyond the documented line: ⚠ not confirmed.

## Recommended decision
Create one persistent tunnel (`devtunnel create deskpilot -a --expiration 30d`, port 8000) once and reuse it, so the URL stays the same between demo sessions. Protect the API with a rotating demo API key (anonymous means the key is the only barrier). Keep Cloudflare quick tunnel as plan B. Do a dry run of the Copilot Studio tool call before recording the demo. Do not rely on it for anything beyond the demo (preview, no SLA).

## Sources
- Dev tunnels command-line reference. https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/cli-commands (consulted 2026-11-22)
- Dev tunnels security. https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/security (consulted 2026-11-22)
- Azure subscription and service limits, section "Dev tunnels limits" (aka.ms/devtunnels/limits redirects here). https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits#dev-tunnels-limits (consulted 2026-11-22)
