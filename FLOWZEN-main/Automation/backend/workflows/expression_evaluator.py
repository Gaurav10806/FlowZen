"""
n8n-style expression evaluator.
Supports expressions like:
- {{ $json.field }}
- {{ $item(0).json.field }}
- {{ $node("NodeName").json.field }}
- {{ $execution.id }}
- {{ $workflow.id }}
- {{ $now }}
- {{ $today }}
"""
import re
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from django.utils import timezone


class DotDict(dict):
    """Dict that supports dot notation access."""
    def __getattr__(self, name):
        if name in self:
            val = self[name]
            if isinstance(val, dict):
                return DotDict(val)
            if isinstance(val, list):
                return [DotDict(i) if isinstance(i, dict) else i for i in val]
            if isinstance(val, str):
                return JSString(val)
            return val
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    def __getitem__(self, key):
        val = super().get(key)
        if isinstance(val, dict):
            return DotDict(val)
        if isinstance(val, list):
             return [DotDict(i) if isinstance(i, dict) else i for i in val]
        if isinstance(val, str):
            return JSString(val)
        return val

class JSString(str):
    """String that supports some JS-like methods."""
    def includes(self, other):
        return other in self
    
    def toUpperCase(self):
        return self.upper()
    
    def toLowerCase(self):
        return self.lower()
    
    def split(self, sep=None, maxsplit=-1):
        # Override to ensure result items are also JSStrings
        res = super().split(sep, maxsplit)
        return [JSString(s) for s in res]

class ExpressionEvaluator:
    """Evaluates n8n-style expressions."""
    
    def __init__(
        self,
        items: List[Dict] = None,
        node_outputs: Dict[str, List[Dict]] = None,
        execution_context: Dict = None
    ):
        self.items = items or []
        self.execution_context = execution_context or {}
        
        # 1. Use explicit node_outputs if provided
        if node_outputs is not None:
             self.node_outputs = node_outputs
        else:
             # 2. Try to extract from context (Dict or Object)
             if isinstance(self.execution_context, dict):
                  self.node_outputs = self.execution_context.get('node_outputs', {})
             elif hasattr(self.execution_context, 'node_outputs'):
                  self.node_outputs = getattr(self.execution_context, 'node_outputs', {})
             else:
                  self.node_outputs = {}
    
    def evaluate(self, expression: str, item_index: int = 0) -> Any:
        """
        Evaluate an expression string.
        
        Args:
            expression: Expression string like "{{ $json.field }}"
            item_index: Index of current item being processed
        
        Returns:
            Evaluated value
        """
        if not expression:
            return ""
        
        # Find all expression blocks {{ ... }}
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, expression)
        
        if not matches:
            return expression  # No expressions, return as-is
        
        # DEBUG LOGGING for User Issue
        try:
            import logging
            logger = logging.getLogger(__name__)
            keys = list(self.node_outputs.keys())
            logger.critical(f"🔍 EVALUATING: '{expression}'")
            logger.critical(f"🔍 AVAILABLE NODES: {keys}")
        except:
            pass

        result = expression
        for match in matches:
            expr = match.strip()
            value = self._evaluate_expression(expr, item_index)
            
            # Replace in result
            result = result.replace(f"{{{{{match}}}}}", str(value))
        
        # Try to parse as JSON if it looks like JSON
        try:
            return json.loads(result)
        except:
            return result
    
    def _evaluate_expression(self, expr: str, item_index: int) -> Any:
        """Evaluate a single expression."""
        expr = expr.strip()
        
        # $json.field - current item's JSON data
        if expr.startswith("$json."):
            field_path = expr[6:]  # Remove "$json."
            if item_index < len(self.items):
                return self._get_nested_value(self.items[item_index].get("json", {}), field_path)
            return None
        
        # $item(index).json.field - specific item
        item_match = re.match(r'\$item\((\d+)\)\.json\.(.+)', expr)
        if item_match:
            idx = int(item_match.group(1))
            field_path = item_match.group(2)
            if idx < len(self.items):
                return self._get_nested_value(self.items[idx].get("json", {}), field_path)
            return None
        
        # $node("NodeName") OR $node["NodeName"]
        # Support function call () and bracket [] syntax
        node_match = re.match(r'\$node(?:\(\s*|\[\s*)["\']([^"\']+)["\'](?:\)\s*|\]\s*)\.json\.(.+)', expr)
        if node_match:
            node_name = node_match.group(1)
            field_path = node_match.group(2)
            
            # Fuzzy match node name
            target_node = None
            if node_name in self.node_outputs:
                target_node = node_name
            else:
                # Try simple variations
                clean_name = node_name.strip().lower()
                for key in self.node_outputs.keys():
                    if key.strip().lower() == clean_name:
                        target_node = key
                        break
            
            if target_node:
                node_items = self.node_outputs[target_node]
                if node_items:
                    # Robust handling for List vs Dict (User requested Dict storage in Core Engine)
                    first_item = node_items[0] if isinstance(node_items, list) else node_items
                    return self._get_nested_value(first_item.get("json", {}), field_path)
            return None
        
        # $node("NodeName").item(index)... or $node["NodeName"]...
        node_item_match = re.match(r'\$node(?:\(\s*|\[\s*)["\']([^"\']+)["\'](?:\)\s*|\]\s*)\.item\((\d+)\)\.json\.(.+)', expr)
        if node_item_match:
            node_name = node_item_match.group(1)
            item_idx = int(node_item_match.group(2))
            field_path = node_item_match.group(3)
            if node_name in self.node_outputs:
                node_items = self.node_outputs[node_name]
                if item_idx < len(node_items):
                    return self._get_nested_value(node_items[item_idx].get("json", {}), field_path)
            return None
        
        # $node("NodeName").all() or $node["NodeName"].all()
        node_all_match = re.match(r'\$node(?:\(\s*|\[\s*)["\']([^"\']+)["\'](?:\)\s*|\]\s*)\.all\(\)', expr)
        if node_all_match:
            node_name = node_all_match.group(1)
            return self.node_outputs.get(node_name, [])
        
        # $execution.id - execution ID
        if expr == "$execution.id":
            return self.execution_context.get("execution_id", "")
        
        # $workflow.id - workflow ID
        if expr == "$workflow.id":
            return self.execution_context.get("workflow_id", "")
        
        # $now - current timestamp
        if expr == "$now":
            return timezone.now().isoformat()
        
        # $today - today's date
        if expr == "$today":
            return timezone.now().date().isoformat()
        
        # $now.format() - formatted timestamp
        if expr.startswith("$now.format("):
            # Extract format string
            format_match = re.match(r'\$now\.format\("([^"]+)"\)', expr)
            if format_match:
                fmt = format_match.group(1)
                return timezone.now().strftime(fmt)
        
        # $trigger - shortcut for trigger node output
        if expr.startswith("$trigger."):
            trigger_data = self.node_outputs.get("trigger", {}) 
            path = expr[9:] # Remove "$trigger."
            return self._get_nested_value(trigger_data, path)

        # Math functions
        if expr.startswith("$math."):
            import math
            # $math.round(value)
            round_match = re.match(r'\$math\.round\((.+)\)', expr)
            if round_match:
                val = self._evaluate_expression(round_match.group(1).strip(), item_index)
                return round(float(val))
            
            # $math.floor(value)
            floor_match = re.match(r'\$math\.floor\((.+)\)', expr)
            if floor_match:
                val = self._evaluate_expression(floor_match.group(1).strip(), item_index)
                return math.floor(float(val))
            
            # $math.ceil(value)
            ceil_match = re.match(r'\$math\.ceil\((.+)\)', expr)
            if ceil_match:
                val = self._evaluate_expression(ceil_match.group(1).strip(), item_index)
                return math.ceil(float(val))
        
        # String functions
        if expr.startswith("$str."):
            # $str.toUpper(value)
            upper_match = re.match(r'\$str\.toUpper\((.+)\)', expr)
            if upper_match:
                val = self._evaluate_expression(upper_match.group(1).strip(), item_index)
                return str(val).upper()
            
            # $str.toLower(value)
            lower_match = re.match(r'\$str\.toLower\((.+)\)', expr)
            if lower_match:
                val = self._evaluate_expression(lower_match.group(1).strip(), item_index)
                return str(val).lower()
            
            # $str.length(value)
            length_match = re.match(r'\$str\.length\((.+)\)', expr)
            if length_match:
                val = self._evaluate_expression(length_match.group(1).strip(), item_index)
                return len(str(val))
        
        # Array functions
        if expr.startswith("$array."):
            # $array.length(array)
            array_length_match = re.match(r'\$array\.length\((.+)\)', expr)
            if array_length_match:
                arr = self._evaluate_expression(array_length_match.group(1).strip(), item_index)
                if isinstance(arr, list):
                    return len(arr)
                return 0
            
            # $array.first(array)
            array_first_match = re.match(r'\$array\.first\((.+)\)', expr)
            if array_first_match:
                arr = self._evaluate_expression(array_first_match.group(1).strip(), item_index)
                if isinstance(arr, list) and arr:
                    return arr[0]
                return None
            
            # $array.last(array)
            array_last_match = re.match(r'\$array\.last\((.+)\)', expr)
            if array_last_match:
                arr = self._evaluate_expression(array_last_match.group(1).strip(), item_index)
                if isinstance(arr, list) and arr:
                    return arr[-1]
                return None
        
        # $input.all() - all input items
        if expr == "$input.all()":
            return self.items
        
        # $input.item() - current item
        if expr == "$input.item()":
            return self.items[item_index] if item_index < len(self.items) else {}
        
        # $input.item(index) - specific item
        input_item_match = re.match(r'\$input\.item\((\d+)\)', expr)
        if input_item_match:
            idx = int(input_item_match.group(1))
            return self.items[idx] if idx < len(self.items) else {}
        
        # Proxy objects for n8n compatibility
        # We inject them into safe_dict so {{ $trigger... }} and {{ $node("Node")... }} work
        
        # Fallback: try to evaluate as Python expression (with restrictions)
        try:
            # Wrap node outputs in DotDict for dot notation support
            context_nodes = {k: DotDict(v) if isinstance(v, dict) else v for k, v in self.node_outputs.items()}
            
            safe_dict = {
                "json": DotDict(self.items[item_index].get("json", {})) if item_index < len(self.items) else DotDict(),
                "items": self.items,
                "node": context_nodes,
                "$node": context_nodes, # Alias for $node
                "execution": DotDict(self.execution_context),
                "$execution": DotDict(self.execution_context),
                "trigger": context_nodes.get("trigger", DotDict()),
                "$trigger": context_nodes.get("trigger", DotDict()),
            }
            
            # Additional node aliases
            for nid, data in context_nodes.items():
                if nid not in safe_dict:
                    safe_dict[nid] = data
            
            # Simple expression evaluation
            # Use a slightly more robust eval environment
            result = eval(expr, {"__builtins__": {}}, safe_dict)
            
            # If the result is a proxy, convert back to string for the replace() if it was part of a larger string
            return result
        except Exception as e:
            # logger.debug(f"Eval failed for {expr}: {e}")
            return expr  # Return as-is if can't evaluate
    
    def _get_nested_value(self, obj: Dict, path: str) -> Any:
        """Get nested value from dict using dot notation."""
        keys = path.split(".")
        value = obj
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list):
                try:
                    idx = int(key)
                    value = value[idx] if idx < len(value) else None
                except:
                    return None
            else:
                return None
            if value is None:
                return None
        return value


def evaluate_expression(
    expression: str,
    items: List[Dict] = None,
    item_index: int = 0,
    node_outputs: Dict[str, List[Dict]] = None,
    execution_context: Dict = None
) -> Any:
    """Convenience function to evaluate an expression."""
    evaluator = ExpressionEvaluator(
        items=items or [],
        node_outputs=node_outputs or {},
        execution_context=execution_context or {}
    )
    return evaluator.evaluate(expression, item_index)

