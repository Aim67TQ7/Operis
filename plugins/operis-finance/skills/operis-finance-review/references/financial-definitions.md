# Financial definitions and evidence requirements

| Measure | Definition | Evidence needed |
|---|---|---|
| Recognized revenue | Net revenue on the approved accounting basis | Posting/recognition status, credits, period and sign mapping |
| Gross profit | Revenue minus corresponding cost of goods sold | Matched revenue and COGS basis; any excluded cost clearly identified |
| Gross margin | Total gross profit / total revenue × 100 | Zero revenue means undefined; use weighted totals |
| Amount change | Current amount minus prior amount | Same company, currency and comparison basis |
| Percentage change | Amount change / prior amount × 100 | Undefined when prior amount is zero; flag negative-base interpretation |
| Margin change | Current margin minus prior margin | Express in percentage points, not percentage growth |
| Backlog | Open orders on the approved order-status basis | Snapshot/as-of time, cancellations, outstanding quantities and duplicated releases |
| Posted AP | Unpaid posted liabilities on the stated as-of date | Balance, due date, credits, payments and posting status |
| PO commitment | Approved remaining purchasing obligation | Open/unreceived quantities and status; treatment of received/uninvoiced lines |
| AR aging | Outstanding receivables grouped by aging basis | Snapshot date, due/invoice-date choice, credits and payment allocations |
| Cash forecast | Timing model of inflows and outflows | Opening cash, expected collections, payment assumptions and scenario horizon |

Do not equate backlog with recognized revenue, AP with all future spending,
or a purchasing commitment with a paid transaction. Do not add overlapping PO,
receipt and invoice stages without identifying and reconciling their overlap.

For product-line variance, distinguish a change in total gross profit from a change
in gross-margin percentage. A product line can add profit while lowering aggregate
margin through mix. Price/volume/mix attribution requires consistent quantities,
prices and cost units; otherwise report the measured segment changes only.

Normalize canonical margin amounts to signed net recognized revenue and signed net
COGS expense. Credits/reversals may be negative. Do not invert GL signs without
verified account mappings. `record_id` must identify a unique source line within
the company, not an invoice header repeated across many lines. Use a separate input
for alternative snapshots of the same source record; never count both revisions.

Use fiscal labels as supplied by the source. Do not assume fiscal period 09 is
September or assume a 12-period calendar. Normalize currencies to approved codes.
Separate entity and currency totals. FX conversion requires a named rate source,
date and method. A missing period is missing evidence, not a zero balance.
