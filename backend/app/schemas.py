"""Pydantic input validation for every write endpoint."""
from typing import Literal

from pydantic import BaseModel, EmailStr, Field  # noqa: F401

Role = Literal["CO", "ENGO", "TECH", "LOGO", "BRD", "FSO", "ADMIN", "AUDITOR", "HQ"]
Category = Literal["Engine", "Hydraulics", "Avionics", "Landing gear", "Fuel", "Electrical", "Airframe", "Environmental control"]


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=200)


class OtpIn(BaseModel):
    code: str = Field(min_length=4, max_length=8)


class StatusIn(BaseModel):
    status: Literal["MC", "PMC", "AOG", "MAINT"]
    reason: str = Field(min_length=3, max_length=500)


class ReviewIn(BaseModel):
    decision: Literal["Inspect", "Schedule", "FalseAlarm"]
    note: str = Field(default="", max_length=1000)


class DefectIn(BaseModel):
    tail_no: str
    text: str = Field(min_length=3, max_length=1000)


class ConfirmIn(BaseModel):
    category: Category


class CloseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class CompleteIn(BaseModel):
    hours_spent: float = Field(gt=0, le=500)


class PlanTask(BaseModel):
    tail: str
    start_day: int = Field(ge=0, le=60)


class PlanIn(BaseModel):
    squadron: str | None = None
    tasks: list[PlanTask] | None = None


class WhatIfIn(BaseModel):
    squadron: str | None = None
    service: list[str] = []
    horizon_days: int = Field(default=30, ge=7, le=30)
    sorties_per_day: float | None = Field(default=None, gt=0, le=6)
    expedite: list[str] = []


class UserIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
    name: str = Field(min_length=2, max_length=80)
    role: Role
    squadron_code: str | None = None
    password: str = Field(min_length=6, max_length=200)


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    role: Role | None = None
    squadron_code: str | None = None
    active: bool | None = None
    unlock: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=200)


class AircraftIn(BaseModel):
    tail_no: str = Field(pattern=r"^TAIL-[A-Z0-9]+-\d+$", max_length=20)
    type: str = Field(min_length=2, max_length=40)
    squadron_code: str
    flying_hours: float = Field(default=0, ge=0)


class AircraftPatch(BaseModel):
    type: str | None = Field(default=None, min_length=2, max_length=40)
    flying_hours: float | None = Field(default=None, ge=0)
    archived: bool | None = None
    archived_reason: str | None = Field(default=None, max_length=500)


class BaseIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9]{2,8}$")
    name: str = Field(min_length=2, max_length=80)


class GrievanceIn(BaseModel):
    kind: Literal["Grievance", "Correction"] = "Grievance"
    text: str = Field(min_length=5, max_length=2000)


class RespondIn(BaseModel):
    response: str = Field(min_length=3, max_length=2000)


class BreachIn(BaseModel):
    what_happened: str = Field(min_length=5, max_length=2000)
    impact: str = Field(min_length=3, max_length=2000)
    steps_taken: str = Field(min_length=3, max_length=2000)
    affected_users: list[str] = []


INCIDENT_TYPES = [  # from the CERT-In Directions of 28 April 2022 (Annexure I), shortened
    "Targeted scanning or probing of critical systems", "Compromise of critical systems or information",
    "Unauthorised access to IT systems or data", "Website defacement or intrusion", "Malicious code attack (virus, worm, trojan, spyware)",
    "Ransomware attack", "Attack on servers or network devices", "Identity theft, spoofing or phishing", "Denial of service (DoS / DDoS)",
    "Attack on critical infrastructure, SCADA or operational technology", "Attack on applications such as e-governance",
    "Data breach", "Data leak", "Attack on IoT devices", "Unauthorised access to social media accounts",
    "Attack or suspicious activity affecting cloud systems", "Attack affecting AI / ML systems",
]


class IncidentIn(BaseModel):
    incident_type: str
    description: str = Field(min_length=5, max_length=2000)


class SettingsIn(BaseModel):
    classification: str | None = Field(default=None, min_length=3, max_length=80)
    certin_poc_name: str | None = Field(default=None, max_length=120)
    certin_poc_contact: str | None = Field(default=None, max_length=120)
    ntp_servers: str | None = Field(default=None, max_length=200)
    grievance_contact: str | None = Field(default=None, max_length=120)
