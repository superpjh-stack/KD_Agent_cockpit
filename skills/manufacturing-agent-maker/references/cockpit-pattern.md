# Chat-centered manufacturing cockpit

## Information hierarchy

| Region | Must answer | Recommended controls |
|---|---|---|
| KPI strip | What requires attention now? | 4–6 metrics with units and warning counts |
| History rail | What did I ask recently? | new conversation, 5–8 recent user questions |
| Recommendations | What can I ask next? | 3–5 domain categories, two concise prompts each |
| Conversation | What is the conclusion and its basis? | chat messages, source/tool labels, evidence expander, input |
| Context rail | What is happening to the selected object? | Job/LOT/project selector, progress, due date, risk counts |
| Approval card | What must a person decide? | owner, decision, evidence state; never an unguarded action |
| Settings | How is retrieval configured? | key, model, result count, document upload, connection status |

The center conversation should be visually dominant. Avoid making users change tabs to understand the answer. Detailed tables may remain in secondary views only when needed; surface their risk summaries beside the chat.

## Interaction rules

- Clicking a recommended or prior question sets one shared `pending_question` state and uses the same submission path as typed input.
- Store role, content, time, document sources, evidence snippets, and invoked factory tools per message.
- Reset the conversation and response-chain identifier together.
- Recommended questions must contain real process nouns and identifiers from the company domain.
- Selecting a project/Job/LOT refreshes the context rail but does not silently alter the conversation.
- A “brief this object” button should generate a normal question, not call a privileged workflow.
- When no API key is present, show the cockpit and demo context while disabling live chat cleanly.

## Visual behavior

Use restrained cards, consistent radii, compact KPI density, and one primary action. Color must never be the only risk signal; pair it with text and an icon. Do not hide demo/unvalidated status. Check desktop and stacked/narrow layouts, scrolling, long Korean text, and empty history.

## Acceptance checks

- The user sees history, recommendations, chat, operational context, and approvals without navigating away.
- The chat area remains the largest region.
- Every generated answer can show both document and structured-data grounding.
- No UI control directly commits a safety, quality, financial, or external decision.
- The initial screen remains useful without a live model call.

