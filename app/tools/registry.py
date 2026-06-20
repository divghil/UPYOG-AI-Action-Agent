import os
import yaml
import logging
from typing import Dict, Any, List, Optional, Tuple
from app.tools.base import ModuleSpec, ToolSpec, WorkflowSpec

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self, specs_dir: str):
        self.specs_dir = specs_dir
        self.modules: Dict[str, ModuleSpec] = {}
        self.load_specs()

    def load_specs(self) -> None:
        logger.info(f"Loading tool specifications from: {self.specs_dir}")
        if not os.path.exists(self.specs_dir):
            logger.warning(f"Specs directory does not exist: {self.specs_dir}")
            return
            
        for file in os.listdir(self.specs_dir):
            if file.endswith(".yaml") or file.endswith(".yml"):
                module_name = os.path.splitext(file)[0]
                file_path = os.path.join(self.specs_dir, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    module_spec = ModuleSpec.model_validate(data)
                    # Dynamically set name attribute in each ToolSpec
                    for tool_name, tool_spec in module_spec.tools.items():
                        tool_spec.name = tool_name
                    self.modules[module_name] = module_spec
                    logger.info(f"Loaded module spec: '{module_name}' with {len(module_spec.tools)} tools")
                except Exception as e:
                    logger.error(f"Failed to parse spec file {file}: {e}")

    def get_tool_spec(self, tool_name: str) -> Tuple[Optional[ToolSpec], Optional[str]]:
        """Find and return the tool specification and corresponding module name."""
        for module_name, module_spec in self.modules.items():
            if tool_name in module_spec.tools:
                return module_spec.tools[tool_name], module_name
        return None, None

    def get_workflow_spec(self, module_name: str) -> Optional[WorkflowSpec]:
        """Get the workflow goal and step list for a module."""
        module_spec = self.modules.get(module_name)
        return module_spec.workflow if module_spec else None

    def get_all_tool_schemas_for_llm(self) -> List[Dict[str, Any]]:
        """Convert YAML tools specifications into Groq/OpenAI tool call schemas."""
        schemas = []
        for module_name, module_spec in self.modules.items():
            for tool_name, tool_spec in module_spec.tools.items():
                properties = {}
                required = []
                
                for param_name, input_spec in tool_spec.inputs.items():
                    # Exclude inputs sourced from session context to prevent LLM hallucinations
                    if input_spec.source == "session":
                        continue
                    
                    schema_type = "string"
                    if input_spec.type in ("integer", "number"):
                        schema_type = "number"
                    elif input_spec.type == "boolean":
                        schema_type = "boolean"
                        
                    properties[param_name] = {
                        "type": schema_type,
                        "description": input_spec.ask or f"The {param_name} parameter."
                    }
                    required.append(param_name)
                    
                schema = {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool_spec.description,
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required
                        }
                    }
                }
                schemas.append(schema)
        return schemas
