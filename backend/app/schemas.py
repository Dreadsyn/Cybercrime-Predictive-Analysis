"""
Pydantic Request & Response Validation Schemas.

Enforces schema contracts for:
1. Complaint inputs and outputs
2. Real-time prediction requests and responses
3. ATM coordinates and hotspot queries
4. Dashboard KPI stats
5. Model information and evaluation provenance
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

# Allowed operational categorical domains
VALID_CRIME_CATEGORIES = ("EXTORTION", "INVESTMENT_FRAUD", "LOAN_SCAM", "PHISHING_UPI", "TASK_FRAUD")
VALID_PAYMENT_CHANNELS = ("IMPS", "NEFT", "UPI")
VALID_MULE_BANKS = ("BANK_AXIS_SYNTH", "BANK_HDFC_SYNTH", "BANK_ICIC_SYNTH", "BANK_PNB_SYNTH", "BANK_SBI_SYNTH")
VALID_ACCOUNT_TIERS = ("NEW_DIGITAL", "RURAL_REGIONAL", "STANDARD")
VALID_BRANCH_ZONES = ("ZONE_CENTRAL", "ZONE_EAST", "ZONE_NORTH", "ZONE_SOUTH", "ZONE_WEST")


# ==============================================================================
# 1. COMPLAINT SCHEMAS
# ==============================================================================
class ComplaintCreate(BaseModel):
    crime_category: str = Field(..., json_schema_extra={"example": "INVESTMENT_FRAUD"})
    reported_amount: float = Field(..., gt=0, json_schema_extra={"example": 75000.0})
    payment_channel: str = Field(..., json_schema_extra={"example": "UPI"})
    mule_bank_code: str = Field(..., json_schema_extra={"example": "BANK_SBI_SYNTH"})
    mule_account_tier: str = Field(..., json_schema_extra={"example": "NEW_DIGITAL"})
    mule_branch_zone: str = Field(..., json_schema_extra={"example": "ZONE_WEST"})
    reporting_delay_mins: float = Field(..., ge=0, json_schema_extra={"example": 35.0})
    incident_hour: int = Field(..., ge=0, le=23, json_schema_extra={"example": 15})
    incident_day_of_week: int = Field(..., ge=0, le=6, json_schema_extra={"example": 4})
    complaint_timestamp: Optional[str] = Field(None, json_schema_extra={"example": "2026-09-26 15:30:00"})
    incident_timestamp: Optional[str] = Field(None, json_schema_extra={"example": "2026-09-26 14:55:00"})
    complaint_id: Optional[str] = None

    @field_validator("crime_category")
    @classmethod
    def validate_crime_category(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("crime_category is required.")
        val = v.strip().upper()
        if val not in VALID_CRIME_CATEGORIES:
            raise ValueError(f"Invalid crime_category '{v}'. Allowed: {', '.join(VALID_CRIME_CATEGORIES)}")
        return val

    @field_validator("payment_channel")
    @classmethod
    def validate_payment_channel(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("payment_channel is required.")
        val = v.strip().upper()
        if val not in VALID_PAYMENT_CHANNELS:
            raise ValueError(f"Invalid payment_channel '{v}'. Allowed: {', '.join(VALID_PAYMENT_CHANNELS)}")
        return val

    @field_validator("mule_bank_code")
    @classmethod
    def validate_mule_bank_code(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("mule_bank_code is required.")
        val = v.strip().upper()
        if val not in VALID_MULE_BANKS:
            raise ValueError(f"Invalid mule_bank_code '{v}'. Allowed: {', '.join(VALID_MULE_BANKS)}")
        return val

    @field_validator("mule_account_tier")
    @classmethod
    def validate_mule_account_tier(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("mule_account_tier is required.")
        val = v.strip().upper()
        if val not in VALID_ACCOUNT_TIERS:
            raise ValueError(f"Invalid mule_account_tier '{v}'. Allowed: {', '.join(VALID_ACCOUNT_TIERS)}")
        return val

    @field_validator("mule_branch_zone")
    @classmethod
    def validate_mule_branch_zone(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("mule_branch_zone is required.")
        val = v.strip().upper()
        if val not in VALID_BRANCH_ZONES:
            raise ValueError(f"Invalid mule_branch_zone '{v}'. Allowed: {', '.join(VALID_BRANCH_ZONES)}")
        return val

    @field_validator("reported_amount")
    @classmethod
    def validate_reported_amount(cls, v: float) -> float:
        if v is None or v <= 0:
            raise ValueError("reported_amount must be greater than 0.")
        return float(v)

    @field_validator("reporting_delay_mins")
    @classmethod
    def validate_reporting_delay_mins(cls, v: float) -> float:
        if v is None or v < 0:
            raise ValueError("reporting_delay_mins must be 0 or greater.")
        return float(v)

    @field_validator("incident_hour")
    @classmethod
    def validate_incident_hour(cls, v: int) -> int:
        if v is None or not (0 <= v <= 23):
            raise ValueError("incident_hour must be an integer between 0 and 23.")
        return int(v)

    @field_validator("incident_day_of_week")
    @classmethod
    def validate_incident_day_of_week(cls, v: int) -> int:
        if v is None or not (0 <= v <= 6):
            raise ValueError("incident_day_of_week must be an integer between 0 (Monday) and 6 (Sunday).")
        return int(v)


class ComplaintResponse(BaseModel):
    complaint_id: str
    incident_timestamp: str
    complaint_timestamp: str
    reporting_delay_mins: float
    crime_category: str
    reported_amount: float
    payment_channel: str
    mule_bank_code: str
    mule_account_tier: str
    mule_branch_zone: str
    incident_hour: int
    incident_day_of_week: int
    complaint_status: str


# ==============================================================================
# 2. PREDICTION SCHEMAS
# ==============================================================================
class CandidateATM(BaseModel):
    rank: int
    atm_id: str
    bank_code: str
    zone_id: str
    location_type: str
    latitude: float
    longitude: float
    probability: float
    historical_cashout_count: int


class PredictionRequest(BaseModel):
    crime_category: str = Field(..., json_schema_extra={"example": "INVESTMENT_FRAUD"})
    reported_amount: float = Field(..., gt=0, json_schema_extra={"example": 85000.0})
    payment_channel: str = Field(..., json_schema_extra={"example": "UPI"})
    mule_bank_code: str = Field(..., json_schema_extra={"example": "BANK_SBI_SYNTH"})
    mule_account_tier: str = Field(..., json_schema_extra={"example": "NEW_DIGITAL"})
    mule_branch_zone: str = Field(..., json_schema_extra={"example": "ZONE_NORTH"})
    reporting_delay_mins: float = Field(..., ge=0, json_schema_extra={"example": 40.0})
    incident_hour: int = Field(..., ge=0, le=23, json_schema_extra={"example": 14})
    incident_day_of_week: int = Field(..., ge=0, le=6, json_schema_extra={"example": 4})
    complaint_timestamp: Optional[str] = Field(None, json_schema_extra={"example": "2026-09-26 14:55:00"})
    complaint_id: Optional[str] = Field(None, json_schema_extra={"example": "CMP-LIVE-001"})

    @field_validator("crime_category")
    @classmethod
    def validate_crime_category(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("crime_category is required.")
        val = v.strip().upper()
        if val not in VALID_CRIME_CATEGORIES:
            raise ValueError(f"Invalid crime_category '{v}'. Allowed: {', '.join(VALID_CRIME_CATEGORIES)}")
        return val

    @field_validator("payment_channel")
    @classmethod
    def validate_payment_channel(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("payment_channel is required.")
        val = v.strip().upper()
        if val not in VALID_PAYMENT_CHANNELS:
            raise ValueError(f"Invalid payment_channel '{v}'. Allowed: {', '.join(VALID_PAYMENT_CHANNELS)}")
        return val

    @field_validator("mule_bank_code")
    @classmethod
    def validate_mule_bank_code(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("mule_bank_code is required.")
        val = v.strip().upper()
        if val not in VALID_MULE_BANKS:
            raise ValueError(f"Invalid mule_bank_code '{v}'. Allowed: {', '.join(VALID_MULE_BANKS)}")
        return val

    @field_validator("mule_account_tier")
    @classmethod
    def validate_mule_account_tier(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("mule_account_tier is required.")
        val = v.strip().upper()
        if val not in VALID_ACCOUNT_TIERS:
            raise ValueError(f"Invalid mule_account_tier '{v}'. Allowed: {', '.join(VALID_ACCOUNT_TIERS)}")
        return val

    @field_validator("mule_branch_zone")
    @classmethod
    def validate_mule_branch_zone(cls, v: str) -> str:
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("mule_branch_zone is required.")
        val = v.strip().upper()
        if val not in VALID_BRANCH_ZONES:
            raise ValueError(f"Invalid mule_branch_zone '{v}'. Allowed: {', '.join(VALID_BRANCH_ZONES)}")
        return val

    @field_validator("reported_amount")
    @classmethod
    def validate_reported_amount(cls, v: float) -> float:
        if v is None or v <= 0:
            raise ValueError("reported_amount must be greater than 0.")
        return float(v)

    @field_validator("reporting_delay_mins")
    @classmethod
    def validate_reporting_delay_mins(cls, v: float) -> float:
        if v is None or v < 0:
            raise ValueError("reporting_delay_mins must be 0 or greater.")
        return float(v)

    @field_validator("incident_hour")
    @classmethod
    def validate_incident_hour(cls, v: int) -> int:
        if v is None or not (0 <= v <= 23):
            raise ValueError("incident_hour must be an integer between 0 and 23.")
        return int(v)

    @field_validator("incident_day_of_week")
    @classmethod
    def validate_incident_day_of_week(cls, v: int) -> int:
        if v is None or not (0 <= v <= 6):
            raise ValueError("incident_day_of_week must be an integer between 0 (Monday) and 6 (Sunday).")
        return int(v)



class PlaybookAction(BaseModel):
    step: int
    title: str
    action_type: str
    urgency: str
    target: str
    description: str
    rationale: str


class InvestigatorPlaybook(BaseModel):
    disposition: str
    summary: str
    total_actions: int
    estimated_lead_time_window: str
    dispatch_brief: str
    actions: List[PlaybookAction]


class PredictionResponse(BaseModel):
    prediction_id: str
    complaint_id: str
    prediction_timestamp: str
    predicted_atm_id: str
    predicted_zone_id: str
    confidence_score: float
    top_candidates: List[CandidateATM]
    predicted_window_start: str
    predicted_window_end: str
    risk_level: str
    explanation_codes: List[str]
    action_status: str
    priority_score: int = Field(..., ge=0, le=100, description="Deterministic 0-100 intervention priority score")
    priority_level: str = Field(..., description="Operational triage level: LOW, MEDIUM, HIGH, CRITICAL")
    priority_reasons: List[str] = Field(default_factory=list, description="2-4 concise reasons explaining the score")
    playbook: Optional[InvestigatorPlaybook] = None
    alert_state: str = Field(default="NEW", description="Alert lifecycle state: NEW, REFRESHED, ESCALATED")
    occurrence_count: int = Field(default=1, description="Number of incidents mapped to this operational alert")
    escalation_reason: Optional[str] = Field(default="", description="Rationale explaining alert refresh or escalation")
    parent_alert_id: Optional[str] = Field(default=None, description="Primary active alert ID if linked or deduplicated")
    case_id: Optional[str] = Field(default=None, description="Unique linked operational case identifier")
    case_status: Optional[str] = Field(default="NEW_ALERT", description="Current operational case lifecycle status: NEW_ALERT, PATROL_DISPATCHED, RESOLVED")


class CaseResponse(BaseModel):
    case_id: str
    parent_alert_id: str
    complaint_id: Optional[str] = None
    predicted_atm_id: str
    predicted_zone_id: str
    priority_score: int
    priority_level: str
    intervention_window_start: str
    intervention_window_end: str
    case_status: str
    created_timestamp: str
    updated_timestamp: str
    notes: Optional[str] = ""


class CaseStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Target operational case lifecycle status: PATROL_DISPATCHED or RESOLVED")
    notes: Optional[str] = Field(default="", description="Operational dispatcher remarks or patrol unit logs")


class PlaybookRequest(BaseModel):
    prediction_id: Optional[str] = None
    predicted_atm_id: str
    predicted_zone_id: str
    risk_level: str = "MODERATE"
    priority_level: str = "MEDIUM"
    priority_score: int = 50
    confidence_score: float = 0.10
    predicted_window_start: Optional[str] = ""
    predicted_window_end: Optional[str] = ""
    explanation_codes: List[str] = Field(default_factory=list)
    top_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    reported_amount: Optional[float] = None
    payment_channel: Optional[str] = "UPI"
    mule_bank_code: Optional[str] = None


# ==============================================================================
# 3. ATM & HOTSPOT SCHEMAS
# ==============================================================================
class ATMLocationResponse(BaseModel):
    atm_id: str
    bank_code: str
    latitude: float
    longitude: float
    zone_id: str
    location_type: str
    cash_capacity_level: str
    historical_cashout_count: int
    operating_status: str


class HotspotZone(BaseModel):
    zone_id: str
    atm_count: int
    historical_cashouts: int
    active_risk_level: str
    center_latitude: float
    center_longitude: float


# ==============================================================================
# 4. DASHBOARD STATS & MODEL INFO SCHEMAS
# ==============================================================================
class StatsResponse(BaseModel):
    total_complaints: int
    total_cashouts: int
    active_atms: int
    total_predictions: int
    crime_category_breakdown: Dict[str, int]
    payment_channel_breakdown: Dict[str, int]
    zone_distribution: Dict[str, int]
    recent_risk_breakdown: Dict[str, int]


class ModelInfoResponse(BaseModel):
    model_name: str
    trained_at: str
    evaluation_partition: str
    p3_eval_metrics: Dict[str, Any]
    partition_sizes: Dict[str, int]
    chronological_boundaries: Dict[str, str]


# ==============================================================================
# 5. EMERGING CASH-OUT CLUSTER SCHEMAS (FEATURE 1)
# ==============================================================================
class EmergingCluster(BaseModel):
    cluster_id: str
    cluster_type: str
    zone: str
    primary_atm_id: str
    involved_atm_ids: List[str]
    time_window_start: str
    time_window_end: str
    complaint_count: int
    complaint_case_count: Optional[int] = None
    cash_out_event_count: int
    event_count: Optional[int] = None
    prediction_count: int
    total_amount_involved: float
    severity_level: str
    emergence_score: int
    supporting_complaint_ids: List[str]
    supporting_prediction_ids: List[str]
    center_latitude: float
    center_longitude: float
    recommendation: str
    recommended_action: Optional[str] = None


class ClusterResponse(BaseModel):
    total_clusters: int
    total_clusters_detected: int
    window_hours: int
    rolling_window_hours: int
    window_start: str
    window_end: str
    reference_timestamp: Optional[str] = None
    active_zone_filter: Optional[str] = None
    source_evaluated: str
    clusters: List[EmergingCluster]


# ==============================================================================
# 6. REPEATED ATM / ZONE CONVERGENCE SCHEMAS (FEATURE 2)
# ==============================================================================
class RepeatedConvergence(BaseModel):
    convergence_id: str
    convergence_type: str  # "ATM_CONVERGENCE" or "ZONE_CONVERGENCE"
    target_id: str         # ATM ID or Zone ID
    target_name: str       # Descriptive label
    zone_id: str
    total_matches: int
    prediction_count: int
    case_count: int
    involved_atm_ids: List[str]
    time_window_start: str
    time_window_end: str
    time_span_hours: float
    convergence_score: int
    severity_level: str    # "CRITICAL", "HIGH", "ELEVATED", "MODERATE"
    supporting_prediction_ids: List[str]
    supporting_case_ids: List[str]
    reason: str
    recommended_action: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ConvergenceResponse(BaseModel):
    total_convergences: int
    atm_convergences_count: int
    zone_convergences_count: int
    window_hours: int
    window_start: str
    window_end: str
    target_type: str
    zone_filter: Optional[str] = None
    convergences: List[RepeatedConvergence]

