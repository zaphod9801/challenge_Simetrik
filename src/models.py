from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class IncidentSeverity(str, Enum):
    URGENT = "URGENT"
    ATTENTION_REQUIRED = "ATTENTION_REQUIRED"
    ALL_GOOD = "ALL_GOOD"

class IncidentType(str, Enum):
    MISSING_FILE = "Missing File"
    DUPLICATED_FILE = "Duplicated File"
    UNEXPECTED_EMPTY = "Unexpected Empty File"
    VOLUME_VARIATION = "Unexpected Volume Variation"
    LATE_UPLOAD = "File Upload After Schedule"
    PREVIOUS_FILE = "Upload of Previous File"
    FAILED_FILE = "Failed File"

class FileData(BaseModel):
    filename: str
    rows: int
    status: str
    is_duplicated: bool
    file_size: Optional[float] = None
    uploaded_at: datetime
    status_message: Optional[str] = None

class SourceCV(BaseModel):
    resource_id: str
    workspace_id: str
    filename_pattern: str
    upload_schedule: Dict[str, str]  # Day -> Time (e.g., "Mon": "15:00")
    volume_stats: Dict[str, Dict[str, float]] # Day -> {mean, std, min, max}
    
    # We might need more specific patterns, but let's start with these generic ones
    # derived from the markdown parsing

class Incident(BaseModel):
    incident_type: IncidentType
    severity: IncidentSeverity
    description: str
    file_name: Optional[str] = None
    source_id: str

class SourceReport(BaseModel):
    source_id: str
    incidents: List[Incident] = []
    status: IncidentSeverity = IncidentSeverity.ALL_GOOD
    recommendations: List[str] = []

class GlobalReport(BaseModel):
    date: str
    source_reports: List[SourceReport]
