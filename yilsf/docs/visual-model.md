# YILSF — One-Page Visual Model

A single picture of the framework: the yogic path from distraction to stable
insight, mapped onto the pipeline. Rendered with Mermaid (GitHub renders it
inline).

---

## The cognitive stack

```mermaid
flowchart TD
    subgraph IN[" "]
        R["Requirements + Task type"]
    end

    R --> P

    subgraph YCL["Yoga Cognitive Layer"]
        direction TB
        P["🧘 Pratyāhāra — withdraw noise<br/>prune to minimal context"]
        D1["🎯 Dhāraṇā — focus<br/>one role, one task"]
        G["🌊 Dhyāna — generate<br/>Generator agent drafts"]
        C["🔍 Dhyāna — reflect<br/>Critic agent challenges"]
        GR{"🛡️ Guardrails<br/>coverage · assumptions<br/>unknowns · scenarios"}
        V["🪷 Samādhi — stabilise<br/>Validator resolves each issue"]

        P --> D1 --> G --> C --> GR --> V
    end

    Y["📜 Yamas / Niyamas — the constitution<br/>never invent · mark UNKNOWN · domain rules"]
    Y -.enforced at every stage.-> YCL

    V --> OUT["Stable, traceable artefact<br/>+ full stage trace"]
```

---

## The dialogue that creates stability

Three roles, one model, three disciplines. Stability is an emergent property of
the dialogue, not of any single call.

```mermaid
sequenceDiagram
    participant U as Caller
    participant Gen as Generator (Dhyāna)
    participant Cri as Critic (Dhyāna)
    participant GR as Guardrails (code)
    participant Val as Validator (Samādhi)

    U->>Gen: requirements + focused task
    Gen-->>Cri: draft artefact
    Note over Cri: observe → challenge<br/>assumptions, edge cases, mismatches
    Cri-->>GR: refined candidate
    Note over GR: deterministic checks<br/>coverage · hedging · unknowns
    GR-->>Val: candidate + issue list
    Note over Val: resolve every issue,<br/>keep UNKNOWNs honest
    Val-->>U: stable artefact + trace
```

---

## The mapping, at a glance

| Principle | Sanskrit | Discipline | Control in YILSF |
|-----------|----------|------------|------------------|
| Withdraw noise | Pratyāhāra | Calm the inputs | Pruned, minimal context |
| Focus | Dhāraṇā | One-pointed attention | Single role + single task |
| Flow | Dhyāna | Sustained, self-aware reasoning | Generate → critique |
| Stability | Samādhi | Settled, unshakeable output | Guardrails → validate |
| Ethics | Yamas/Niyamas | Restraint & observance | Domain constitution |

> **The tagline:** *observe → reflect → refine → stabilise.*
