import requests
from datetime import datetime


class FHIRClient:
    def __init__(self, base_url: str, token: str = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json"
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _get(self, resource_type: str, params: dict = None) -> dict:
        url = f"{self.base_url}/{resource_type}"
        response = requests.get(url, headers=self.headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_patient(self, patient_id: str) -> dict:
        return self._get(f"Patient/{patient_id}")

    def get_conditions(self, patient_id: str) -> list:
        bundle = self._get("Condition", {"patient": patient_id, "_count": "50"})
        return [e["resource"] for e in bundle.get("entry", [])]

    def get_medications(self, patient_id: str) -> list:
        bundle = self._get("MedicationRequest", {"patient": patient_id, "_count": "50"})
        return [e["resource"] for e in bundle.get("entry", [])]

    def get_observations(self, patient_id: str) -> list:
        bundle = self._get("Observation", {
            "patient": patient_id,
            "_count": "50",
            "_sort": "-date"
        })
        return [e["resource"] for e in bundle.get("entry", [])]

    def get_encounters(self, patient_id: str) -> list:
        bundle = self._get("Encounter", {
            "patient": patient_id,
            "_count": "20",
            "_sort": "-date"
        })
        return [e["resource"] for e in bundle.get("entry", [])]

    def get_allergies(self, patient_id: str) -> list:
        bundle = self._get("AllergyIntolerance", {"patient": patient_id})
        return [e["resource"] for e in bundle.get("entry", [])]

    def get_diagnostic_reports(self, patient_id: str) -> list:
        bundle = self._get("DiagnosticReport", {
            "patient": patient_id,
            "_count": "20",
            "_sort": "-date"
        })
        return [e["resource"] for e in bundle.get("entry", [])]

    def get_service_requests(self, patient_id: str) -> list:
        bundle = self._get("ServiceRequest", {"patient": patient_id})
        return [e["resource"] for e in bundle.get("entry", [])]

    def get_patient_bundle(self, patient_id: str) -> dict:
        """
        Fetches all relevant FHIR resources for a patient
        and returns a structured summary dict.
        """
        patient = self.get_patient(patient_id)

        # Extract patient demographics
        name_entry = patient.get("name", [{}])[0]
        given = " ".join(name_entry.get("given", []))
        family = name_entry.get("family", "")
        full_name = f"{given} {family}".strip()
        dob = patient.get("birthDate", "Unknown")
        gender = patient.get("gender", "Unknown")

        # Calculate age
        age = None
        if dob and dob != "Unknown":
            try:
                birth_year = int(dob.split("-")[0])
                age = datetime.now().year - birth_year
            except Exception:
                age = None

        # Fetch all resource types
        conditions = self.get_conditions(patient_id)
        medications = self.get_medications(patient_id)
        observations = self.get_observations(patient_id)
        encounters = self.get_encounters(patient_id)
        allergies = self.get_allergies(patient_id)
        diagnostic_reports = self.get_diagnostic_reports(patient_id)
        service_requests = self.get_service_requests(patient_id)

        # Parse conditions
        parsed_conditions = []
        for c in conditions:
            code_obj = c.get("code", {})
            codings = code_obj.get("coding", [{}])
            parsed_conditions.append({
                "name": code_obj.get("text") or codings[0].get("display", "Unknown condition"),
                "icd10": codings[0].get("code", ""),
                "status": c.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", ""),
                "onset": c.get("onsetDateTime", ""),
                "note": c.get("note", [{}])[0].get("text", "") if c.get("note") else ""
            })

        # Parse medications
        parsed_medications = []
        for m in medications:
            med_code = m.get("medicationCodeableConcept", {})
            status_reason = m.get("statusReason", {}).get("coding", [{}])[0].get("display", "")
            note = m.get("note", [{}])[0].get("text", "") if m.get("note") else ""
            parsed_medications.append({
                "name": med_code.get("text") or med_code.get("coding", [{}])[0].get("display", "Unknown"),
                "status": m.get("status", ""),
                "authored_on": m.get("authoredOn", ""),
                "status_reason": status_reason,
                "note": note
            })

        # Parse key observations
        parsed_observations = []
        for o in observations:
            code_obj = o.get("code", {})
            value = o.get("valueQuantity", {})
            interp = o.get("interpretation", [{}])[0].get("coding", [{}])[0].get("display", "")
            note = o.get("note", [{}])[0].get("text", "") if o.get("note") else ""
            parsed_observations.append({
                "name": code_obj.get("text") or code_obj.get("coding", [{}])[0].get("display", ""),
                "value": value.get("value"),
                "unit": value.get("unit", ""),
                "date": o.get("effectiveDateTime", ""),
                "interpretation": interp,
                "note": note
            })

        # Parse allergies
        parsed_allergies = []
        for a in allergies:
            code_obj = a.get("code", {})
            reactions = a.get("reaction", [])
            severity = reactions[0].get("severity", "") if reactions else ""
            parsed_allergies.append({
                "substance": code_obj.get("text") or code_obj.get("coding", [{}])[0].get("display", ""),
                "severity": severity,
                "status": a.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "active")
            })

        # Parse encounters
        parsed_encounters = []
        for e in encounters:
            period = e.get("period", {})
            reason = e.get("reasonCode", [{}])[0].get("text", "") if e.get("reasonCode") else ""
            participant = e.get("participant", [{}])[0].get("individual", {}).get("display", "") if e.get("participant") else ""
            parsed_encounters.append({
                "date": period.get("start", ""),
                "type": e.get("type", [{}])[0].get("coding", [{}])[0].get("display", "") if e.get("type") else "",
                "reason": reason,
                "clinician": participant
            })

        # Parse diagnostic reports
        parsed_reports = []
        for r in diagnostic_reports:
            parsed_reports.append({
                "name": r.get("code", {}).get("text", ""),
                "date": r.get("effectiveDateTime", ""),
                "conclusion": r.get("conclusion", "")
            })

        # Parse service requests
        parsed_service_requests = []
        for s in service_requests:
            code_obj = s.get("code", {})
            note = s.get("note", [{}])[0].get("text", "") if s.get("note") else ""
            parsed_service_requests.append({
                "service": code_obj.get("text") or code_obj.get("coding", [{}])[0].get("display", ""),
                "status": s.get("status", ""),
                "requester": s.get("requester", {}).get("display", ""),
                "note": note
            })

        return {
            "patient": {
                "id": patient_id,
                "name": full_name,
                "dob": dob,
                "age": age,
                "gender": gender
            },
            "conditions": parsed_conditions,
            "medications": parsed_medications,
            "observations": parsed_observations,
            "encounters": parsed_encounters,
            "allergies": parsed_allergies,
            "diagnostic_reports": parsed_reports,
            "service_requests": parsed_service_requests
        }
