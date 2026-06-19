"""
Professional If / Else Node with True/False Branching.
"""

from typing import Dict, Any
from .base_node import BaseNode, NodeExecutionError
from .registry import register_node
from ..expression_evaluator import evaluate_expression

@register_node
class IfElseNode(BaseNode):
    """
    If / Else Node - Routes execution to one of two branches.
    Exactly like n8n's IF node.
    """
    NODE_TYPE = "if_else"
    DISPLAY_NAME = "If / Else"
    DESCRIPTION = "Branch workflow execution into True/False paths"
    CATEGORY = "Logic"
    SUPPORTS_RETRY = False

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        condition = params.get('condition_expression', '')
        comparison_type = params.get('comparison_type', 'Expression')
        
        # Resolve data
        items = [input_data] if isinstance(input_data, dict) else input_data
        
        # evaluation logic
        try:
            # We use the standardized expression evaluator
            result = evaluate_expression(
                condition,
                items=items,
                node_outputs=context.get('node_outputs', {}),
                execution_context=context
            )
            
            # Truthiness check
            is_true = False
            if isinstance(result, bool):
                is_true = result
            elif isinstance(result, (int, float)):
                is_true = bool(result)
            elif isinstance(result, str):
                is_true = result.lower() in ('true', '1', 'yes', 'on')
            else:
                is_true = bool(result)
                
            branch = "true" if is_true else "false"
            
            self.logger.info(f"If/Else evaluated to {is_true} -> branch: {branch}")
            
            return {
                "output": input_data,
                "branch": branch,
                "condition_result": is_true
            }
        except Exception as e:
            raise NodeExecutionError(f"Expression evaluation failed: {str(e)}")

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """Schema is defined in node_schemas.py and returned via API."""
        return {}
