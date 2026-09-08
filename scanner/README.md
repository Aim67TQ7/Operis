# Operis Epicor Discovery Kit 0.3.0

This is a limited, assisted assessment kit for Epicor REST v2. It does not certify ERP health, GL accuracy, savings, or security. It does not support SyteLine.

1. In Operis Discovery, select your company. Its code must match the Epicor company code.
2. Download the kit ZIP and extract it to a new folder.
3. Download the company scan configuration and save it beside `epicor_discover.py` as `operis-scan-config.json`.
4. On a machine with Python 3.10+ and access to Epicor, run `Run-Discovery.cmd` (Windows). On macOS/Linux run `python3 epicor_discover.py` in that folder.
5. Enter the HTTPS application URL and an existing authorized API key and account. Secrets are entered hidden. Use a read-only account with the required metadata/count permissions. The program only issues GET requests; it cannot establish whether your account has write privileges.
6. Review the new ZIP in `results/` and upload it to the same company in Operis. A failed preflight creates no package. Old packages are retained; use the filename printed by the successful run.

## Collection and limits

The scanner makes at most 16 GET requests, with 20-second request timeouts and a 4 MiB response cap. It checks the company identity using one explicitly selected field, then requests counts for BAQs, BPM methods, functions, reports, dashboards, scheduled tasks and AP invoices. It reads OData metadata for AP, vendors, purchasing and receipts to count entity types, fields and custom fields. Counts reflect the account's permissions, not necessarily the full ERP estate. Some counts may be system-wide; they do not establish company ownership of every object. AP invoice count is all records visible to that account, not a monthly workload estimate.

Only aggregate integers, fixed coverage statuses, company binding, timestamps and checksums are exported. No invoice/vendor records, monetary amounts, definitions, user names, endpoint URLs, credentials, raw responses, SQLite databases, or error excerpts are exported. Metadata responses are reduced in memory. There is no unselected fallback, definition capture, redirect following, TLS bypass, or automatic upload. Your organization can supply its trusted CA with `--ca-file`.

The ZIP contains exactly manifest.json, summary.json, self_evaluation.json and opportunities.md. The latter two are fixed placeholders; the server computes findings. The manifest's credential flag and checksums are not proof that arbitrary files are safe or that reported counts are true. Operis validates an exact schema and only retains normalized aggregate data. Customers can edit reports; all findings require validation with the customer.

The signed company configuration expires after seven days. It identifies the selected Operis tenant/company and must not be edited. Use a new configuration if expired or if the company code changed. This kit produces schema 1 packages; older prototype ZIPs are not accepted.

No installation or background service is created. Delete the extracted kit, configuration and results to remove local files. Operis retains accepted aggregate assessments and audit evidence in the selected organization; no raw upload ZIP is retained by this release. Pilot requests are saved for an administrator to review; no email or ERP action is sent automatically.

## Provenance and verification

Probe targets and metadata counting derive from the supplied v0.1 scanner. The v0.2 ZIP was referenced in an earlier conversation but was not recovered; this is a new reviewed v0.3 implementation. Windows launcher and real ERP verification receipts are maintained in the repository's docs/DISCOVERY.md. An offline test is not proof of a Windows/Epicor run.
