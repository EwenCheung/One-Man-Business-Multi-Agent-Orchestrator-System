# Implementation Plan — Identity Resolution, Policy Retrieval, Approval Rules, and Review Loop

## Goal

Evolve the system from a working multi-agent prototype into a production-safe one-owner business operator that:

- accepts external sender identifiers at the API boundary
- resolves them to canonical internal UUID entities
- defaults unknown senders into the customer workflow correctly
- retrieves business policy using both semantic and lexical methods
- protects owner benefit through outbound approval rules
- captures approval outcomes for future evaluation and training

This plan replaces the older P3-only deployment plan and reflects the latest confirmed product decisions.

---

## Locked Product Decisions

These are confirmed and should be treated as implementation constraints:

1. `sender_id` received by the API is an **external identifier** such as phone number or username.
2. The system must resolve that external identifier into a **canonical internal UUID** for downstream business logic.
3. Resolution happens in the **intake / identity layer**, not as a fallback in the retrieval agent.
4. We should **not** force a corrective fallback in `pipeline_graph.py` for role repair.
5. The system uses **one owner, one database**. All records belong to the same fixed `owner_id`.
6. Unknown senders should enter the system through the **customer path**.
7. Policy retrieval should support **semantic retrieval + lexical retrieval + metadata filtering**.
8. Internal owner-protection logic should be called **approval rules**, not “policy”, to avoid collision with client/T&C policy documents.
9. Schema changes are allowed if required for the correct architecture.
10. During implementation, clearer naming is allowed and encouraged if it reduces ambiguity in code, database schema, or product language.

---

## Architecture Direction

## Naming Convention Guidance

If implementation reveals confusing names, we should prefer clearer names even if they require small refactors.

Preferred direction:

- use `external_sender_id` for the raw API/platform identifier
- use `entity_id` for the canonical internal UUID used across the system
- use `entity_role` for normalized business roles (`customer`, `supplier`, `partner`, `investor`)
- use **approval rules** for internal outbound protection logic
- reserve **policy** for business/T&C documents handled by the Policy Agent

Examples of acceptable renaming during implementation:

- ambiguous `sender_id` usages inside internal state or DB-adjacent code may be split into:
  - `external_sender_id`
  - `entity_id`
- ambiguous approval/risk naming may be updated so the code clearly distinguishes:
  - policy retrieval
  - approval-rule validation
  - final risk aggregation

Any rename should follow these rules:

1. reduce confusion, not increase it
2. preserve API compatibility unless explicitly changed
3. prefer migration-safe schema changes
4. update related docs/tests together

### Sender Identity Model

The correct approach is:

- keep API `sender_id` as an external string
- persist that external id in messages / memory / approvals for traceability
- resolve it to a canonical internal entity UUID before downstream business retrieval

### Required Schema Direction

We should add a new mapping layer for external identities.

Recommended new table:

`external_identities`

Suggested fields:

- `id` UUID primary key
- `owner_id` UUID not null
- `external_id` TEXT not null
- `external_type` TEXT nullable (`phone`, `username`, `email`, `platform_user`, etc.)
- `entity_role` TEXT not null (`customer`, `supplier`, `partner`, `investor`)
- `entity_id` UUID not null
- `is_primary` BOOLEAN default true
- `metadata` JSONB nullable
- `created_at` timestamptz default now()

Suggested uniqueness:

- unique `(owner_id, external_type, external_id)`

This table becomes the canonical bridge between external sender identity and internal UUID identity.

### Resolution Order

The resolver should use this order:

1. exact internal UUID match if incoming sender id is already a valid UUID and matches an entity id
2. exact match in `external_identities`
3. normalized phone match against known entity phone fields
4. normalized email / username match if relevant
5. if still not found:
   - create a new `customers` row for this owner
   - create a matching `external_identities` row
   - use the new customer UUID from this point onward

---

## Phases

## Phase 1 — External Sender Identity Resolution and Intake Persistence

### Objective

Accept external identifiers like phone numbers or usernames, resolve them to canonical UUIDs, and ensure unknown senders are onboarded into the customer path at intake.

### Why this phase comes first

The current code incorrectly assumes `sender_id == entity.id` in several places. That is incompatible with your intended API contract.

### Current gaps

- `IncomingMessage.sender_id` is a string, which is correct at the boundary
- `intake.py` currently checks `Customer.id == sender_id` / `Supplier.id == sender_id` / etc.
- `router.py` repeats the same wrong assumption for owner resolution
- downstream retrieval uses `sender_id` as if it were already the internal UUID
- there is no external-id mapping table today

### Changes

1. Add `external_identities` table
2. Add a shared resolver function, e.g. `resolve_external_sender(...)`
3. Update intake to:
   - resolve incoming external sender id
   - set canonical `sender_role`
   - set canonical internal entity UUID in state
   - create a new customer + external identity if sender is unknown
4. Update router owner resolution to use resolver output, not raw sender id equality against UUID columns
5. Update downstream state contract so agents use canonical UUID for scoped data access
6. Keep original external sender id persisted for traceability

### Core files

- `backend/models/__init__.py`
- `backend/api/router.py`
- `backend/nodes/intake.py`
- `backend/graph/state.py`
- `backend/db/models.py`
- new migration / schema file for `external_identities`

### Acceptance criteria

- API accepts phone number / username in `sender_id`
- known sender resolves to correct UUID and role
- unknown sender is auto-created as customer under the fixed owner
- new customer gets a linked external identity record
- retrieval and memory use canonical UUID where entity scoping is required
- raw external sender id remains stored in message history

---

## Phase 2 — Owner-Oriented Policy Corpus and Dual Retrieval

### Objective

Upgrade the policy layer so the Policy Agent reasons over a richer owner-oriented corpus using semantic retrieval, lexical retrieval, and metadata-aware narrowing.

### Current gaps

Current policy retrieval supports:

- semantic pgvector search
- reranking
- final LLM evaluation

It does **not** yet support a separate lexical retrieval path over policy text.

### Changes

1. Update `backend/db/generate_policies.py` to generate a stronger production-like business document set.
2. Add an explicit owner-oriented document, e.g.:
   - `owner_benefit_rules.pdf`
3. Expand `backend/data/policy_metadata.py` with the new document category metadata.
4. Re-generate policy PDFs.
5. Re-ingest policies into Supabase.
6. Add lexical policy retrieval in `backend/tools/policy_tools.py`.
7. Merge semantic + lexical candidates before reranking in `backend/agents/policy_agent.py`.
8. Preserve metadata/category filtering in retrieval.

### Target policy set

- pricing policy
- returns policy
- supplier terms
- partner agreement policy
- data privacy policy
- owner benefit / approval rule source document

### Retrieval design

The policy retrieval flow should become:

1. semantic candidate search
2. lexical candidate search
3. optional metadata narrowing
4. candidate merge + dedupe
5. rerank
6. structured evaluation

### Core files

- `backend/db/generate_policies.py`
- `backend/data/policy_metadata.py`
- `backend/db/ingest_policies.py`
- `backend/tools/policy_tools.py`
- `backend/agents/policy_agent.py`

### Acceptance criteria

- policy corpus is regenerated and ingested cleanly
- policy chunk metadata includes new owner-oriented category
- policy agent uses both semantic and lexical retrieval paths
- lexical retrieval materially improves exact-rule pickup
- tests cover retrieval merge behavior

---

## Phase 3 — Approval Rule Validation Layer

### Objective

Add a unified outbound validation layer that decides whether a reply can be sent automatically or must wait for owner approval.

This phase merges the previously separate “business risk” and “evidence validation” ideas into one approval-rule system.

### Terminology

- **Policy Agent** = reads T&C / business documents from policy corpus
- **Approval Rules** = internal outbound decision rules protecting owner interests

### Approval rule goals

The system should protect the owner by default and hold replies that create avoidable downside.

### What this phase should check

1. **Owner-benefit risk**
   - unnecessary discounts
   - margin erosion
   - excessive concessions
   - free upgrades / fee waivers

2. **Liability risk**
   - absolute promises
   - guarantees without evidence or approval
   - admissions that create commercial or legal exposure

3. **Commitment risk**
   - custom commitments beyond known terms
   - delivery / SLA / exclusivity promises
   - non-standard commercial commitments

4. **Evidence grounding**
   - every factual claim in reply should map to retrieved evidence
   - unsupported or contradictory claims should be flagged

5. **Approval-rule matching**
   - concessions must be allowed by rule or held for approval
   - sensitive commercial actions require hold

### Default thresholds to implement

Unless tests or later review prove otherwise, use these reasonable defaults:

- standard catalog / published pricing may be discussed normally
- explicit discounts above ordinary documented discount bands require approval
- any waiver / freebie / exception / custom deal requires approval unless explicitly grounded in a rule
- guarantees and absolute promises require approval unless grounded in retrieved evidence and allowed terms
- cost price, internal margin, supplier leverage, or internal negotiation room are high-risk disclosures

### Design

Recommended routing:

`reply -> approval_rule_validation -> risk aggregation -> send or hold`

This layer can be implemented as:

- a new node, or
- an expansion of existing risk rule evaluation,

but the behavior should be logically unified.

### Core files

- `backend/nodes/risk_rules.py`
- `backend/nodes/risk.py`
- `backend/agents/reply_agent.py`
- `backend/graph/pipeline_graph.py`

### Acceptance criteria

- risky discounts / waivers / guarantees are held
- unsupported factual claims are flagged
- grounded, safe, owner-benefiting replies can flow through automatically
- approval rule result is visible in held reply metadata and traces

---

## Phase 4 — Approval Dataset and Trace Review Loop

### Objective

Capture real-world approval decisions and connect them to trace review so the system can improve over time and later support PEFT or other tuning.

### Changes

1. Save approval outcome data for held replies:
   - approved
   - rejected
   - edited
2. Save reasons for rejection / edit
3. Save approval-rule flags and grounding results
4. Add stable trace correlation for each run
5. Support false-positive / false-negative review workflow

### Data to capture

- external sender id
- resolved internal entity UUID
- sender role
- raw message
- reply text
- approval rule flags
- evidence validation result
- final decision
- reviewer reason
- trace id

### Why this matters

This creates the labeled dataset needed later if we want to:

- tune thresholds
- improve prompts
- train a lightweight approval model
- build PEFT datasets from approved/rejected owner decisions

### Core files

- `backend/services/approval_service.py`
- `backend/db/models.py`
- `backend/api/router.py`
- optional frontend approval review components

### Acceptance criteria

- every held reply records enough context for review
- approval decisions are auditable
- trace ids link application records to runtime traces
- false positive / false negative review is possible

---

## Suggested Execution Order

1. Phase 1 — identity resolution and schema support
2. Phase 2 — policy corpus and dual retrieval
3. Phase 3 — approval rules and evidence grounding
4. Phase 4 — dataset capture and review loop

---

## Required Schema / Data Work

### Schema changes expected

1. add `external_identities`
2. update pipeline state to carry both:
   - external sender id
   - canonical internal entity id
3. optionally add explicit trace id storage where helpful for review flows

### Data generation work allowed

The user explicitly approved generating improved owner-oriented data.

So we should:

- update `backend/db/generate_policies.py`
- update `backend/db/generate_seed_data.py`

The generated content should reflect a realistic one-man-business operating model.

---

## No Longer Needed

The following earlier ideas are no longer the chosen path:

- retrieval-agent fallback for missing role
- pipeline-graph forced sender-role normalization fallback
- treating approval-rule logic as just another “policy” layer

---

## Remaining Ambiguity

At this point there are **no blocking product ambiguities** remaining for planning.

Implementation can proceed using these locked assumptions:

- incoming sender id is external
- external id resolves to canonical internal UUID
- one fixed owner for the whole database
- unknown senders are created as customers
- policy retrieval becomes semantic + lexical + metadata aware
- approval rules protect owner benefit and decide hold vs send

---

## Verification Plan

### Phase 1 verification

- send API message with phone number / username as sender id
- verify entity resolution works for known senders
- verify unknown sender creates customer + external identity mapping
- verify downstream retrieval uses canonical UUID

### Phase 2 verification

- regenerate policy PDFs
- ingest into Supabase
- verify semantic and lexical retrieval both return useful candidates
- verify policy evaluation remains structured and grounded

### Phase 3 verification

- test safe replies that should auto-send
- test discount / concession / guarantee replies that should hold
- test unsupported factual claims that should hold

### Phase 4 verification

- approve and reject held replies
- verify records contain decision reason and trace id
- verify review workflow can classify false positives / false negatives

---

## Tracking Notes

This file is now the canonical work plan for the next implementation wave. Update it as each phase completes or if architecture changes materially.
