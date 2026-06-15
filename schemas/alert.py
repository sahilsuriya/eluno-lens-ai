from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from models.alert import AlertChannel, AlertType


class AlertOut(BaseModel):
    id:         int
    order_id:   Optional[int]
    alert_type: AlertType
    channel:    AlertChannel
    message:    str
    sent:       bool
    read:       bool
    created_at: datetime
    sent_at:    Optional[datetime]

    model_config = {"from_attributes": True}


class AlertMarkRead(BaseModel):
    ids: list[int]


class TATprediction(BaseModel):
    order_id:       int
    lens_type:      str
    current_stage:  str
    elapsed_days:   int
    sla_days:       int
    predicted_tat:  int
    breach_prob:    float
    risk_level:     str
    ai_reasoning:   str