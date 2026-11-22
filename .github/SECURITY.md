# Security policy

## Scope

DeskPilot AI is a portfolio project. All data is synthetic (fictional bank "Banco Altiplano"); the repository holds no real customer, employee or tenant data.

## Supported versions

Only the latest release receives fixes.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability):

1. Open the repository's **Security** tab (shown as "Security and quality" in the current GitHub UI).
2. Click **Report a vulnerability** and fill in the form (summary, details, proof of concept, impact).
3. Submit the report.

The report stays private between you and the maintainer until a fix is ready. This is a personal project, so there is no response-time guarantee; I will answer as soon as I can.

## What is not a vulnerability

- Synthetic data in `data/` and in the knowledge base (it is fake by design).
- Example keys and placeholders in tests and in `.env.example` (they are not real credentials).

## Secrets

No secrets are published in this repository. If you find something that looks like a real credential, report it privately as described above; do not post it publicly.
