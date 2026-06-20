from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class ToolInputSpec(BaseModel):
    type: str
    source: Optional[str] = None  # e.g., "session"
    ask: Optional[str] = None     # question prompt if missing

class ToolSpec(BaseModel):
    name: str = ""                # dynamically populated from yaml keys
    description: str
    method: str
    url: str
    inputs: Dict[str, ToolInputSpec]
    returns: str
    mutating: bool = False
    bodyTemplate: Optional[str] = None

class WorkflowSpec(BaseModel):
    goal: str
    steps: List[str]
    requiredDocuments: Optional[List[str]] = None

class ModuleSpec(BaseModel):
    tools: Dict[str, ToolSpec]
    workflow: WorkflowSpec
