from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fhir_client import FHIRClient
from pa_builder import PABuilder
import uvicorn
import os

app = FastAPI(
    title="AuthBridge MCP Server",
    description="Prior Authorization Intelligence MCP Server using FHIR R4",
    version="1.0.0"
)

FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")

# ─────────────────────────────────────────────
# MCP Tool Discovery Endpoint
# ─────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "AuthBridge MCP Server running", "version": "1.0.0"}

@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {
                "name": "fetch_patient_fhir",
                "description": "Fetches a patient's full FHIR record including conditions, medications, observations, encounters, allergies, and diagnostic reports",
                "parameters": {
                    "patient_id": {"type": "string", "description": "FHIR Patient resource ID"},
                    "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server", "default": FHIR_BASE_URL}
                }
            },
            {
                "name": "draft_prior_auth",
                "description": "Generates a complete payer-ready prior authorization packet from a patient FHIR record and proposed treatment",
                "parameters": {
                    "patient_id": {"type": "string", "description": "FHIR Patient resource ID"},
                    "proposed_treatment": {"type": "string", "description": "The medication, procedure, or service requiring authorization"},
                    "payer_name": {"type": "string", "description": "Name of the insurance payer", "default": "Not specified"},
                    "clinician_name": {"type": "string", "description": "Name of the requesting clinician", "default": "Not specified"},
                    "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server", "default": FHIR_BASE_URL}
                }
            },
            {
                "name": "assess_denial_risk",
                "description": "Quickly scores the likelihood of prior authorization denial and returns top risk factors with mitigation steps",
                "parameters": {
                    "patient_id": {"type": "string", "description": "FHIR Patient resource ID"},
                    "proposed_treatment": {"type": "string", "description": "The treatment being requested"},
                    "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server", "default": FHIR_BASE_URL}
                }
            }
        ]
    }

# ─────────────────────────────────────────────
# Tool 1: Fetch Patient FHIR Data
# ─────────────────────────────────────────────
@app.post("/tools/fetch_patient_fhir")
async def fetch_patient_fhir(request: Request):
    try:
        body = await request.json()
        patient_id = body.get("patient_id")
        fhir_base_url = body.get("fhir_base_url", FHIR_BASE_URL)

        if not patient_id:
            return JSONResponse(status_code=400, content={"error": "patient_id is required"})

        client = FHIRClient(fhir_base_url)
        patient_data = client.get_patient_bundle(patient_id)

        return {
            "status": "success",
            "patient_id": patient_id,
            "fhir_base_url": fhir_base_url,
            "data": patient_data
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─────────────────────────────────────────────
# Tool 2: Draft Prior Authorization Packet
# ─────────────────────────────────────────────
@app.post("/tools/draft_prior_auth")
async def draft_prior_auth(request: Request):
    try:
        body = await request.json()
        patient_id = body.get("patient_id")
        proposed_treatment = body.get("proposed_treatment")
        payer_name = body.get("payer_name", "Not specified")
        clinician_name = body.get("clinician_name", "Not specified")
        fhir_base_url = body.get("fhir_base_url", FHIR_BASE_URL)

        if not patient_id or not proposed_treatment:
            return JSONResponse(status_code=400, content={
                "error": "patient_id and proposed_treatment are required"
            })

        client = FHIRClient(fhir_base_url)
        patient_data = client.get_patient_bundle(patient_id)

        builder = PABuilder(patient_data, proposed_treatment, payer_name, clinician_name)
        pa_packet = builder.build_packet()

        return {
            "status": "success",
            "patient_id": patient_id,
            "proposed_treatment": proposed_treatment,
            "pa_packet": pa_packet
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─────────────────────────────────────────────
# Tool 3: Assess Denial Risk
# ─────────────────────────────────────────────
@app.post("/tools/assess_denial_risk")
async def assess_denial_risk(request: Request):
    try:
        body = await request.json()
        patient_id = body.get("patient_id")
        proposed_treatment = body.get("proposed_treatment")
        fhir_base_url = body.get("fhir_base_url", FHIR_BASE_URL)

        if not patient_id or not proposed_treatment:
            return JSONResponse(status_code=400, content={
                "error": "patient_id and proposed_treatment are required"
            })

        client = FHIRClient(fhir_base_url)
        patient_data = client.get_patient_bundle(patient_id)

        builder = PABuilder(patient_data, proposed_treatment)
        risk_assessment = builder.assess_denial_risk()

        return {
            "status": "success",
            "patient_id": patient_id,
            "proposed_treatment": proposed_treatment,
            "risk_assessment": risk_assessment
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "healthy", "service": "AuthBridge MCP Server"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
