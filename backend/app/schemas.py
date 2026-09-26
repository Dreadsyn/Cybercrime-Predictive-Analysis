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
from pydantic import BaseModel, Field


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
