# OPERIS Finance

A first OPERIS plugin for manufacturing financial review. It explains financial
changes from the customer's own data, with a reusable analysis workflow and a
deterministic gross-margin calculator. It does not contain customer records,
credentials, a preselected ERP connection, or a background model loop.

## What this release does

- Compare recognized revenue, COGS, gross profit and weighted gross margin by period.
- Guide AR/AP and purchasing-exposure reviews without adding overlapping liabilities.
- Prepare a concise, source-backed management briefing.
- Analyze the user's supplied exports, or use a separately configured customer MCP
  after authentication and scope verification.

The calculator handles normalized margin CSV only; other datasets are analyzed by
the skill using their verified definitions. A configured MCP URL is not proof that
live financial tools or customer isolation work. Server permissions must enforce
read-only access and customer boundaries. This package does not implement ERP
connectors, tenant provisioning, billing or production authentication.

## Install the base plugin

The repository marketplace is `.agents/plugins/marketplace.json`; the package is
`plugins/operis-finance/`. On a supported local Codex/ChatGPT desktop surface,
open this repository and select OPERIS Finance from its marketplace. Complete
the install and test it in a new conversation. On Codex CLI, use `/plugins`.

For ChatGPT web/workspace distribution, use Plugin Creator or your workspace's
plugin import process with this package. Availability depends on workspace
permissions. Register a customer MCP connection separately if live access is
needed; a repository package is not automatically installed in ChatGPT web.

Official references:
- https://developers.openai.com/plugins/build/plugins
- https://learn.chatgpt.com/docs/build-plugins
- https://developers.openai.com/plugins/build/auth

The base package works with supplied exports and deliberately has no `mcp.json`
or `.app.json`. Keep it this way for distribution.

## Configure a customer's live connection

Obtain that customer's approved, authenticated, read-only MCP endpoint. Create a
separate customer copy outside this source folder:

```sh
python3 plugins/operis-finance/scripts/configure_customer.py \
  --endpoint "$CUSTOMER_FINANCE_MCP_URL" \
  --output /absolute/path/customer-operis-finance
```

For an existing ChatGPT-registered MCP connection, also supply
`--registered-app-id "$CUSTOMER_REGISTERED_MCP_APP_ID"`. The script writes the
portable Streamable HTTP MCP configuration and, when supplied, a registered app
mapping. Authentication happens through the MCP client; do not embed bearer
tokens, ERP passwords or secrets in the package. Do not commit customer copies.

Before selling a live installation, verify authenticated company/role scope,
read-only tool restrictions, cross-company denials, revocation, source freshness,
complete pagination, and one reconciled financial question against the customer's
trusted report. Never substitute another customer's endpoint to get a test to pass.

## Try the synthetic example

All fixture amounts and company labels are synthetic.

```sh
python3 plugins/operis-finance/skills/operis-finance-review/scripts/margin_review.py \
  plugins/operis-finance/tests/fixtures/synthetic-margin.csv \
  --current FY2026-P09 --prior FY2026-P08
```

Expected: revenue remains 150,000 USD; gross profit falls from 65,000 to 51,000;
gross margin falls from 43.33% to 34.00%, a 9.33 percentage-point decline.
Equipment loses 4,000 in gross profit; Replacement Parts loses 10,000.
Price/volume/mix causes remain unproven
because the fixture lacks quantity and unit-price data.

Example request: "Use OPERIS Finance to explain the change in these two periods.
Separate measured changes from explanations that need more evidence."

## Validate

```sh
python3 -m unittest discover -s plugins/operis-finance/tests -v
```

These checks validate package structure, endpoint configuration and calculator
behavior. They do not establish a native ChatGPT install or a live ERP connection.

## Commercial pilot

The proposed paid service is customer ERP onboarding plus ongoing financial review
and support. Plugin access is the interface, not the entire service. Start with one
recurring question and verify the result against the customer's trusted report.
Measure analyst time saved, reconciliation errors, usage and willingness to pay.
Price and demand are not validated by this release. Each customer requires their
own data rights, connection and onboarding; this package provides no shared dataset.

Before public publication, supply approved support/privacy/terms information,
complete platform review requirements and verify the promised live workflow. The
source package intentionally omits invented legal URLs and claims of readiness.
