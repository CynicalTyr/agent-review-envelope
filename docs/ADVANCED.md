# Advanced: two-tier review for autonomous agents

This guide is for people who already ran [`START_HERE.md`](../START_HERE.md)
and want the design that keeps showing up in production: **why two queues**,
how prompt injection rides “helpful” sitreps, and how to wire this next to
watchdogs, secret scanners, and OSINT sidecars.

Search terms this document is meant to answer: *AI agent Slack without
review*, *LLM worker outbox*, *generator vs evaluator agents*, *fail-closed
JSON schema for tool results*, *two-tier review queue*.

---

## 1. The failure that looks like success

A hunter, disk watcher, or watchdog finds something true. It also has a
language model. The shortest path to “the human saw it” is: **render a
paragraph and POST to chat.**

That path has three hidden properties:

1. **The finder chooses the wording.** Injected repo text, poisoned logs, or
   a sarcastic system prompt become the page.
2. **There is no reject.** Noise and real incidents share a channel. Humans
   mute it. Real keys get ignored (see `whitehat-secret-policy`).
3. **There is no replay.** A crashed messenger loses the only copy.

The envelope is slower than Slack and immune to “the broker was down so we
skipped review.” The bus is the filesystem: `.tmp` → `fsync` → `replace`.

---

## 2. Why *two* directories, not one

| Queue | Owner | Job |
| ----- | ----- | --- |
| `pending_systems_review/` | Small local “systems” model or rules | Fix obvious junk, reject noise, or **ESCALATE** |
| `pending_primary_review/` | Larger model / human | Act, or actually send the message |

If you collapse them, you recreate the original bug: the same stack both
discovers and authorizes speech.

**Exception:** scheduled briefings (news, weather) sometimes bypass both
queues because latency and tone beat dual-control. Mixing CVE sitreps onto
that bypass either slows the news or skips the judge. Keep the exception
**named** in code, not vibes.

---

## 3. Real-world application: watchdog that must not DM

A user-bus watchdog restarts a unit, then wants to tell someone.

**Wrong:** HTTP POST to the chat API from the watchdog process — especially
if the chat API *is* the casualty (see `casualty-aware-watchdog`).

**Right:** `enqueue_systems_review(...)` with `source="watchdog"`,
`kind="unit_down"`. A poller that is **not** the watchdog judges it.

Integration sketch:

```python
# watchdog process
enqueue_systems_review(build_review_payload(
    source="watchdog",
    kind="unit_down",
    message=f"{unit} still inactive after local restart",
    recipient="operator",
    recipient_role="admin",
    details={"unit": unit, "tier_tried": "local"},
    allow_code_blocks=True,
))
```

---

## 4. Real-world application: secret findings

A scanner that dumps tokens into Slack is an incident. Policy:

- Enqueue **only** when `valid_keys_found > 0` (`whitehat-secret-policy`).
- Put **masked** keys in `message`; full material in a local file the
  messenger never reads.
- `allow_code_blocks=True` only for `recipient_role="admin"`.

If your systems model **ESCALATE**s zero-key runs, that is a contract error.
Record it with `agent-loop-guardrails` so the next judge does not repeat it.

---

## 5. Real-world application: OSINT sidecar (Curiosity-Docker)

Username discovery returns **candidate URLs**, not identity. Those hits
should not be a chat novel. File an envelope (`kind="osint_candidates"`)
or keep them in the identity ledger until a human accepts them.

On HTTP 503 `busy`, do not enqueue “scan failed mysteriously.” Use
`sidecar-occupancy` kinds and retry next cycle. Pair this repo with
[Curiosity-Docker](https://github.com/CynicalTyr/Curiosity-Docker).

---

## 6. Integration anti-pattern: reviewer as JSON extractor

The systems-tier model is good at **fix / reject / escalate**. It is a
terrible CSV/JSON extractor. If you route OSINT enrichment to it:

1. It replies in chat.
2. You stamp a cooldown anyway.
3. You get days of silence.

Use `reviewer-not-extractor` (`assert_lane("extract_json", "reviewer")`
must raise). Extraction needs JSON-mode on a **different** lane. Do not
stamp long cooldowns until parse succeeds.

---

## How this stands out

Researched with Context7 (`libraryId=/langchain-ai/langgraph` HITL
`interrupt()` / `Command(resume=...)`; `libraryId=/modelcontextprotocol/python-sdk`
FastMCP stdio + stderr logging) and GitHub-MCP (`langchain-ai/langgraph`
file `libs/prebuilt/langgraph/prebuilt/interrupt.py`; public `filename:outbox.py`
trees are transactional DB outboxes, not LLM dual-control). DeepWiki on
`langchain-ai/langgraph` lists HITL as inspect-and-resume *inside* the Pregel
loop, not a second OS process.

| Obvious alternative | What they optimize | What they miss | This kernel |
| ------------------- | ------------------ | -------------- | ----------- |
| LangGraph `interrupt()` + checkpointer | Pause one graph until a human `Command(resume=...)` | Finder and sender still share the graph; resume re-runs the interrupt node | Finder writes JSON; a *different* process judges; MCP cannot enqueue |
| Ticket bots (Jira/GitHub issues) | Audit trail | Still no fail-closed speech schema; bots spam projects | Exact `orchestrator.workflow` or quarantine |
| Redis / Celery list | Speed, multi-host | “Skip if broker down”; no admin-vs-user fence | Atomic `.tmp`+`fsync`+`replace` on disk |
| `outbox.py` (transactional outbox) | DB event delivery | Reliable *events*, not “who may word a human page” | Envelope is the only legal page request |
| MCP `send_message` tool | Demo speed | Prompt injection becomes an ops alert | Inspect-only MCP (`review_envelope_health` / `_read`) |

**Non-obvious / high-leverage:** rigidity of the schema strings *is* the
product. A typo quarantines. Flexing the schema “so the poller is nicer”
recreates worker-POSTs-to-chat.

**Mental model to replace:** adopters think HITL = interrupt-in-graph; the
governing model is **generator ≠ evaluator** across process boundaries
(per Cynical0n3 NotebookLM `deep-thought`: same channel for untrusted retrieve
and privileged send is a confused-deputy).

**Incentive:** the stack will keep adding a send-chat tool because it is
cheaper than waiting for the poller.

**Second-order effect:** once copied, teams optimize time-to-Slack, which
causes the first “debug” MCP write tool — dual-control dies without a
schema change.

---

## 7. Short comparison (same facts, operator table)

See **How this stands out** above for library/file evidence. In one line:
this is not an agent *framework*. It is a kernel you drop into the loop
you already have. You still write a poller.

---

## 8. Architecture decisions worth copying

1. **Exact workflow strings.** Typos quarantine. Do not “flex” the schema
   in v1; fork `schema_version` if you must.
2. **Admin-only fences.** User-bound markdown code is how tools get invoked
   by accident.
3. **Natural language `format`.** The human channel is prose. Structured
   data lives in `details`.
4. **Source + kind.** Pollers prioritize `kind=unit_down` over
   `kind=curiosity_note` without reading the essay.

---

## 9. Measuring whether anyone *uses* this

Stars are vanity. Count:

- Envelopes that reached `rejected/` vs `primary/` vs `sent/`.
- Pages that still came from a process other than the poller (those are
  bypasses — bugs).
- Reviewer `ESCALATE` rate on hunter jobs with `valid_keys_found=0` (should
  be ~0).

---

## 10. Where this sits in the kernel family

Queues (this repo) + denies (`epistemic-deny`) + budgets
(`edge-capacity-gate`, `agent-coherence-clamp`) + occupancy
(`sidecar-occupancy`) are the unusual parts of an autonomous operator.
The model is a tier inside that machine, not the machine.

## Hidden dynamics (short)

- Pattern: Generator ≠ evaluator. The process that *finds* a problem must not *word* the human message.
- Loop: Worker JSON → systems verdict → primary or drop. If the reviewer is also used as an extractor, you get chat, then a cooldown on nothing.
- Incentive: Direct chat is the shortest path to “the human saw it.” Every worker will try to skip the envelope unless skip is more expensive than filing.
- Leverage: Keep orchestrator.workflow exact. A typo quarantines the item. That rigidity is the product.
- Harness: A harness (Cursor, Claude Desktop) launches tools for a chat model. Give it *read-only* inspect tools. Do not give it enqueue or Slack.
- Custom AI: Your worker process calls enqueue_systems_review. A *different* timer reads the folder and judges. The chat model is not that worker.

