"""
Logic Nodes

This module contains nodes that control the flow of execution.
Includes: Conditions, Loops (Sub-workflow), Merge, and Error handling.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from .base_node import LogicNode, NodeExecutionError
from .registry import register_node


# Removed ConditionNode (now in if_else_node.py)

@register_node
class LoopNode(LogicNode):
    """
    Loop Node (Iterator) using Sub-Workflow.
    """
    NODE_TYPE = "loop"
    DISPLAY_NAME = "Loop"
    DESCRIPTION = "Iterate over a list"
    CATEGORY = "logic"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Get List (Key: loop_over)
        items_expr = params.get('loop_over', '')
        
        # Resolve the expr
        items = self._resolve_template(items_expr, input_data, context)
        
        # If it's a JSON string, try to parse it
        if isinstance(items, str):
            try:
                # Basic check for [ or {
                if items.strip().startswith(('[', '{')):
                    items = json.loads(items)
            except:
                pass
        
        # Ensure it's a list
        if not isinstance(items, list):
            self.logger.warning(f"Loop node input is not a list: {type(items)}")
            if items:
                items = [items]
            else:
                items = []
            
        if not items:
            return {
                "output": {
                    "results": [],
                    "iterations": 0,
                    "status": "empty_array"
                }
            }

        # 2. Get Sub-Workflow ID
        sub_workflow_id = params.get('sub_workflow') 
        if not sub_workflow_id:
             raise NodeExecutionError("Sub-Workflow ID is required for Loop node")

        # 3. Setup Internal Execution
        from workflows.models import Workflow
        from workflows.execution.core_engine import WorkflowExecutionEngine, ExecutionContext
        import uuid
        
        try:
             sub_workflow = Workflow.objects.get(id=sub_workflow_id)
        except Workflow.DoesNotExist:
             raise NodeExecutionError(f"Sub-Workflow {sub_workflow_id} not found")

        # 4. Iterate
        results = []
        errors = []
        engine = WorkflowExecutionEngine(hooks=None)
        
        max_iterations = int(params.get('max_iterations', 100))
        break_condition = params.get('break_condition', '')
        
        self.logger.info(f"Looping over {len(items)} items (Max: {max_iterations})")
        
        for index, item in enumerate(items):
            if index >= max_iterations:
                self.logger.info(f"Reached max iterations: {max_iterations}")
                break
            
            # Use expression_evaluator to check break condition if exists
            if break_condition:
                 from ..expression_evaluator import evaluate_expression
                 should_break = evaluate_expression(
                     break_condition,
                     items=[item],
                     context=context
                 )
                 if should_break:
                      self.logger.info(f"Break condition met at index {index}")
                      break

            item_input = item if isinstance(item, dict) else {"json": item}
            
            # Setup sub-context
            sub_ctx = ExecutionContext(
                workflow_id=str(sub_workflow.id),
                execution_id=str(uuid.uuid4()),
                user_id=context.get('user_id'),
                tenant_id=context.get('tenant_id'),
                variables=context.get('variables', {}).copy(),
                debug_mode=context.get('debug_mode', False),
                triggered_by='loop'
            )
            
            try:
                exec_result = engine.run(sub_workflow.graph, item_input, sub_ctx)
                if exec_result.success:
                     results.append(exec_result.final_output)
                else:
                     error = f"Item {index} failed: {exec_result.error_message}"
                     errors.append(error)
                     results.append({"error": error, "status": "failed"})
            except Exception as e:
                errors.append(str(e))
                results.append({"error": str(e), "status": "error"})

        return {
            "output": {
                "results": results,
                "iterations": len(results),
                "errors": errors,
                "success": len(errors) == 0
            }
        }

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {}

@register_node
class MergeNode(LogicNode):
    # Unchanged
    NODE_TYPE = "merge"
    DISPLAY_NAME = "Merge"
    DESCRIPTION = "Merge branches"
    CATEGORY = "logic"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        return {**input_data, "merged_at": datetime.utcnow().isoformat()}
        
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {}

@register_node
class FailNode(LogicNode):
    # Unchanged
    NODE_TYPE = "fail"
    DISPLAY_NAME = "Stop / Fail"
    DESCRIPTION = "Stop execution"
    CATEGORY = "logic"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        message = params.get('message', 'Stopped')
        raise NodeExecutionError(message)
        
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {}

# Removed SwitchNode (now in switch_node.py)


@register_node
class DateNode(LogicNode):
    """
    Date & Time Utility - Format, Calc, Timezone.
    """
    NODE_TYPE = "date_time"
    DISPLAY_NAME = "Date & Time"
    DESCRIPTION = "Format dates, calculate duration, or get current time"
    CATEGORY = "utility"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        operation = params.get('operation', 'current')
        
        import dateutil.parser
        from datetime import timedelta
        import pytz
        
        result = {}
        
        if operation == 'current':
            format_str = params.get('format', '%Y-%m-%d %H:%M:%S')
            tz_str = params.get('timezone', 'UTC')
            tz = pytz.timezone(tz_str)
            now = datetime.now(tz)
            result['date'] = now.strftime(format_str)
            result['iso'] = now.isoformat()
            result['timestamp'] = now.timestamp()
            
        elif operation == 'format':
            input_date = params.get('date')
            resolved_date = self._resolve_template(input_date, input_data, context)
            format_str = params.get('format', '%Y-%m-%d %H:%M:%S')
            try:
                dt = dateutil.parser.parse(str(resolved_date))
                result['formatted'] = dt.strftime(format_str)
            except Exception as e:
                raise NodeExecutionError(f"Invalid date format: {e}")
                
        elif operation == 'add':
            input_date = params.get('date')
            resolved_date = self._resolve_template(input_date, input_data, context)
            value = int(params.get('value', 0))
            unit = params.get('unit', 'hours')
            
            try:
                 dt = dateutil.parser.parse(str(resolved_date))
                 delta = timedelta(**{unit: value})
                 new_dt = dt + delta
                 result['new_date'] = new_dt.isoformat()
            except Exception as e:
                 raise NodeExecutionError(f"Calculation failed: {e}")
                 
        return {**input_data, "date_result": result}

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string", 
                    "enum": ["current", "format", "add"],
                    "default": "current"
                },
                "format": {"type": "string", "title": "Format (e.g. %Y-%m-%d)"},
                "timezone": {"type": "string", "default": "UTC"},
                "date": {"type": "string", "title": "Input Date"},
                "value": {"type": "integer", "title": "Value to Add"},
                "unit": {"type": "string", "enum": ["minutes", "hours", "days", "weeks"]}
            }
        }


@register_node
class CryptoNode(LogicNode):
    """
    Crypto Utility - Hashing and Encoding.
    """
    NODE_TYPE = "crypto"
    DISPLAY_NAME = "Crypto / Hash"
    DESCRIPTION = "Hashing (MD5, SHA) and Encoding (Base64)"
    CATEGORY = "utility"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get('action', 'hash')
        value = params.get('value', '')
        resolved_value = self._resolve_template(value, input_data, context)
        
        import hashlib
        import base64
        import hmac
        
        result = {}
        
        if action == 'hash':
            algo = params.get('algo', 'sha256')
            encoded_val = str(resolved_value).encode('utf-8')
            
            if algo == 'md5':
                h = hashlib.md5(encoded_val)
            elif algo == 'sha1':
                h = hashlib.sha1(encoded_val)
            elif algo == 'sha256':
                h = hashlib.sha256(encoded_val)
            elif algo == 'sha512':
                h = hashlib.sha512(encoded_val)
            else:
                raise NodeExecutionError(f"Unknown algo: {algo}")
                
            result['hash'] = h.hexdigest()
            
        elif action == 'hmac':
            algo = params.get('algo', 'sha256')
            secret = params.get('secret', '')
            # Secret might be template too
            secret = self._resolve_template(secret, input_data, context)
            
            h = hmac.new(
                key=str(secret).encode('utf-8'),
                msg=str(resolved_value).encode('utf-8'),
                digestmod=getattr(hashlib, algo)
            )
            result['hmac'] = h.hexdigest()
            
        elif action == 'base64_encode':
             result['encoded'] = base64.b64encode(str(resolved_value).encode('utf-8')).decode('utf-8')
             
        elif action == 'base64_decode':
             try:
                result['decoded'] = base64.b64decode(str(resolved_value)).decode('utf-8')
             except:
                raise NodeExecutionError("Invalid Base64 string")
                
        return {**input_data, "crypto": result}
        
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
             "type": "object",
             "properties": {
                 "action": {"type": "string", "enum": ["hash", "hmac", "base64_encode", "base64_decode"]},
                 "value": {"type": "string", "title": "Input Value"},
                 "algo": {"type": "string", "enum": ["md5", "sha256", "sha512"], "default": "sha256"},
                 "secret": {"type": "string", "title": "Secret Key (for HMAC)"}
             }
        }
