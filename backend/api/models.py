"""Pydantic models for API request/response"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class QueryRequest(BaseModel):
    query: str


class PassengerDetails(BaseModel):
    first_name: str
    last_name: str
    age: int
    gender: str  # "male" | "female" | "other"
    email: Optional[str] = None
    phone: Optional[str] = None


class FlightResult(BaseModel):
    airline: str
    flight_number: Optional[str] = None
    departure_time: str
    arrival_time: str
    duration: Optional[str] = None
    price: str
    stops: Optional[str] = None
    index: int


class WorkflowStage(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    OPENING_BROWSER = "opening_browser"
    NAVIGATING = "navigating"
    SEARCHING = "searching"
    EXTRACTING = "extracting"
    AWAITING_SELECTION = "awaiting_selection"
    FILLING_FORM = "filling_form"
    STOPPED_BEFORE_PAYMENT = "stopped_before_payment"
    ERROR = "error"
    COMPLETED = "completed"


class WorkflowStatus(BaseModel):
    workflow_id: str
    stage: WorkflowStage
    logs: List[dict]
    flights: List[FlightResult]
    screenshot_available: bool
    error: Optional[str] = None


class LogEntry(BaseModel):
    timestamp: str
    agent: str
    level: str  # "info" | "warning" | "error" | "success"
    message: str
    details: Optional[dict] = None
