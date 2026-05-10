from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fhir_client import FHIRClient
from pa_builder import PABuilder
import uvicorn
import json
import os

app = FastAPI(title="AuthBridge MCP Server", version="1.0.0")
FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")

def get_tools_list():
    return [
        {"name": "fetch_patient_fhir", "description": "Fetches a patient's full FHIR record including conditions, medications, observations, encounters, allergies, and diagnostic reports", "inputSchema": {"type": "object", "properties": {"patient_id": {"type": "string", "description": "FHIR Patient resource ID"}, "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server", "default": FHIR_BASE_URL}}, "required": ["patient_id"]}},
        {"name": "draft_prior_auth", "description": "Generates a complete payer-ready prior authorization packet from a patient FHIR record and proposed treatment", "inputSchema": {"type": "object", "properties": {"patient_id": {"type": "string"}, "proposed_treatment": {"type": "string"}, "payer_name": {"type": "string"}, "clinician_name": {"type": "string"}, "fhir_base_url": {"type": "string", "default": FHIR_BASE_URL}}, "required": ["patient_id", "proposed_treatment"]}},
        {"name": "assess_denial_risk", "description": "Scores the likelihood of prior authorization denial and returns top risk factors with mitigation steps", "inputSchema": {"type": "object", "properties": {"patient_id": {"type": "string"}, "proposed_treatment": {"type": "string"}, "fhir_base_url": {"type": "string", "default": FHIR_BASE_URL}}, "required": ["patient_id", "proposed_treatment"]}}
    ]

@app.get("/")
def root():
    return {"status": "AuthBridge MCP Server running", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "AuthBridge MCP Server"}

@app.get("/tools")
def list_tools_rest():
    return {"tools": get_tools_list()}

@app.get("/mcp")
def mcp_get():
    return {"name": "AuthBridge MCP Server", "version": "1.0.0", "protocolVersion": "2024-11-05", "tools": get_tools_list()}

@app.post("/mcp")
async def mcp_post(request: Request):
    try:
        body = await request.json()
        method = body.get("method", "")
        req_id = body.get("id", 1)

        if method == "initialize":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "AuthBridge MCP Server", "version": "1.0.0"}}}

        if method in ("notifications/initialized", "notifications/cancelled"):
            return {}

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": get_tools_list()}}

        if method == "tools/call":
            params = body.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            fhir_url = arguments.get("fhir_base_url", FHIR_BASE_URL)
            patient_id = arguments.get("patient_id")
            if not patient_id:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "patient_id is required"}}
            client = FHIRClient(fhir_url)

            if tool_name == "fetch_patient_fhir":
                data = client.get_patient_bundle(patient_id)
                return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}}

            elif tool_name == "draft_prior_auth":
                proposed = arguments.get("proposed_treatment", "")
                data = client.get_patient_bundle(patient_id)
                builder = PABuilder(data, proposed, arguments.get("payer_name", "Not specified"), arguments.get("clinician_name", "Not specified"))
                packet = builder.build_packet()
                return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(packet, indent=2)}]}}

            elif tool_name == "assess_denial_risk":
                data = client.get_patient_bundle(patient_id)
                builder = PABuilder(data, arguments.get("proposed_treatment", ""))
                risk = builder.assess_denial_risk()
                return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(risk, indent=2)}]}}

            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method '{method}' not supported"}}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/tools/fetch_patient_fhir")
async def fetch_patient_fhir(request: Request):
    try:
        body = await request.json()
        patient_id = body.get("patient_id")
        fhir_base_url = body.get("fhir_base_url", FHIR_BASE_URL)
        if not patient_id:
            return JSONResponse(status_code=400, content={"error": "patient_id is required"})
        client = FHIRClient(fhir_base_url)
        return {"status": "success", "patient_id": patient_id, "data": client.get_patient_bundle(patient_id)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/tools/draft_prior_auth")
async def draft_prior_auth(request: Request):
    try:
        body = await request.json()
        patient_id = body.get("patient_id")
        proposed_treatment = body.get("proposed_treatment")
        if not patient_id or not proposed_treatment:
            return JSONResponse(status_code=400, content={"error": "patient_id and proposed_treatment are required"})
        client = FHIRClient(body.get("fhir_base_url", FHIR_BASE_URL))
        data = client.get_patient_bundle(patient_id)
        builder = PABuilder(data, proposed_treatment, body.get("payer_name", "Not specified"), body.get("clinician_name", "Not specified"))
        return {"status": "success", "patient_id": patient_id, "pa_packet": builder.build_packet()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/tools/assess_denial_risk")
async def assess_denial_risk(request: Request):
    try:
        body = await request.json()
        patient_id = body.get("patient_id")
        proposed_treatment = body.get("proposed_treatment")
        if not patient_id or not proposed_treatment:
            return JSONResponse(status_code=400, content={"error": "patient_id and proposed_treatment are required"})
        client = FHIRClient(body.get("fhir_base_url", FHIR_BASE_URL))
        data = client.get_patient_bundle(patient_id)
        builder = PABuilder(data, proposed_treatment)
        return {"status": "success", "patient_id": patient_id, "risk_assessment": builder.assess_denial_risk()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
