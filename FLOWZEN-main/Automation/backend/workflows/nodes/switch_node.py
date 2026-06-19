"""
Professional Switch Node with Multi-Path Routing.
"""

import json
from typing import Dict, Any, List
from .base_node import BaseNode, NodeExecutionError
from .registry import register_node
from ..expression_evaluator import evaluate_expression

@register_node
class SwitchNode(BaseNode):
    """
    Switch Node - Match a value against multiple cases.
    Routes to the first matching branch handle.
    """
    NODE_TYPE = "switch"
    DISPLAY_NAME = "Switch"
    DESCRIPTION = "Route execution based on matching a value"
    CATEGORY = "Logic"

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        expr = params.get('switch_expression', '')
        cases = params.get('cases', [])
        
        # Support JSON string or list
        if isinstance(cases, str):
            try:
                cases = json.loads(cases)
            except:
                cases = []
        
        # Resolve the expression value
        items = [input_data] if isinstance(input_data, dict) else input_data
        resolved_value = evaluate_expression(
            expr,
            items=items,
            node_outputs=context.get('node_outputs', {}),
            execution_context=context
        )
        
        self.logger.info(f"Switch evaluating '{expr}' -> value: {resolved_value}")
        
        branch = "default"
        match_found = False
        
        # Check cases
        # Expected cases format: [{"value": "val1", "label": "Label 1"}, ...]
        for case in cases:
            case_val = case.get('value')
            if str(resolved_value) == str(case_val):
                branch = f"case_{case_val}"
                match_found = True
                break
        
        if not match_found:
            self.logger.info("No match found in Switch, using default branch")
        else:
            self.logger.info(f"Switch matched case '{branch}'")

        return {
            "output": input_data,
            "branch": branch,
            "matched": match_found,
            "value": resolved_value
        }

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {}
