# AuthBridge MCP Server

**Prior Authorization Intelligence Agent for Healthcare**  
Built for the [Agents Assemble Hackathon](https://agents-assemble.devpost.com) · Prompt Opinion Platform

---

## What is AuthBridge?

AuthBridge is a **Model Context Protocol (MCP) server** that eliminates the #1 administrative burden in US healthcare — prior authorization. It reads a patient's FHIR R4 record and automatically generates a complete, payer-ready prior authorization packet in seconds.

Clinicians currently spend **2+ hours per day** on manual prior auth paperwork. AuthBridge reduces this to a 2-minute review.

---

## Architecture

```
Prompt Opinion Platform (A2A)
        ↓  MCP
AuthBridge Server (FastAPI · Railway)
        ↓  FHIR R4
HAPI FHIR / Any FHIR-compliant EHR
```

---

## MCP Tools Exposed

| Tool | Description |
|---|---|
| `fetch_patient_fhir` | Fetches complete patient FHIR record (conditions, meds, labs, encounters, allergies, reports) |
| `draft_prior_auth` | Generates full PA packet: medical necessity statement, step therapy, evidence, denial risk, appeal points |
| `assess_denial_risk` | Scores denial probability (LOW/MEDIUM/HIGH) with specific mitigation steps |

---

## PA Packet Sections

1. **Request Summary** — treatment, diagnosis codes, payer, urgency
2. **Medical Necessity Statement** — clinician-language narrative ready to paste into payer portal
3. **Step Therapy History** — chronological prior medication trials with discontinuation reasons
4. **Clinical Evidence** — key labs, diagnostic reports, specialist encounters
5. **Denial Risk Assessment** — scored risk with actionable mitigations
6. **Appeal Talking Points** — pre-built arguments if denied
7. **A2A Summary** — structured JSON passable to other agents

---

## Quick Start

### Local Development

```bash
git clone https://github.com/YOUR_USERNAME/authbridge-mcp
cd authbridge-mcp
pip install -r requirements.txt
uvicorn main:app --reload
```

Server runs at `http://localhost:8000`

### Test the API

```bash
# List available tools
curl http://localhost:8000/tools

# Draft a prior auth packet
curl -X POST http://localhost:8000/tools/draft_prior_auth \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "pt-syn-00287",
    "proposed_treatment": "Adalimumab (Humira) 40mg subcutaneous injection every 2 weeks",
    "payer_name": "BlueCross BlueShield",
    "clinician_name": "Dr. Priya Mehta",
    "fhir_base_url": "https://hapi.fhir.org/baseR4"
  }'

# Assess denial risk only
curl -X POST http://localhost:8000/tools/assess_denial_risk \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "pt-syn-00287",
    "proposed_treatment": "Adalimumab (Humira) 40mg",
    "fhir_base_url": "https://hapi.fhir.org/baseR4"
  }'
```

---

## Deploy to Railway (Free)

1. Fork this repo
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select this repo → Railway auto-detects the Procfile
4. Your live URL appears in ~2 minutes

No environment variables required for basic use. Optionally set:
- `FHIR_BASE_URL` — default FHIR server (defaults to HAPI public sandbox)

---

## Synthetic Test Patient

A fully synthetic FHIR R4 patient bundle is included in `/data/synthetic_patient_bundle_transaction.json`.

**Patient:** Ananya Sharma (synthetic) — 43F  
**Diagnosis:** Seropositive Rheumatoid Arthritis (M05.79)  
**Requesting:** Adalimumab (Humira) biologic therapy  
**Step therapy:** Methotrexate (hepatotoxicity), Hydroxychloroquine (inadequate response)  
**Allergy:** Sulfasalazine  
**Labs:** CRP 42.6 mg/L, ESR 78 mm/h, RF 186 IU/mL, DAS28 5.4  

Upload to any FHIR server:
```bash
curl -X POST "https://hapi.fhir.org/baseR4" \
  -H "Content-Type: application/fhir+json" \
  -d @data/synthetic_patient_bundle_transaction.json
```

> ⚠️ **No real PHI is used anywhere in this project.** All data is fully synthetic.

---

## SHARP Context Integration

AuthBridge is designed to receive patient context via the Prompt Opinion SHARP extension:

```json
{
  "patient_id": "pt-syn-00287",
  "fhir_base_url": "https://hapi.fhir.org/baseR4",
  "fhir_token": "[optional bearer token]",
  "proposed_treatment": "Adalimumab 40mg biweekly",
  "payer_name": "BlueCross BlueShield",
  "clinician_name": "Dr. Priya Mehta"
}
```

---

## Tech Stack

- **Python 3.11** · **FastAPI** · **Uvicorn**
- **HL7 FHIR R4** (via HAPI FHIR public sandbox)
- **MCP (Model Context Protocol)**
- **A2A (Agent-to-Agent)** via Prompt Opinion
- **Railway** (free deployment)

---

## Judging Criteria Alignment

| Criterion | How AuthBridge addresses it |
|---|---|
| **AI Factor** | LLM-powered reasoning synthesizes across FHIR resources to generate clinical narratives — impossible with rule-based systems |
| **Impact** | Prior auth delays affect 93% of physicians (AMA 2023); AuthBridge directly reduces 2+ hours/day of admin burden |
| **Feasibility** | FHIR R4 standard, synthetic-only data, no PHI, deployable on any cloud, connects to any FHIR-compliant EHR |

---

*Built for Agents Assemble Hackathon · Prompt Opinion Platform · May 2026*  
*All patient data is synthetic. No real PHI is processed.*
