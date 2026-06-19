
import logging
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """
    Phase 13: Multi-Agent Orchestration.
    Breaks complex tasks into sub-tasks and executes them.
    """
    
    def __init__(self, engine_class, context: Dict):
        self.engine = engine_class # UniversalAIEngine class reference
        self.context = context
        
    def run_parallel(self, task: str, agents_config: Dict, credential_id: str):
        """
        Planner -> [Worker1, Worker2...] -> Aggregator
        """
        logger.info(f"🤖 Orchestrator started for task: {task[:50]}...")
        
        # 1. PLANNER: Break down task
        plan = self._create_plan(task, credential_id)
        if not plan:
             return {"text": "Agent failed to create a plan.", "json": {}, "meta": {"agent_status": "plan_failed"}}
             
        # 2. WORKERS: Execute steps
        results = []
        # TODO: Real parallel execution using ThreadPool (for now sequential loop for safety)
        for step in plan:
             res = self._execute_step(step, credential_id)
             results.append(f"Step '{step['title']}': {res['output']['text']}")
             
        # 3. AGGREGATOR: Summarize
        final_response = self._aggregate_results(task, results, credential_id)
        
        return final_response

    def _create_plan(self, task: str, cred_id: str) -> List[Dict]:
        """Uses AI to generate a JSON plan."""
        sys_prompt = (
            "You are a Senior Project Manager. "
            "Break the user's request into 2-4 distinct, actionable sub-tasks. "
            "Return JSON ONLY: [{'title': '...', 'instruction': '...'}]"
        )
        try:
             res = self.engine.run(
                 user_prompt=task,
                 system_prompt=sys_prompt,
                 response_mode="json",
                 credential_id=cred_id,
                 context=self.context
             )
             raw = res['output']['json']
             # Handle list being wrapped or direct
             if isinstance(raw, list): return raw
             if isinstance(raw, dict) and 'tasks' in raw: return raw['tasks']
             return []
        except Exception as e:
             logger.error(f"Planning failed: {e}")
             return []

    def _execute_step(self, step: Dict, cred_id: str):
        """Executes a single step."""
        return self.engine.run(
            user_prompt=step.get('instruction', ''),
            system_prompt="You are a Task Executor. Complete this step rigorously.",
            response_mode="text",
            credential_id=cred_id,
            context=self.context
        )

    def _aggregate_results(self, original_task: str, results: List[str], cred_id: str):
        """Synthesizes final answer."""
        combined = "\n\n".join(results)
        prompt = f"Original Task: {original_task}\n\nSub-task Results:\n{combined}\n\nSynthesize a final comprehensive answer."
        return self.engine.run(
            user_prompt=prompt,
            system_prompt="You are a Finalizer Agent. Combine the results into a coherent response.",
            response_mode="text",
            credential_id=cred_id,
            context=self.context
        )
