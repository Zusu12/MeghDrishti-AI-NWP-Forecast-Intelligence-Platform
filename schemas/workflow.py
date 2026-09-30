"""
schemas/workflow.py — Operational Blending Workflow & Execution Status Schemas
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class WorkflowStepResult(BaseModel):
    step_name: str
    status: str  # SUCCESS | WARNING | FAILED | SKIPPED
    duration_ms: int
    details: Optional[str] = None


class OperationalWorkflowStatus(BaseModel):
    """Execution state of the automated multi-model forecast blending pipeline."""
    workflow_id: str
    last_run_time: str
    status: str  # COMPLETED | RUNNING | FAILED | IDLE
    execution_type: str  # SCHEDULED | MANUAL_TRIGGER
    active_providers: List[str]
    provider_health: Dict[str, str]  # e.g., {"GFS": "HEALTHY", "WRF": "HEALTHY", "ECMWF": "OFFLINE"}
    steps: List[WorkflowStepResult]
    total_duration_ms: int
    blended_timesteps_generated: int
    next_scheduled_run: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
