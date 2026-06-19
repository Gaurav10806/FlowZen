from typing import Any, Dict, List

def sanitize_payload(data: Any, max_depth: int = 15, current_depth: int = 0, visited: set = None) -> Any:
    """
    Helper to sanitize data for JSON serialization.
    Handles recursion, circular references, and deep nesting.
    """
    # 0. Initialize visited set on first call
    if visited is None:
        visited = set()

    # 1. Check Recursion Depth
    if current_depth > max_depth:
        return "[MAX_DEPTH_REACHED]"

    # 2. Check Circular References (for containers only)
    if isinstance(data, (dict, list)):
        obj_id = id(data)
        if obj_id in visited:
            return "[CIRCULAR_REFERENCE]"
        visited.add(obj_id)

    try:
        if isinstance(data, dict):
            return {
                str(k): sanitize_payload(v, max_depth, current_depth + 1, visited)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [
                sanitize_payload(v, max_depth, current_depth + 1, visited)
                for v in data
            ]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        elif hasattr(data, 'isoformat') and callable(data.isoformat):  # datetime
            return data.isoformat()
        elif hasattr(data, 'id'):  # Django models often have id
            return str(data.id)
        else:
            return str(data)
    finally:
        # 3. Clean up visited set (backtracking)
        if isinstance(data, (dict, list)):
            visited.remove(id(data))
