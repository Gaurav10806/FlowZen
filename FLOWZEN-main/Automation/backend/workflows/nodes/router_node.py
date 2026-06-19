"""
Router/Switch Node

This module provides a router/switch node for workflow multi-path routing.
Routes execution to multiple paths based on rule evaluation with first-match strategy.
"""

from typing import Dict, Any, List, Union
import re
import json
from datetime import datetime
from .base_node import UtilityNode, NodeExecutionError
from .registry import register_node


@register_node
class RouterNode(UtilityNode):
    """
    Router/Switch Node - Multi-path routing for workflows.
    
    Routes workflow execution to different paths based on rule evaluation.
    Uses first-match strategy with configurable default path.
    
    Key Features:
    - Multiple rule-based routing paths
    - First-match evaluation strategy
    - Safe operand resolution from input_data
    - Configurable default/fallback path
    - Template variable support
    - Deterministic routing logic
    """
    
    NODE_TYPE = "router"
    DISPLAY_NAME = "Router / Switch"
    DESCRIPTION = "Route workflow execution to multiple paths based on rules"
    CATEGORY = "utilities"
    SUPPORTS_RETRY = True
    DEFAULT_TIMEOUT = 10  # Fast execution
    
    # Supported operators (reuse from conditional node)
    OPERATORS = {
        "equals": "Equal to (==)",
        "not_equals": "Not equal to (!=)",
        "greater_than": "> Greater than",
        "greater_equal": ">= Greater than or equal",
        "less_than": "< Less than", 
        "less_equal": "<= Less than or equal",
        "contains": "Contains substring",
        "not_contains": "Does not contain substring",
        "starts_with": "Starts with",
        "ends_with": "Ends with",
        "exists": "Field exists",
        "not_exists": "Field does not exist",
        "is_empty": "Is empty/null",
        "is_not_empty": "Is not empty/null",
        "regex_match": "Matches regex pattern",
        "in_list": "Value is in list",
        "not_in_list": "Value is not in list"
    }
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate routing rules and determine execution path.
        
        Args:
            input_data: Data from previous nodes
            params: Router configuration
                - rules: List of routing rules with name, left_operand, operator, right_operand
                - default_path: Default path name when no rules match
                - case_sensitive: Whether string comparisons are case sensitive
                - evaluation_strategy: "first_match" (default) or "all_matches"
            context: Execution context
            
        Returns:
            Dict with routing result and selected path information
        """
        self.logger.info("Evaluating router rules")
        
        # Extract parameters
        rules = params.get('rules', [])
        default_path = params.get('default_path', 'default')
        case_sensitive = params.get('case_sensitive', True)
        evaluation_strategy = params.get('evaluation_strategy', 'first_match')
        
        # Validate rules
        if not isinstance(rules, list):
            raise NodeExecutionError("Rules must be a list")
        
        if not rules and not default_path:
            raise NodeExecutionError("Must provide either rules or default_path")
        
        try:
            # Evaluate rules
            matched_paths = []
            rule_results = []
            
            for i, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    self.logger.warning(f"Skipping invalid rule at index {i}: not a dict")
                    continue
                
                rule_name = rule.get('name', f'rule_{i}')
                left_operand = rule.get('left_operand', '')
                operator = rule.get('operator', 'equals')
                right_operand = rule.get('right_operand', '')
                
                # Validate operator
                if operator not in self.OPERATORS:
                    self.logger.warning(f"Skipping rule '{rule_name}': invalid operator '{operator}'")
                    continue
                
                # Resolve operands
                left_value = self._resolve_operand(left_operand, input_data, context)
                right_value = self._resolve_operand(right_operand, input_data, context)
                
                # Evaluate rule condition
                rule_result = self._evaluate_condition(
                    left_value, operator, right_value, case_sensitive
                )
                
                rule_info = {
                    'name': rule_name,
                    'result': rule_result,
                    'left_value': left_value,
                    'operator': operator,
                    'right_value': right_value,
                    'left_operand': left_operand,
                    'right_operand': right_operand
                }
                rule_results.append(rule_info)
                
                self.logger.debug(f"Rule '{rule_name}': {left_value} {operator} {right_value} = {rule_result}")
                
                # If rule matches, add to matched paths
                if rule_result:
                    matched_paths.append(rule_name)
                    
                    # For first-match strategy, stop at first match
                    if evaluation_strategy == 'first_match':
                        break
            
            # Determine selected path
            if matched_paths:
                selected_path = matched_paths[0]  # First match
                self.logger.info(f"Router matched path: {selected_path}")
            else:
                selected_path = default_path
                self.logger.info(f"Router using default path: {selected_path}")
            
            # Return result with routing information
            return {
                **input_data,  # Pass through all input data
                'router_result': {
                    'selected_path': selected_path,
                    'matched_paths': matched_paths,
                    'rule_results': rule_results,
                    'default_path': default_path,
                    'evaluation_strategy': evaluation_strategy,
                    'total_rules': len(rules),
                    'evaluated_at': datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            error_msg = f"Router evaluation failed: {str(e)}"
            self.logger.error(error_msg)
            raise NodeExecutionError(error_msg)
    
    def _resolve_operand(self, operand: Union[str, Any], input_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """
        Resolve an operand to its actual value.
        
        Reuses the same logic as ConditionalNode for consistency.
        
        Args:
            operand: The operand to resolve
            input_data: Input data from previous nodes
            context: Execution context
            
        Returns:
            Resolved value
        """
        if not isinstance(operand, str):
            # Already a literal value (number, boolean, etc.)
            return operand
        
        operand = operand.strip()
        
        # Handle empty operand
        if not operand:
            return ""
        
        # Handle template variables {{variable}}
        if operand.startswith('{{') and operand.endswith('}}'):
            field_path = operand[2:-2].strip()
            return self._get_nested_value(field_path, input_data, context)
        
        # Handle JSON literals
        if operand.startswith(('{', '[', '"')) or operand in ('true', 'false', 'null'):
            try:
                return json.loads(operand)
            except (json.JSONDecodeError, ValueError):
                pass  # Not valid JSON, treat as literal
        
        # Handle numeric literals
        try:
            # Try integer first
            if '.' not in operand and 'e' not in operand.lower():
                return int(operand)
            else:
                return float(operand)
        except ValueError:
            pass  # Not a number
        
        # Handle boolean literals
        if operand.lower() == 'true':
            return True
        elif operand.lower() == 'false':
            return False
        elif operand.lower() == 'null':
            return None
        
        # Try as field path
        field_value = self._get_nested_value(operand, input_data, context)
        if field_value != f"{{{{{operand}}}}}":  # Field was found
            return field_value
        
        # Return as literal string
        return operand
    
    def _evaluate_condition(self, left_value: Any, operator: str, right_value: Any, case_sensitive: bool = True) -> bool:
        """
        Evaluate the condition based on operator.
        
        Reuses the same logic as ConditionalNode for consistency.
        
        Args:
            left_value: Left operand value
            operator: Comparison operator
            right_value: Right operand value
            case_sensitive: Whether string comparisons are case sensitive
            
        Returns:
            Boolean result of the condition
        """
        # Handle existence checks first (don't need right_value)
        if operator == "exists":
            return left_value is not None
        elif operator == "not_exists":
            return left_value is None
        elif operator == "is_empty":
            return self._is_empty(left_value)
        elif operator == "is_not_empty":
            return not self._is_empty(left_value)
        
        # For other operators, handle None values
        if left_value is None or right_value is None:
            if operator in ["equals", "not_equals"]:
                return (left_value == right_value) if operator == "equals" else (left_value != right_value)
            else:
                return False  # Can't compare None with other operators
        
        # Convert to strings for string operations if needed
        if operator in ["contains", "not_contains", "starts_with", "ends_with", "regex_match"]:
            left_str = str(left_value)
            right_str = str(right_value)
            
            if not case_sensitive:
                left_str = left_str.lower()
                right_str = right_str.lower()
            
            if operator == "contains":
                return right_str in left_str
            elif operator == "not_contains":
                return right_str not in left_str
            elif operator == "starts_with":
                return left_str.startswith(right_str)
            elif operator == "ends_with":
                return left_str.endswith(right_str)
            elif operator == "regex_match":
                try:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    return bool(re.search(right_str, left_str, flags))
                except re.error as e:
                    raise NodeExecutionError(f"Invalid regex pattern '{right_str}': {e}")
        
        # List operations
        elif operator in ["in_list", "not_in_list"]:
            if not isinstance(right_value, (list, tuple)):
                # Try to convert string to list
                if isinstance(right_value, str):
                    try:
                        right_value = json.loads(right_value)
                        if not isinstance(right_value, (list, tuple)):
                            right_value = [right_value]
                    except (json.JSONDecodeError, ValueError):
                        # Split by comma as fallback
                        right_value = [item.strip() for item in right_value.split(',')]
                else:
                    right_value = [right_value]
            
            if operator == "in_list":
                return left_value in right_value
            else:  # not_in_list
                return left_value not in right_value
        
        # Numeric/comparison operations
        elif operator in ["greater_than", "greater_equal", "less_than", "less_equal"]:
            try:
                left_num = float(left_value)
                right_num = float(right_value)
                
                if operator == "greater_than":
                    return left_num > right_num
                elif operator == "greater_equal":
                    return left_num >= right_num
                elif operator == "less_than":
                    return left_num < right_num
                elif operator == "less_equal":
                    return left_num <= right_num
                    
            except (ValueError, TypeError):
                # Fallback to string comparison for non-numeric values
                left_str = str(left_value)
                right_str = str(right_value)
                
                if operator == "greater_than":
                    return left_str > right_str
                elif operator == "greater_equal":
                    return left_str >= right_str
                elif operator == "less_than":
                    return left_str < right_str
                elif operator == "less_equal":
                    return left_str <= right_str
        
        # Equality operations (default)
        elif operator == "equals":
            return self._safe_equals(left_value, right_value, case_sensitive)
        elif operator == "not_equals":
            return not self._safe_equals(left_value, right_value, case_sensitive)
        
        else:
            raise NodeExecutionError(f"Unknown operator: {operator}")
        
        return False
    
    def _safe_equals(self, left_value: Any, right_value: Any, case_sensitive: bool = True) -> bool:
        """
        Safe equality comparison handling different types.
        """
        # Direct equality first
        if left_value == right_value:
            return True
        
        # Type conversion attempts
        if isinstance(left_value, str) and isinstance(right_value, str):
            if not case_sensitive:
                return left_value.lower() == right_value.lower()
            return left_value == right_value
        
        # Try numeric conversion
        try:
            return float(left_value) == float(right_value)
        except (ValueError, TypeError):
            pass
        
        # Try string conversion
        try:
            left_str = str(left_value)
            right_str = str(right_value)
            if not case_sensitive:
                return left_str.lower() == right_str.lower()
            return left_str == right_str
        except:
            pass
        
        return False
    
    def _is_empty(self, value: Any) -> bool:
        """
        Check if a value is considered empty.
        """
        if value is None:
            return True
        if isinstance(value, (str, list, dict, tuple)):
            return len(value) == 0
        if isinstance(value, (int, float)):
            return value == 0
        return False
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """
        Return JSON schema for router node parameters.
        """
        return {
            "type": "object",
            "properties": {
                "rules": {
                    "type": "array",
                    "title": "Routing Rules",
                    "description": "List of rules to evaluate for routing decisions",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "title": "Rule Name",
                                "description": "Unique name for this routing path",
                                "examples": ["billing", "support", "sales"]
                            },
                            "left_operand": {
                                "type": "string",
                                "title": "Left Operand",
                                "description": "Left side of comparison (field path, template, or literal)",
                                "examples": ["input.text", "{{user.department}}", "priority"]
                            },
                            "operator": {
                                "type": "string",
                                "enum": list(cls.OPERATORS.keys()),
                                "title": "Operator",
                                "description": "Comparison operator",
                                "default": "contains"
                            },
                            "right_operand": {
                                "type": "string",
                                "title": "Right Operand", 
                                "description": "Right side of comparison (field path, template, or literal)",
                                "examples": ["refund", "billing", "urgent"]
                            }
                        },
                        "required": ["name", "left_operand", "operator"],
                        "additionalProperties": False
                    },
                    "minItems": 1
                },
                "default_path": {
                    "type": "string",
                    "title": "Default Path",
                    "description": "Path to use when no rules match",
                    "default": "default",
                    "examples": ["default", "general", "fallback"]
                },
                "case_sensitive": {
                    "type": "boolean",
                    "title": "Case Sensitive",
                    "description": "Whether string comparisons should be case sensitive",
                    "default": True
                },
                "evaluation_strategy": {
                    "type": "string",
                    "enum": ["first_match", "all_matches"],
                    "title": "Evaluation Strategy",
                    "description": "How to handle multiple matching rules",
                    "default": "first_match"
                }
            },
            "required": ["rules"],
            "additionalProperties": False
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Expected input data schema."""
        return {
            "type": "object",
            "description": "Any data from previous nodes - operands will be resolved from this data",
            "additionalProperties": True
        }
    
    def get_output_schema(self) -> Dict[str, Any]:
        """Output data schema."""
        return {
            "type": "object",
            "properties": {
                "router_result": {
                    "type": "object",
                    "properties": {
                        "selected_path": {"type": "string", "description": "The selected routing path"},
                        "matched_paths": {"type": "array", "items": {"type": "string"}},
                        "rule_results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "result": {"type": "boolean"},
                                    "left_value": {"description": "Resolved left operand value"},
                                    "operator": {"type": "string"},
                                    "right_value": {"description": "Resolved right operand value"}
                                }
                            }
                        },
                        "default_path": {"type": "string"},
                        "evaluation_strategy": {"type": "string"},
                        "total_rules": {"type": "integer"},
                        "evaluated_at": {"type": "string", "format": "date-time"}
                    }
                }
            },
            "additionalProperties": True,
            "description": "All input data plus router_result with routing details"
        }

