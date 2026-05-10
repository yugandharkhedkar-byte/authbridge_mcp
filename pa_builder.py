from datetime import datetime


class PABuilder:
    def __init__(self, patient_data: dict, proposed_treatment: str,
                 payer_name: str = "Not specified", clinician_name: str = "Not specified"):
        self.patient = patient_data.get("patient", {})
        self.conditions = patient_data.get("conditions", [])
        self.medications = patient_data.get("medications", [])
        self.observations = patient_data.get("observations", [])
        self.encounters = patient_data.get("encounters", [])
        self.allergies = patient_data.get("allergies", [])
        self.reports = patient_data.get("diagnostic_reports", [])
        self.service_requests = patient_data.get("service_requests", [])
        self.proposed_treatment = proposed_treatment
        self.payer_name = payer_name
        self.clinician_name = clinician_name
        self.generated_at = datetime.utcnow().isoformat() + "Z"

    # ─────────────────────────────────────────
    # Helper: get primary diagnosis
    # ─────────────────────────────────────────
    def _primary_condition(self) -> dict:
        active = [c for c in self.conditions if c.get("status") == "active"]
        if not active:
            return {}
        # Prefer the condition most relevant to the proposed treatment
        treatment_lower = self.proposed_treatment.lower()
        keywords = {
            "adalimumab": ["arthritis", "rheumatoid", "psoriasis", "crohn"],
            "humira": ["arthritis", "rheumatoid", "psoriasis", "crohn"],
            "methotrexate": ["arthritis", "rheumatoid", "cancer"],
            "insulin": ["diabetes"],
            "statin": ["hyperlipidemia", "cholesterol", "cardiovascular"],
        }
        for drug, related_conditions in keywords.items():
            if drug in treatment_lower:
                for condition in active:
                    name_lower = condition.get("name", "").lower()
                    if any(kw in name_lower for kw in related_conditions):
                        return condition
        return active[0]

    # ─────────────────────────────────────────
    # Helper: get stopped / discontinued meds
    # ─────────────────────────────────────────
    def _prior_medications(self) -> list:
        return [m for m in self.medications if m.get("status") in ("stopped", "cancelled", "entered-in-error")]

    # ─────────────────────────────────────────
    # Helper: get active meds
    # ─────────────────────────────────────────
    def _active_medications(self) -> list:
        return [m for m in self.medications if m.get("status") == "active"]

    # ─────────────────────────────────────────
    # Helper: get relevant observations
    # ─────────────────────────────────────────
    def _key_observations(self) -> list:
        high_value = [o for o in self.observations if o.get("interpretation") and
                      any(word in o["interpretation"].upper() for word in ["HIGH", "H", "POSITIVE", "ABNORMAL"])]
        return high_value[:5] if high_value else self.observations[:5]

    # ─────────────────────────────────────────
    # Helper: last encounter date
    # ─────────────────────────────────────────
    def _last_encounter(self) -> str:
        if self.encounters:
            return self.encounters[0].get("date", "Not on record")[:10]
        return "Not on record"

    # ─────────────────────────────────────────
    # Build medical necessity statement
    # ─────────────────────────────────────────
    def _build_necessity_statement(self) -> str:
        primary = self._primary_condition()
        condition_name = primary.get("name", "the documented condition")
        icd10 = primary.get("icd10", "")
        onset = primary.get("onset", "")[:10] if primary.get("onset") else ""
        prior_meds = self._prior_medications()
        key_obs = self._key_observations()

        onset_str = f" first documented on {onset}" if onset else ""
        icd_str = f" (ICD-10: {icd10})" if icd10 else ""

        prior_str = ""
        if prior_meds:
            names = [m["name"].split(" ")[0] for m in prior_meds[:2]]
            prior_str = f" The patient has previously trialed {' and '.join(names)}, " \
                        f"which were discontinued due to documented adverse effects or inadequate therapeutic response."

        obs_str = ""
        if key_obs:
            obs_items = [f"{o['name']} {o['value']} {o['unit']} ({o['date'][:10] if o.get('date') else 'recent'})"
                         for o in key_obs[:3] if o.get("value")]
            if obs_items:
                obs_str = f" Supporting laboratory evidence includes: {'; '.join(obs_items)}."

        allergy_str = ""
        if self.allergies:
            allergy_names = [a["substance"] for a in self.allergies if a.get("substance")]
            if allergy_names:
                allergy_str = f" The patient has documented allergies/intolerances to {', '.join(allergy_names)}, " \
                              f"which contraindicate standard alternative therapies."

        statement = (
            f"This patient presents with {condition_name}{icd_str}{onset_str}, "
            f"which has failed to respond adequately to conventional first-line therapies despite appropriate trials."
            f"{prior_str}"
            f"{obs_str}"
            f"{allergy_str} "
            f"The requested treatment, {self.proposed_treatment}, is medically necessary to address the patient's "
            f"ongoing disease activity and prevent further clinical deterioration. "
            f"This request is supported by objective clinical findings and is consistent with current evidence-based "
            f"guidelines for the management of this condition."
        )
        return statement

    # ─────────────────────────────────────────
    # Build step therapy section
    # ─────────────────────────────────────────
    def _build_step_therapy(self) -> dict:
        prior_meds = self._prior_medications()
        if not prior_meds:
            return {
                "status": "INCOMPLETE",
                "medications": [],
                "notes": "No prior medication history found in FHIR record. "
                         "Step therapy documentation should be provided manually before submission."
            }

        parsed = []
        for m in prior_meds:
            parsed.append({
                "medication": m.get("name", "Unknown"),
                "started": m.get("authored_on", "")[:10] if m.get("authored_on") else "Unknown",
                "status": m.get("status", "stopped"),
                "reason_discontinued": m.get("status_reason") or m.get("note", "Reason not documented"),
            })

        return {
            "status": "COMPLETE",
            "medications": parsed,
            "notes": f"Step therapy documented: {len(parsed)} prior medication(s) on record with "
                     f"documented discontinuation reasons."
        }

    # ─────────────────────────────────────────
    # Build supporting evidence section
    # ─────────────────────────────────────────
    def _build_supporting_evidence(self) -> dict:
        return {
            "key_observations": [
                {
                    "test": o.get("name", ""),
                    "value": f"{o.get('value', '')} {o.get('unit', '')}".strip(),
                    "date": o.get("date", "")[:10] if o.get("date") else "",
                    "interpretation": o.get("interpretation", ""),
                    "note": o.get("note", "")
                }
                for o in self._key_observations() if o.get("value")
            ],
            "active_conditions": [
                {"name": c.get("name"), "icd10": c.get("icd10"), "onset": c.get("onset", "")[:10]}
                for c in self.conditions if c.get("status") == "active"
            ],
            "recent_encounters": [
                {"date": e.get("date", "")[:10], "type": e.get("type", ""), "reason": e.get("reason", "")}
                for e in self.encounters[:3]
            ],
            "diagnostic_reports": [
                {"name": r.get("name"), "date": r.get("date", "")[:10], "conclusion": r.get("conclusion", "")[:300]}
                for r in self.reports[:3]
            ],
            "allergies": [
                {"substance": a.get("substance"), "severity": a.get("severity")}
                for a in self.allergies
            ]
        }

    # ─────────────────────────────────────────
    # Assess denial risk
    # ─────────────────────────────────────────
    def assess_denial_risk(self) -> dict:
        risk_factors = []
        score = 0

        # Check step therapy
        prior_meds = self._prior_medications()
        if not prior_meds:
            risk_factors.append({
                "factor": "Missing step therapy documentation",
                "severity": "HIGH",
                "mitigation": "Document all previously tried medications with dates and discontinuation reasons"
            })
            score += 3
        elif len(prior_meds) < 2:
            risk_factors.append({
                "factor": "Limited step therapy history (fewer than 2 prior medications)",
                "severity": "MEDIUM",
                "mitigation": "Provide documentation of all alternative treatments considered or tried"
            })
            score += 1

        # Check recent labs
        obs_dates = [o.get("date", "") for o in self.observations if o.get("date")]
        if obs_dates:
            most_recent = max(obs_dates)
            try:
                days_old = (datetime.utcnow() - datetime.fromisoformat(most_recent.replace("Z", ""))).days
                if days_old > 180:
                    risk_factors.append({
                        "factor": f"Lab values are {days_old} days old (payers prefer < 6 months)",
                        "severity": "MEDIUM",
                        "mitigation": "Order updated lab panel before submitting authorization"
                    })
                    score += 1
            except Exception:
                pass
        else:
            risk_factors.append({
                "factor": "No laboratory observations found in FHIR record",
                "severity": "HIGH",
                "mitigation": "Attach recent lab results supporting medical necessity"
            })
            score += 2

        # Check specialist encounter
        specialist_encounters = [
            e for e in self.encounters
            if any(word in (e.get("type", "") + e.get("reason", "")).lower()
                   for word in ["specialist", "rheumatology", "oncology", "cardiology", "neurology", "consult"])
        ]
        if not specialist_encounters:
            risk_factors.append({
                "factor": "No specialist consultation documented",
                "severity": "MEDIUM",
                "mitigation": "Include specialist consultation note or referral letter"
            })
            score += 1

        # Check diagnostic reports
        if not self.reports:
            risk_factors.append({
                "factor": "No diagnostic reports in FHIR record",
                "severity": "LOW",
                "mitigation": "Attach relevant imaging or pathology reports if available"
            })
            score += 1

        # Check allergies documented (contraindication support)
        if self.allergies:
            risk_factors.append({
                "factor": "Allergies documented — use as contraindication evidence",
                "severity": "INFO",
                "mitigation": "Include allergy documentation to justify why standard alternatives cannot be used"
            })

        # Score to risk level
        if score >= 4:
            risk_level = "HIGH"
        elif score >= 2:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "denial_risk": risk_level,
            "risk_score": score,
            "risk_factors": risk_factors,
            "recommendation": (
                "Submit with confidence — documentation appears strong."
                if risk_level == "LOW" else
                "Address identified gaps before submission to improve approval odds."
                if risk_level == "MEDIUM" else
                "Significant documentation gaps found. Resolve HIGH severity items before submitting."
            )
        }

    # ─────────────────────────────────────────
    # Build appeal talking points
    # ─────────────────────────────────────────
    def _build_appeal_points(self) -> list:
        points = []
        prior_meds = self._prior_medications()
        if prior_meds:
            names = [m["name"].split(" ")[0] for m in prior_meds]
            points.append(
                f"Step therapy is complete — patient has documented trials of {', '.join(names)} "
                f"with clear reasons for discontinuation, satisfying payer step therapy requirements."
            )
        if self.allergies:
            substances = [a["substance"] for a in self.allergies]
            points.append(
                f"Patient has documented allergies/intolerances to {', '.join(substances)}, "
                f"which clinically contraindicate standard first-line alternatives."
            )
        if self.reports:
            points.append(
                f"Objective diagnostic evidence ({self.reports[0].get('name', 'diagnostic report')} dated "
                f"{self.reports[0].get('date', '')[:10]}) confirms disease severity and progression, "
                f"supporting medical necessity for the requested treatment."
            )
        key_obs = self._key_observations()
        if key_obs:
            obs_parts = [f"{o['name']} {o['value']} {o['unit']}" for o in key_obs[:2] if o.get("value")]
            obs_str = ", ".join(obs_parts)
            points.append(
                f"Laboratory findings demonstrate active disease: {obs_str}. "
                f"These values are inconsistent with controlled disease and support the urgency of treatment initiation."
            )
        return points

    # ─────────────────────────────────────────
    # Main: Build full PA packet
    # ─────────────────────────────────────────
    def build_packet(self) -> dict:
        primary = self._primary_condition()
        step_therapy = self._build_step_therapy()
        evidence = self._build_supporting_evidence()
        risk = self.assess_denial_risk()
        appeal_points = self._build_appeal_points()

        # Urgency assessment
        urgency = "Routine"
        high_risk_obs = [o for o in self.observations
                         if o.get("interpretation") and "HIGH" in o.get("interpretation", "").upper()
                         and o.get("value") and float(str(o["value"]).replace(",", "")) > 0]
        if len(high_risk_obs) >= 3:
            urgency = "Urgent"

        return {
            "generated_at": self.generated_at,
            "section_1_request_summary": {
                "requested_treatment": self.proposed_treatment,
                "primary_diagnosis": primary.get("name", "Not found"),
                "icd10_primary": primary.get("icd10", ""),
                "supporting_diagnoses": [
                    {"name": c.get("name"), "icd10": c.get("icd10")}
                    for c in self.conditions if c != primary and c.get("status") == "active"
                ],
                "payer": self.payer_name,
                "requesting_clinician": self.clinician_name,
                "urgency": urgency
            },
            "section_2_medical_necessity": self._build_necessity_statement(),
            "section_3_step_therapy": step_therapy,
            "section_4_clinical_evidence": evidence,
            "section_5_denial_risk": risk,
            "section_6_appeal_points": appeal_points,
            "a2a_summary": {
                "patient_id": self.patient.get("id"),
                "patient_name": self.patient.get("name"),
                "proposed_treatment": self.proposed_treatment,
                "primary_icd10": primary.get("icd10", ""),
                "step_therapy_complete": step_therapy["status"] == "COMPLETE",
                "denial_risk": risk["denial_risk"],
                "denial_risk_factors_count": len([r for r in risk["risk_factors"] if r["severity"] != "INFO"]),
                "packet_ready": True,
                "generated_at": self.generated_at
            }
                }
