# Operis Universal Signal, Case & Decision Architecture

Status: architecture baseline for implementation on `build/universal-case-kernel`.

## Purpose

Operis is a configurable business decision operating layer above existing systems of record. It connects to ERP, CRM, email, quality, maintenance, finance, communications, files, APIs and other business sources; interprets operational activity; determines when a decision is required; creates or updates a Case; assembles evidence; supports or executes the decision; monitors the outcome; and learns from the result.

The universal flow is:

```text
SYSTEMS OF RECORD
      ↓
FACTS + EVENTS
      ↓
INTERPRETATION
      ↓
SIGNAL / EVIDENCE / RESPONSE
      ↓
CASE
      ↓
DECISION
      ↓
ACTION / PROCESS
      ↓
OUTCOME
      ↓
LEARNING
```

The Case is the operational spine of Operis.

## Non-negotiable rule

> No decision required = no Case.

Transactions, emails, status changes, threshold crossings, inventory movements, approvals, comments and machine readings are not automatically Cases. They are facts or events. Operis interprets them to determine whether they create a new decision need, provide evidence to an existing Case, represent a response, change urgency or risk, execute a decision, represent an outcome, or require no action.

## Core definitions

### Source

Any system, person, device, service, database, API, message channel or file that provides business information.

Examples: Epicor, Infor SyteLine/CSI, SAP, Oracle, NetSuite, HubSpot, Salesforce, Outlook, Gmail, Teams, Slack, QMS, WMS, CMMS, IoT, spreadsheets, EDI, webhooks and human-entered information.

### Fact

A current or historical piece of business information, such as credit limit, on-hand inventory, due date, supplier lead time, warranty expiration, machine temperature or an active credit hold.

Facts do not automatically create Cases.

### Event

Something that happened, such as an order entry, inventory change, inspection failure, quote request, supplier message, contract renewal window, approval, shipment delay or payment posting.

Events are inputs to interpretation.

### Signal

An interpreted condition indicating that a business decision may be required.

Examples:

- projected material shortage threatens a job,
- quote requires engineering review,
- customer order requires a credit decision,
- warranty claim may indicate recurring product failure,
- supplier delay threatens customer commitment,
- contract renewal requires review,
- abnormal utility consumption requires investigation,
- quality failure creates a disposition decision.

### Case

A persistent business situation requiring evaluation, decision, action or monitoring. A Case remains open until the decision need and resulting condition are resolved.

Examples:

- Protect availability of Part 123 for Job 45021.
- Determine disposition of failed inspection lot.
- Decide whether to release Customer Order 88102.
- Produce commercial response to RFQ 1093.
- Resolve warranty claim WC-402.
- Determine response to supplier delivery failure.

A Case is not a task list. It represents the business problem or decision situation.

### Evidence

Information relevant to a Case: ERP records, parsed emails, drawings, prior quotes, customer history, supplier performance, open POs, inventory, financial exposure, contracts, photos, documents and previous decisions.

Evidence should normally be referenced, not duplicated.

### Response

An inbound human or system reaction relevant to an existing Case, such as approval, rejection, revised supplier commitment, engineering recommendation, customer acceptance or missing information supplied.

A Response can satisfy a decision, add evidence, change a recommendation, trigger an action or escalate/de-escalate a Case.

### Decision

The selected resolution path for a Case: buy, make, transfer, substitute, expedite, wait, reject, rework, scrap, release, hold, quote, no-bid, renew, renegotiate, terminate, refund, replace, approve, escalate, request more information or take no action.

A Decision can be made by a human, group, deterministic policy, governed AI agent or hybrid approval structure.

### Action

An operation that changes the state of the business or advances the Case, such as create PO, update ERP hold, send email, generate quote, create supplier RFQ, change schedule, create NCR/RMA, reserve inventory or update a job.

### Outcome

What actually happened after the Decision and Action: shortage avoided, order released, supplier missed commitment, quote won/lost, warranty resolved, cost reduced, production delayed, issue recurred or no further action required.

Outcomes are required for learning.

## Case as the core business object

Source systems remain authoritative. Operis does not reproduce every ERP table in the Case record.

```text
ERP / CRM / EMAIL / QMS / MTO / OTHER DATA
                  ↓
             REFERENCES
                  ↓
               CASE
          ↙       ↓       ↘
      Signals   Evidence   Responses
          ↘       ↓       ↙
             Decisions
                  ↓
               Actions
                  ↓
               Outcomes
```

The Case must remain compact, universal and stable. Modules extend Case behavior without changing the core Case concept.

## Minimum Case shape

Logical fields:

```text
case_id
company_id
site_id
module_id
case_type_id

title
decision_question
description

subject_type
subject_id
subject_reference

state
priority
risk_level
confidence

owner_type
owner_id
assigned_team

autonomy_level
approval_policy_id
decision_policy_id

opened_at
decision_due_at
target_resolution_at
resolved_at

current_recommendation
current_decision
decision_reason

financial_exposure
operational_exposure
customer_exposure

source_system
source_reference

created_by
created_at
updated_at
```

Do not overload the Case table. Signals, Evidence, Responses, Decisions, Actions, Outcomes, Participants and source references belong in related tables.

## MTO / operating data interpretation

Existing MTO and operating tables may contain manufacturing data, orders, jobs, demand, inventory, purchasing, parsed email, communications, user actions, system actions, approvals, comments and status changes.

Operis interprets those records as one of:

```text
FACT
EVENT
SIGNAL
EVIDENCE
RESPONSE
ACTION_RESULT
OUTCOME
NO_ACTION
```

The classification is configurable by company and module.

## Signal engine

The Signal Engine converts business activity into decision-relevant signals.

It must support deterministic, pattern-based and AI-interpreted signals.

Example deterministic rule:

```text
IF projected_on_hand < required_quantity
AND requirement_date < replenishment_date
THEN create/update MATERIAL_SHORTAGE signal
```

Example credit rule:

```text
IF order_total + open_ar > credit_limit
AND order_status = READY_TO_RELEASE
THEN create CREDIT_DECISION signal
```

Example parsed email:

```text
"We will not be able to ship before October 3."
→ classification: SIGNAL
→ meaning: delivery_delay
→ affected business objects identified
→ attach to existing Case when appropriate
```

Example response email:

```text
"Approved. Release it."
→ classification: RESPONSE
→ response_type: approval
→ matched to existing Case
```

AI interpretation never bypasses policy or authorization.

## Signal rule configuration

Each company can configure Signals without core code changes. A Signal Rule should support:

```text
signal_rule_id
company_id
module_id
name
description
source_types[]
source_entities[]
conditions
thresholds
time_windows
interpretation_method   # deterministic | model | hybrid
case_behavior           # create | update | merge | attach_only | ignore
case_type
dedupe_key
merge_key
priority_formula
risk_formula
enabled
effective_from
effective_to
version
```

## Case creation and deduplication

A Signal does not automatically create a new Case.

On Signal generation, Operis evaluates:

1. Is there an existing open Case for this decision need?
2. Is this Signal evidence for that Case?
3. Does it materially change the Case?
4. Should Cases be merged?
5. Is a new Case required?
6. Is the Signal informational only?

Allowed behaviors:

```text
NEW_CASE
UPDATE_CASE
ATTACH_SIGNAL
MERGE_CASES
REOPEN_CASE
SUPPRESS
MONITOR_ONLY
```

## Decision engine

A Decision Policy defines available choices and how the decision may be made.

```text
decision_policy_id
company_id
module_id
case_type_id
decision_options[]
required_evidence[]
required_checks[]
policy_rules[]
recommended_model
confidence_threshold
autonomy_level
approval_requirements[]
financial_limits
risk_limits
escalation_rules
fallback_behavior
```

## Configurable autonomy

Autonomy is scoped, never global.

- Level 0 — Observe: detect and record only.
- Level 1 — Explain: identify Case and explain why it matters.
- Level 2 — Recommend: recommend Decision, no action.
- Level 3 — Prepare: prepare Action, wait for approval.
- Level 4 — Execute within policy: execute approved classes within explicit limits.
- Level 5 — Autonomous operations: resolve defined Case classes and escalate exceptions.

Autonomy must be configurable by company, module, Case type, action type, financial amount, risk, customer, supplier, facility, role, confidence and exception type.

## Module architecture

Modules configure the universal Case engine rather than become separate applications.

Examples:

```text
OPERIS-DEMAND
OPERIS-PAYABLES
OPERIS-QUALITY
OPERIS-WARRANTY
OPERIS-SALES
OPERIS-QUOTES
OPERIS-SUPPLY
OPERIS-MAINTENANCE
OPERIS-CONTRACTS
OPERIS-NERVE
OPERIS-CREDIT
```

Each module defines its Signal types/rules, Case types, Decision questions/options, Evidence requirements, Policies, Actions, autonomy defaults, Outcomes and UI views.

## Company customization hierarchy

```text
OPERIS PLATFORM DEFAULT
        ↓
INDUSTRY TEMPLATE
        ↓
ERP TEMPLATE
        ↓
COMPANY CONFIGURATION
        ↓
FACILITY / BUSINESS UNIT
        ↓
MODULE
        ↓
CASE TYPE
        ↓
SPECIFIC POLICY OVERRIDE
```

Configuration is versioned and auditable.

## ERP-agnostic adapter model

Core business logic must not be hard-coded to one ERP.

ERP adapters map native records to canonical Operis concepts.

```text
Epicor OrderRel
Infor CustomerOrderLine
SAP SalesOrderItem
NetSuite SalesOrderLine
        ↓
ERP ADAPTER
        ↓
canonical.sales_order_requirement
```

Canonical entities should cover customer, supplier, part, product, sales order, sales order line, job, operation, material requirement, inventory position, PO, shipment, invoice, payment, quote, quality record, warranty claim, contract, asset, employee and facility.

Raw source references are always preserved.

## NERVE / communication interpretation

Email, Slack, Teams, SMS and portal messages are interpreted as:

```text
SIGNAL
EVIDENCE
RESPONSE
APPROVAL
REQUEST
COMMITMENT
EXCEPTION
OUTCOME
NO_ACTION
```

A communication does not automatically create a Case.

The interpreter should identify company, people, business entity, existing Case, intent, commitment, dates, decision relevance and confidence.

## Decision-oriented Case states

Avoid generic task states. Baseline internal states:

```text
DETECTED
UNDERSTANDING
WAITING_FOR_EVIDENCE
OPTIONS_READY
DECISION_READY
WAITING_FOR_APPROVAL
DECIDED
EXECUTING
MONITORING_OUTCOME
RESOLVED
CANCELLED
```

Companies may rename visible labels while internal semantics remain normalized.

## Case relationships

Cases may relate without turning every event into a Case.

```text
PARENT_OF
CHILD_OF
BLOCKS
BLOCKED_BY
CAUSES
CAUSED_BY
RELATED_TO
DUPLICATE_OF
SUPERSEDES
FOLLOW_UP_TO
```

Create separate Cases only when separate business decisions truly exist.

## Human interface

The main user experience is Case-centric. A manager should be able to answer:

- What requires a decision?
- What is at risk?
- What is blocked?
- What can Operis handle automatically?
- What requires me?
- What has waited too long?
- What decisions are costing money?
- What changed today?
- What outcomes did we achieve?

Primary views should become Decision Inbox, Case Board, Risk, Autonomous Activity, Waiting on Others, Outcomes and Learning.

## Fast company onboarding

1. Connect ERP and available systems.
2. Discover entities, relationships, statuses, workflows, custom fields and APIs.
3. Map to the canonical model.
4. Observe in read-only mode.
5. Validate detected decision Cases against real human decisions.
6. Recommend decisions.
7. Prepare transactions and communications.
8. Enable approved autonomous Case classes.

Operis must earn trust progressively rather than require a disruptive implementation.

## Policy before AI

Evaluation order:

```text
LAW / REGULATION
      ↓
COMPANY POLICY
      ↓
CONTRACTUAL REQUIREMENTS
      ↓
BUSINESS RULES
      ↓
CASE EVIDENCE
      ↓
AI REASONING
      ↓
DECISION
```

AI may interpret ambiguity, compare options and recommend actions. It must not silently override explicit policy.

## Auditability

Record why a Signal was generated, which data was used, which Case was selected, which policy applied, model/version used, recommendation, confidence, human changes, approval, action executed and result.

The system must be able to reconstruct why a decision happened.

## Security

Security boundaries exist at company, business unit, facility, module, Case type, entity, action, field, connector, agent and user levels.

Autonomous actions require explicit permission. Credentials remain in secure runtime/connector boundaries. Agents receive capabilities, not raw secrets.

## Architecture rules

1. Case is the core operational object.
2. No decision need means no Case.
3. Signals are interpreted, not raw events.
4. Source systems remain authoritative.
5. Reference business data rather than copying everything.
6. Modules configure the Case engine rather than reinvent it.
7. Every company can override Signals, Policies, Decisions, Actions and autonomy.
8. ERP-specific logic belongs in adapters.
9. AI operates inside policy and permissions.
10. Every automated action is auditable.
11. Outcomes feed learning.
12. Autonomy is earned and scoped.
13. Configuration replaces customer code forks.
14. Human interfaces center on decisions, not transactions.
15. The platform must work read-only before it is allowed to write.

## Initial build sequence

### Phase A — Universal Case Kernel

Implement Cases, Case Types, Signals, Case Signals, Evidence, Responses, Decisions, Actions, Outcomes and audit integration.

### Phase B — Interpretation Layer

Implement event ingestion, canonical event envelope, Signal Rules, Response interpretation, deduplication and Case matching.

### Phase C — Policy / Decision Layer

Implement Decision definitions/options, Evidence requirements, policy evaluation, approvals and autonomy levels.

### Phase D — Action Runtime

Implement connector actions, permission enforcement, execution ledger, failure handling and reconciliation.

### Phase E — Company Configuration

Implement settings for Signals, Cases, Decisions, Actions, autonomy, Policies and Modules.

### Phase F — ERP Adapter SDK

Implement canonical adapters. First reference adapters should be Epicor, Infor SyteLine/CSI, generic SQL, generic REST and CSV/file import.

### Phase G — NERVE

Classify communications as Signals, Evidence, Responses, approvals and commitments.

### Phase H — Discovery / Onboarding Agent

Automate company mapping and candidate Case discovery.

### Phase I — Learning

Add Outcome scoring and recommendation improvement.

## Acceptance criteria

The architecture is successful when:

- a company can connect a different ERP without modifying Case core code,
- two companies on the same ERP can configure different Signals and Decisions,
- a Module installs without creating a separate application,
- parsed email can become Evidence, Signal or Response depending on context,
- multiple Signals can update one Case,
- Signals do not automatically create duplicate Cases,
- Cases can reference data across systems,
- Decisions can be human, AI-recommended or autonomous,
- Action permissions are independently controlled,
- every Action traces back to Case, Decision, Policy and actor,
- Outcomes are measurable,
- company configuration can evolve without platform forks,
- onboarding can begin safely in read-only mode,
- the same Case architecture supports demand, quality, warranty, quotes, credit, supply, maintenance, contracts and future modules.

## North Star

Operis should learn:

```text
what happened
what matters
what decision is required
what information is needed
what options are allowed
who may decide
what action should occur
what actually happened
what should improve next time
```

The goal is a universal configurable AI operating layer that attaches to a company's existing systems and progressively assumes repeatable operational decision work under explicit company rules.

**Signals create awareness. Cases create focus. Decisions move the business.**
