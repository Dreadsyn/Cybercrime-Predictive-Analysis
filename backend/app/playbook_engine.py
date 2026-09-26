"""
Investigator Action Playbook Engine (Milestone 1, Feature 7).

Generates contextual, prioritized tactical standard operating procedures (SOPs)
for cybercrime law enforcement investigators based on:
1. Calibrated prediction confidence and predicted ATM location
2. Operational priority triage score (0-100) and priority level
3. Estimated intervention lead-time window
4. Point-in-time explainability codes and financial channel characteristics
"""

from typing import Any, Dict, List, Optional


def generate_investigator_playbook(prediction_data: dict) -> dict:
    """
    Generates a structured, prioritized investigator action playbook
    tailored to the specific prediction output.

    Parameters:
        prediction_data (dict): Prediction record dictionary containing:
            - predicted_atm_id (str)
            - predicted_zone_id (str)
            - priority_score (int)
            - priority_level (str)
            - confidence_score (float)
            - predicted_window_start (str)
            - predicted_window_end (str)
            - explanation_codes (list[str])
            - top_candidates (list[dict])
            - reported_amount (float, optional)
            - payment_channel (str, optional)
            - mule_bank_code (str, optional)

    Returns:
        dict: Structured InvestigatorPlaybook object.
    """
    pred_atm = prediction_data.get("predicted_atm_id", "ATM-UNKNOWN")
    pred_zone = prediction_data.get("predicted_zone_id", "ZONE_CENTRAL")
    zone_name = pred_zone.replace("ZONE_", "Zone ").title()
    priority_level = (prediction_data.get("priority_level") or "LOW").upper()
    priority_score = int(prediction_data.get("priority_score", 0))
    confidence_score = float(prediction_data.get("confidence_score", 0.0))
    conf_pct = round(confidence_score * 100, 1)

    window_start = prediction_data.get("predicted_window_start", "")
    window_end = prediction_data.get("predicted_window_end", "")
    if len(window_start) >= 16 and len(window_end) >= 16:
        window_display = f"{window_start[11:16]} - {window_end[11:16]} hrs"
    else:
        window_display = "Immediate 45-min Tactical Window"

    explanation_codes = prediction_data.get("explanation_codes", [])
    top_candidates = prediction_data.get("top_candidates", [])
    payment_channel = prediction_data.get("payment_channel", "UPI")
    mule_bank = prediction_data.get("mule_bank_code", "Beneficiary Bank").replace("BANK_", "").replace("_SYNTH", "")
    reported_amt = prediction_data.get("reported_amount")

    actions: List[Dict[str, Any]] = []
    step_num = 1

    # --------------------------------------------------------------------------
    # 1. FIELD PATROL & DIRECT INTERCEPTION DISPOSITION
    # --------------------------------------------------------------------------
    if priority_level == "CRITICAL":
        disposition = "RAPID_TACTICAL_INTERCEPTION"
        summary = (
            f"CRITICAL DISPATCH: Immediate physical interdiction warranted at {pred_atm} ({zone_name}). "
            f"Composite priority score of {priority_score}/100 indicates active, imminent cash withdrawal runner activity."
        )
        actions.append({
            "step": step_num,
            "title": "Immediate Tactical Patrol Dispatch",
            "action_type": "PATROL_DISPATCH",
            "urgency": "IMMEDIATE",
            "target": f"Primary Terminal: {pred_atm} ({zone_name})",
            "description": (
                f"Vector nearest PCR mobile van / beat unit to {pred_atm} immediately. Establish perimeter visual surveillance. "
                f"Verify person(s) at ATM kiosk using multiple cards or mobile phones."
            ),
            "rationale": (
                f"High priority triage ({priority_score}/100) and calibrated spatial concentration ({conf_pct}%) "
                f"indicate critical withdrawal probability during {window_display}."
            ),
        })
        step_num += 1

    elif priority_level == "HIGH":
        disposition = "PRIORITY_PATROL_MONITORING"
        summary = (
            f"HIGH PRIORITY ALERT: Deploy sector patrol units to {pred_atm} ({zone_name}). "
            f"Priority score {priority_score}/100 indicates elevated cash-out vulnerability during {window_display}."
        )
        actions.append({
            "step": step_num,
            "title": "Priority Sector Patrol Alert",
            "action_type": "PATROL_DISPATCH",
            "urgency": "HIGH",
            "target": f"Primary Terminal: {pred_atm} ({zone_name})",
            "description": (
                f"Alert local police station beat staff to conduct roving inspections at {pred_atm}. "
                f"Maintain visual check for unusual waiting vehicles or repeated transaction attempts."
            ),
            "rationale": (
                f"Elevated spatial probability ({conf_pct}%) and active corridor concentration warrant focused patrol coverage."
            ),
        })
        step_num += 1

    elif priority_level == "MEDIUM":
        disposition = "ELEVATED_BEAT_CANVASS"
        summary = (
            f"MODERATE MONITORING: Incorporate {pred_atm} into scheduled beat patrol checks in {zone_name}. "
            f"Priority score {priority_score}/100 indicates secondary monitoring required."
        )
        actions.append({
            "step": step_num,
            "title": "Sector Beat Patrol Canvass",
            "action_type": "ZONE_MONITORING",
            "urgency": "STANDARD",
            "target": f"Sector ATM: {pred_atm} ({zone_name})",
            "description": (
                f"Task beat constables to inspect {pred_atm} during regular surveillance rounds within {window_display}."
            ),
            "rationale": f"Moderate confidence ({conf_pct}%) suggests scheduled rather than emergency vehicle diversion.",
        })
        step_num += 1

    else:
        disposition = "ROUTINE_AUDIT_LOGGING"
        summary = (
            f"ROUTINE AUDIT: Log prediction for post-incident review at {pred_atm}. "
            f"Lower priority score ({priority_score}/100) indicates delayed reporting or low spatial concentration."
        )
        actions.append({
            "step": step_num,
            "title": "Station Diary & Audit Log Entry",
            "action_type": "ROUTINE_LOG",
            "urgency": "STANDARD",
            "target": f"Incident Record: {pred_atm}",
            "description": (
                f"Record forecasted ATM {pred_atm} into cybercrime station diary. Await bank statement settlement confirmation."
            ),
            "rationale": "Extended reporting delay or dispersed probability; immediate physical dispatch not cost-effective.",
        })
        step_num += 1

    # --------------------------------------------------------------------------
    # 2. FINANCIAL RAIL & MULE ACCOUNT BLOCKING (1930 / CFI)
    # --------------------------------------------------------------------------
    if "HIGH_VELOCITY_CHANNEL" in explanation_codes or payment_channel in ["UPI", "IMPS"]:
        actions.append({
            "step": step_num,
            "title": "1930 / CFI Electronic Lien & Account Freeze",
            "action_type": "FINANCIAL_FREEZE",
            "urgency": "IMMEDIATE" if priority_level in ["CRITICAL", "HIGH"] else "HIGH",
            "target": f"Beneficiary Account at {mule_bank}",
            "description": (
                f"Execute emergency debit freeze on Citizen Financial Cyber Fraud Reporting System (1930 / CFCFRMS). "
                f"Directly flag beneficiary mule account with {mule_bank} to block card/ATM cash-out authorization."
            ),
            "rationale": (
                f"Instant payment channel ({payment_channel}) implies fast multi-layered dispersal; "
                f"lien freeze prevents secondary cash conversion."
            ),
        })
        step_num += 1
    else:
        actions.append({
            "step": step_num,
            "title": "Bank Nodal Officer Account Inward Review",
            "action_type": "FINANCIAL_LIAISON",
            "urgency": "STANDARD",
            "target": f"{mule_bank} Cyber Nodal Desk",
            "description": (
                f"Notify {mule_bank} nodal officer to inspect inward NEFT/clearing batch and apply temporary hold "
                f"on suspect beneficiary account."
            ),
            "rationale": f"Batch payment channel ({payment_channel}) offers clearing window before debit authorization.",
        })
        step_num += 1

    # --------------------------------------------------------------------------
    # 3. SECONDARY / NEARBY CLUSTER ATM PERIMETER REVIEW
    # --------------------------------------------------------------------------
    if len(top_candidates) >= 2:
        cand2 = top_candidates[1]
        cand2_id = cand2.get("atm_id", "N/A")
        cand2_zone = cand2.get("zone_id", "").replace("ZONE_", "Zone ").title()
        cand2_prob = round(float(cand2.get("probability", 0.0)) * 100, 1)

        cand3_text = ""
        if len(top_candidates) >= 3:
            cand3 = top_candidates[2]
            cand3_id = cand3.get("atm_id", "N/A")
            cand3_prob = round(float(cand3.get("probability", 0.0)) * 100, 1)
            cand3_text = f" and #{cand3.get('rank', 3)} {cand3_id} ({cand3_prob}%)"

        actions.append({
            "step": step_num,
            "title": "Secondary Candidate ATM Perimeter Review",
            "action_type": "CLUSTER_REVIEW",
            "urgency": "HIGH" if priority_level == "CRITICAL" else "STANDARD",
            "target": f"Alternative Terminals: {cand2_id} ({cand2_prob}%){cand3_text}",
            "description": (
                f"Alert adjoining beat patrols to inspect secondary candidate {cand2_id} ({cand2_zone}) "
                f"if primary target {pred_atm} has no cash or runner encounters security presence."
            ),
            "rationale": (
                f"Calibrated spatial ranking reveals runners frequently divert to secondary cluster terminals within a 500m catchment."
            ),
        })
        step_num += 1

    # --------------------------------------------------------------------------
    # 4. LOCATION-SPECIFIC VULNERABILITY / CORRIDOR TACTIC
    # --------------------------------------------------------------------------
    if "ON_US_BANK_MATCH" in explanation_codes:
        actions.append({
            "step": step_num,
            "title": "On-Us Terminal Telemetry Coordination",
            "action_type": "TELEMETRY_MONITOR",
            "urgency": "HIGH",
            "target": f"{mule_bank} Switch Operations",
            "description": (
                f"Contact {mule_bank} ATM Switch / SOC to monitor real-time transaction attempts at terminal {pred_atm}. "
                f"Request instant notification for cardless OTP or ATM PIN entries."
            ),
            "rationale": "On-us bank match enables direct cardless or debit withdrawal without inter-bank settlement delays.",
        })
        step_num += 1

    elif "LOW_SURVEILLANCE_RISK" in explanation_codes:
        actions.append({
            "step": step_num,
            "title": "Standalone Kiosk Tactical Observation",
            "action_type": "SURVEILLANCE_TACTIC",
            "urgency": "HIGH",
            "target": f"Kiosk Perimeter: {pred_atm}",
            "description": (
                f"Discreetly observe the entrance of standalone kiosk {pred_atm}. Look for idling motorcycles/scooters "
                f"or individuals entering while wearing full-face helmets or masks."
            ),
            "rationale": "Standalone kiosks lack dedicated guards and are systematically preferred by cash-out mules for swift exits.",
        })
        step_num += 1

    elif "HOTSPOT_CORRIDOR" in explanation_codes:
        actions.append({
            "step": step_num,
            "title": "Historical Hotspot Corridor Intercept",
            "action_type": "CORRIDOR_TACTIC",
            "urgency": "HIGH",
            "target": f"{zone_name} Commercial Transit Corridor",
            "description": (
                f"Position mobile patrol at key choke points along the {zone_name} corridor leading to {pred_atm}. "
                f"Coordinate with local market security."
            ),
            "rationale": "Target ATM is embedded in a historically proven withdrawal hotspot corridor with high repeat activity.",
        })
        step_num += 1

    # --------------------------------------------------------------------------
    # 5. EVIDENCE & CCTV PRESERVATION (SECTION 91 CrPC)
    # --------------------------------------------------------------------------
    actions.append({
        "step": step_num,
        "title": "CCTV & ATM Electronic Journal (EJ) Preservation",
        "action_type": "EVIDENCE_PRESERVATION",
        "urgency": "HIGH" if priority_level in ["CRITICAL", "HIGH"] else "STANDARD",
        "target": f"Terminal {pred_atm} Footage & Controller",
        "description": (
            f"Issue urgent Section 91 CrPC requisition to bank branch manager / ATM custodian to preserve: "
            f"(1) External entrance camera footage, (2) Pinhole fascia camera video, and (3) Electronic Journal (EJ) log "
            f"for time window {window_display}."
        ),
        "rationale": (
            f"ATM surveillance footage is subject to 15-to-30 day circular overwrite loops; "
            f"immediate preservation secures physical biometric evidence of runner."
        ),
    })
    step_num += 1

    # --------------------------------------------------------------------------
    # 6. JURISDICTIONAL COORDINATION & BROADCAST
    # --------------------------------------------------------------------------
    actions.append({
        "step": step_num,
        "title": "Jurisdictional Sector PCR Broadcast",
        "action_type": "SECTOR_BROADCAST",
        "urgency": "STANDARD",
        "target": f"{zone_name} Cyber & Law Enforcement Net",
        "description": (
            f"Broadcast brief to all {zone_name} field patrols: Suspect mule bank {mule_bank}, "
            f"predicted target {pred_atm}, estimated cash-out window {window_display}."
        ),
        "rationale": "Maintains multi-beat situational awareness in case suspect moves across sector boundaries.",
    })

    # --------------------------------------------------------------------------
    # GENERATE COPYABLE DISPATCH BRIEF
    # --------------------------------------------------------------------------
    amt_str = f" | Amount: INR {int(reported_amt):,}" if reported_amt else ""
    dispatch_brief = (
        f"[POLICE CYBERCRIME DISPATCH BRIEF]\n"
        f"PRIORITY: {priority_level} (Score: {priority_score}/100)\n"
        f"DISPOSITION: {disposition}\n"
        f"PREDICTED ATM: {pred_atm} ({zone_name})\n"
        f"TACTICAL WINDOW: {window_display}\n"
        f"SUSPECT MULE BANK: {mule_bank}{amt_str}\n"
        f"ACTION 1: {actions[0]['description']}\n"
        f"ACTION 2: {actions[1]['description']}\n"
        f"COORDINATION: Notify {zone_name} PCR units."
    )

    return {
        "disposition": disposition,
        "summary": summary,
        "total_actions": len(actions),
        "estimated_lead_time_window": window_display,
        "dispatch_brief": dispatch_brief,
        "actions": actions,
    }
