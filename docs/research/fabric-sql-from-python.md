# Connecting to Fabric SQL (lakehouse endpoint and Warehouse) from Python and sqlcmd

Consulted: 2026-11-22. Branch: chore/phase-c-plan.

## Question
How do pyodbc and sqlcmd connect to the SQL analytics endpoint of a lakehouse and to a Warehouse (ODBC Driver 18, connection string, `ActiveDirectoryInteractive`, token with azure-identity)? Which Windows driver must be installed and how (winget id)? How is the SQL connection string obtained through API or CLI?

## Answer
- **Server and port**: both items expose a "SQL connection string" of the form `<unique-id>.datawarehouse.fabric.microsoft.com`, TDS on TCP 1433. Pass the item name (lakehouse or Warehouse) as `DATABASE`. Only Microsoft Entra authentication works (SQL authentication is not supported) and ODBC 18 or higher is required (stated on the Fabric "How to connect" and "Connectivity" pages, not logged here because of the 3-source cap).
- **pyodbc, interactive** (Microsoft sample, Entra Interactive): `DRIVER={ODBC Driver 18 for SQL Server};SERVER=<sql-connection-string>;DATABASE=<item name>;UID=<user@university.edu>;Authentication=ActiveDirectoryInteractive`. The doc sample also lists `PWD=<Secret>`; for interactive login it should not be needed (⚠ driver-level behavior not confirmed in the cited page). A browser window opens for the Entra sign-in and MFA. Other modes: `ActiveDirectoryServicePrincipal` (UID = client id, PWD = secret) and `ActiveDirectoryPassword` (MFA must be off).
- **pyodbc with a token** (what `src/utils/fabric.py` does): get a token with azure-identity for `https://database.windows.net/.default`, pass it as `SQL_COPT_SS_ACCESS_TOKEN` (1256) and leave `UID`, `PWD` and `Authentication` out (confirmed locally with Driver 18: using both fails with FA005). Scope acceptance by Fabric is ⚠ not confirmed against a real tenant (pending T30); fallback `https://database.windows.net//.default`.
- **Access needed**: the user needs a workspace role (any of Admin, Member, Contributor, Viewer is enough to connect) or item-level permission. Service principals additionally need the tenant switch "Service principals can use Fabric APIs".
- **Driver on Windows**: Microsoft ODBC Driver 18 for SQL Server, latest 18.7.1.1 (released 2026-09-07 per the Microsoft download page); `winget install Microsoft.msodbcsql.18` (id and version seen in `winget search "ODBC Driver"` on this machine; install not executed). From 18.7 the installer bundles the VC++ runtime. A `...\Client SDK\ODBC\180\Tools\Binn\sqlcmd` already exists on this machine, so Driver 18 is probably installed (⚠ check with `python -c "import pyodbc; print(pyodbc.drivers())"`).
- **sqlcmd**: two variants. ODBC `sqlcmd`: `sqlcmd -S <host> -d <item> -G -U user@university.edu -l 30 -Q "SELECT 1"` (put `-G` before `-U`; `-G` with a user and no password means interactive). Go `sqlcmd` (winget `Microsoft.Sqlcmd`, 1.10.0 listed): `sqlcmd -S <host> -d <item> --authentication-method ActiveDirectoryInteractive -U user@university.edu`. Both docs describe Azure SQL and Synapse; use against Fabric is ⚠ not confirmed in the cited pages and untested.
- **Getting the connection string by API**: `GET /v1/workspaces/{workspaceId}/lakehouses/{lakehouseId}` returns `properties.sqlEndpointProperties.connectionString` (plus `id` and `provisioningStatus`: `InProgress`, `Success`, `Failed`; wait for `Success`). `GET .../warehouses/{warehouseId}` returns `properties.connectionString` (read on the Get Warehouse page, not logged because of the cap). Scopes `Lakehouse.Read.All` or `Item.Read.All`.
- **By CLI**: `fab get ws1.Workspace/lh1.Lakehouse -q properties.sqlEndpointProperties.connectionString` (⚠ query path not run). Alternative in the portal: item Settings > SQL connection string.

## Recommended decision
Keep the existing token approach for the app (no secrets in the connection string) and use `Authentication=ActiveDirectoryInteractive` only for manual checks by the human user. Install the driver with `winget install Microsoft.msodbcsql.18` if `pyodbc.drivers()` lacks it. Read the server name from the REST or `fab get` output into `.env` (`FABRIC_SQL_ENDPOINT`) instead of copying it by hand, and wait for `provisioningStatus == Success`. Treat sqlcmd on Fabric as an optional convenience.

## Sources
- Microsoft Entra authentication in Fabric Data Warehouse (connection strings, modes, tenant and workspace settings): https://learn.microsoft.com/en-us/fabric/data-warehouse/entra-id-authentication, consulted 2026-11-22
- Authenticate with Microsoft Entra ID in sqlcmd (Go and ODBC variants): https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-authentication, consulted 2026-11-22
- Items - Get Lakehouse (Fabric REST API; `sqlEndpointProperties.connectionString`): https://learn.microsoft.com/en-us/rest/api/fabric/lakehouse/items/get-lakehouse, consulted 2026-11-22

Confidence: medium (strings and fields confirmed in docs; driver version and winget id seen locally; no live Fabric connection made).
