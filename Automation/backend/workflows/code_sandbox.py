"""
Safe code execution sandbox for code nodes using RestrictedPython.
"""
import sys
import io
import contextlib
from typing import Dict, Any, List
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.transformer import RestrictingNodeTransformer
from RestrictedPython import PrintCollector
from RestrictedPython.Eval import default_guarded_getitem
import logging

logger = logging.getLogger(__name__)


def execute_code_safely(code: str, items: List[Dict], execution_context: Dict[str, Any] = None) -> List[Dict]:
    """
    Execute Python code in a restricted sandbox for code nodes.
    
    Args:
        code: Python code to execute (should process items and return results)
        items: Input items list: [{"json": {...}, "binary": {...}}, ...]
        execution_context: Execution context variables
    
    Returns:
        Output items list: [{"json": {...}, "binary": {...}}, ...]
    """
    # Prepare restricted globals
    restricted_globals = safe_globals.copy()
    restricted_globals['_getattr_'] = lambda obj, name: getattr(obj, name)
    restricted_globals['_getiter_'] = lambda obj: iter(obj)
    restricted_globals['_print_'] = PrintCollector
    restricted_globals['_write_'] = lambda x: x
    restricted_globals['_getitem_'] = default_guarded_getitem
    
    # Add safe imports
    restricted_globals['json'] = __import__('json')
    restricted_globals['math'] = __import__('math')
    restricted_globals['datetime'] = __import__('datetime')
    restricted_globals['re'] = __import__('re')
    restricted_globals['random'] = __import__('random')
    restricted_globals['uuid'] = __import__('uuid')
    # Add safe builtins
    restricted_globals['sum'] = sum
    restricted_globals['len'] = len
    restricted_globals['min'] = min
    restricted_globals['max'] = max
    restricted_globals['abs'] = abs
    restricted_globals['zip'] = zip
    restricted_globals['enumerate'] = enumerate
    restricted_globals['dict'] = dict
    restricted_globals['list'] = list
    restricted_globals['str'] = str
    restricted_globals['int'] = int
    restricted_globals['float'] = float
    restricted_globals['bool'] = bool
    
    # Add items and context
    restricted_globals['items'] = items
    restricted_globals['context'] = execution_context or {}
    
    # Compile code with restrictions
    try:
        # Wrap code in a function to allow 'return'
        indented_code = "\n".join(f"    {line}" for line in code.split('\n'))
        # We pass both items and context to the wrapper
        wrapper_code = f"def user_function(input_data, context):\n{indented_code}\n\nresult = user_function(items, context)"
        
        byte_code = compile_restricted(wrapper_code, filename='<code_node>', mode='exec')
    except Exception as e:
        error_msg = f"Code compilation failed: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Execute in restricted environment
    # Note: result will be set in restricted_globals because it's at the top level of the wrapper script
    try:
        exec(byte_code, restricted_globals)
    except Exception as e:
        error_msg = f"Code execution failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg)
    
    # Extract result
    result = restricted_globals.get('result')
    
    # Ensure result is a list of items
    if not isinstance(result, list):
        if isinstance(result, dict):
            # Single item
            result = [result]
        else:
            # Wrap in item format
            result = [{"json": {"output": result}, "binary": {}}]
    
    # Ensure all items have correct format
    output_items = []
    for item in result:
        if isinstance(item, dict):
            if "json" not in item:
                item = {"json": item, "binary": {}}
            output_items.append(item)
        else:
            output_items.append({"json": {"output": item}, "binary": {}})
    
    return output_items


def test_code_syntax(code: str) -> tuple[bool, str]:
    """
    Test if code syntax is valid without executing.
    
    Returns:
        (is_valid, error_message)
    """
    try:
        byte_code = compile_restricted(code, filename='<test>', mode='exec')
        if byte_code.errors:
            return False, ', '.join(byte_code.errors)
        return True, ""
    except Exception as e:
        return False, str(e)

