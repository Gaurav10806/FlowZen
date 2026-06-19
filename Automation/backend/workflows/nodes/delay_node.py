"""
Professional Delay Node with Real Time-Wait logic.
"""

import time
from datetime import datetime
import dateutil.parser
from typing import Dict, Any
from .base_node import BaseNode, NodeExecutionError
from .registry import register_node

@register_node
class DelayNode(BaseNode):
    """
    Delay Node - Pauses execution for a specified duration.
    """
    NODE_TYPE = "delay"
    DISPLAY_NAME = "Delay"
    DESCRIPTION = "Pause workflow execution"
    CATEGORY = "Logic"

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        seconds = int(params.get('delay_seconds', 0))
        minutes = int(params.get('delay_minutes', 0))
        until_dt_str = params.get('delay_until_datetime', '')
        
        total_wait = seconds + (minutes * 60)
        
        # Calculate wait until specific time
        if until_dt_str:
            try:
                until_dt = dateutil.parser.parse(until_dt_str)
                now = datetime.now(until_dt.tzinfo if until_dt.tzinfo else None)
                remaining = (until_dt - now).total_seconds()
                if remaining > 0:
                    total_wait = max(total_wait, remaining)
                self.logger.info(f"Delay until {until_dt_str} resolved to {remaining}s remaining")
            except Exception as e:
                self.logger.warning(f"Could not parse delay_until_datetime: {e}")
        
        # Guard against insane delays (engine limit should be handled by timeout)
        if total_wait > 3600: # 1 hour max for this simple node
             self.logger.warning(f"Delay {total_wait}s exceeds safety cap of 3600s. Capping.")
             total_wait = 3600
        
        if total_wait > 0:
            self.logger.info(f"Sleeping for {total_wait} seconds...")
            time.sleep(total_wait)
            
        return {
            "output": input_data,
            "waited_seconds": total_wait,
            "status": "resumed"
        }

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {}
