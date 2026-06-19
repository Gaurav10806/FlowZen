from typing import Dict, Any, List, Optional
from jinja2 import Template, Environment, BaseLoader
from workflows.expression_evaluator import ExpressionEvaluator

class ActionContext:
    """Context passed to actions containing execution state."""
    
    def __init__(
        self,
        execution_id: str,
        node_outputs: Dict[str, List[Dict]] = None,
        items: List[Dict] = None,
        item_index: int = 0,
        execution_context: Dict = None,
        execution=None,
        node_execution=None,
        inputs: Dict[str, List[Dict]] = None,
    ):
        self.execution_id = execution_id
        self.node_outputs = node_outputs or {}
        self.items = items or []
        self.inputs = inputs or {}  # Map port ID -> items
        self.item_index = item_index
        self.execution_context = execution_context or {}
        self.execution = execution
        self.node_execution = node_execution
        self.evaluator = ExpressionEvaluator(
            items=self.items,
            node_outputs=self.node_outputs,
            execution_context=self.execution_context
        )
    
    def get_node_output(self, node_id: str) -> Optional[List[Dict]]:
        """Get output items from a previous node."""
        return self.node_outputs.get(node_id, [])
    
    def evaluate(self, expression: str) -> Any:
        """Evaluate an expression in current context."""
        return self.evaluator.evaluate(expression, self.item_index)


def render_template(template_str: str, context: Dict[str, Any]) -> str:
    """Render Jinja2 template with context."""
    if not template_str:
        return ""
    
    env = Environment(loader=BaseLoader())
    template = env.from_string(template_str)
    return template.render(**context)
