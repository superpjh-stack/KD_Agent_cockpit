---
name: manufacturing-agent-maker
description: Build or retrofit a company-specific manufacturing AI Agent as a chat-centered cockpit that combines conversation history, recommended questions, live operational context, structured factory tools, document RAG, and human approvals. Use for runnable manufacturing Agent prototypes or UI conversions; do not use for proposal-only writing or generic chatbots without factory data.
---

# Manufacturing Agent Maker

Create a runnable, company-specific manufacturing Agent whose main interface is the conversation—not a collection of disconnected dashboards.

## Start from evidence

Inspect the supplied project, plan, process map, or prior decisions. Separate confirmed company facts, demo assumptions needed for a prototype, and production details that still require field verification.

Do not copy process, equipment, KPI, or terminology from another company. When adapting to a new manufacturer, read [references/manufacturing-adaptation.md](references/manufacturing-adaptation.md).

## Choose the build mode

- **Retrofit:** preserve the existing repository, data access methods, prompts, and tests; replace or reorganize the user interface around the conversation.
- **New prototype:** create the smallest runnable app that proves structured factory retrieval, document retrieval, grounding, and approvals. Prefer a replaceable repository adapter and seed only clearly labeled demo data.

## Build the Agent cockpit

Read [references/cockpit-pattern.md](references/cockpit-pattern.md) before implementing the chat-centered UI.

The default desktop composition is:

1. a compact top strip of operational KPIs;
2. left rail with new conversation, recent user questions, and categorized recommended questions;
3. dominant center conversation with source/tool grounding and a persistent chat input;
4. right rail with the selected Job/LOT/project snapshot, risks, and pending approvals;
5. a collapsed configuration area for API key, model, retrieval depth, and document indexing.

On narrow screens, preserve the same information hierarchy even when it stacks vertically. A recommendation should become the next user question without duplicating chat logic. Conversation history must remain session-safe and resettable.

## Connect knowledge and factory data

Use two retrieval paths behind one conversation:

- document RAG for SOPs, standards, drawings, quotations, manuals, inspection records, and claims;
- strict read-only functions for current MES/ERP/QMS/WMS/IoT data.

Expose fewer than 20 well-bounded tools. Tool names should describe user decisions such as project status, material exceptions, LOT trace, equipment state, or quality release. Return structured JSON with identifiers, timestamps, units, demo/production provenance, and errors. Never expose write, stop, release, approve, purchase, or parameter-change functions unless the user separately authorizes that scope and the system has an approval workflow.

The answer contract is: `conclusion -> evidence -> risk/exception -> recommended action -> owner/approval`. Show document filenames and invoked data tools near the answer.

## Protect operational decisions

Keep human approval for quotations, purchase orders, substitute materials, process parameter changes, maintenance/stop decisions, inspection disposition, FAT, shipment, and customer commitments. Label model outputs and synthetic records as demo or unvalidated. Include RBAC, audit, sensitive-field masking, backup/recovery, data-quality rules, and model evaluation/rollback in the production checklist.

## Verify and hand off

Run unit tests for repository queries, strict read-only tool schemas, conversation/tool-call loops, recommendation routing, history extraction, and risk summaries. Smoke-test the complete UI without requiring a live API call. Check for cross-company names and domain contamination. Package source, sample documents, environment example, tests, and a concise run guide; do not include secrets or caches.

If the user supplied an existing artifact, return a new version unless they explicitly requested in-place replacement. Do not deploy, publish, or connect production systems without separate authorization.

