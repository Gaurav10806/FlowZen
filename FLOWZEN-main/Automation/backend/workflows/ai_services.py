"""
AI service integrations for workflow generation, code generation, and optimization.
"""
import json
import logging
import os
from typing import Dict, List, Any, Optional
from celery import shared_task
from django.conf import settings
from .models import (
    AIWorkflowGeneration, AICodeGeneration, AIWorkflowOptimization,
    Workflow, Node, WorkflowExecution, NodeExecution
)

logger = logging.getLogger(__name__)

# AI Service Configuration
AI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
AI_MODEL = os.environ.get('AI_MODEL', 'gpt-4')
AI_BASE_URL = os.environ.get('AI_BASE_URL', 'https://api.openai.com/v1')


class OpenAIService:
    def __init__(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        self.base_url = (base_url or AI_BASE_URL).rstrip('/')

    def chat(self, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1000, tools: list = None, response_format: dict = None) -> dict:
        """
        Execute Chat Completion with Tool Support.
        Returns: { "message": dict, "tool_call": dict | None }
        """
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if response_format:
            payload["response_format"] = response_format

        # Normalize tools: If dict (name->func), convert to OpenAI schema.
        # If list (OpenAI schema), pass as is.
        openai_tools = []
        if tools:
            if isinstance(tools, dict):
                 for name, tool_info in tools.items():
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": tool_info.get("description", ""),
                            "parameters": tool_info.get("parameters", {
                                "type": "object",
                                "properties": {
                                    "input": {"type": "string", "description": "Input payload for the tool"}
                                },
                                "required": ["input"]
                            })
                        }
                    })
            elif isinstance(tools, list):
                openai_tools = tools
            
            if openai_tools:
                payload["tools"] = openai_tools
                payload["tool_choice"] = "auto"

        try:
            response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=60)
            if response.status_code != 200:
                logger.error(f"OpenAI API Error: {response.text}")
                response.raise_for_status()
                
            data = response.json()
            
            message = data["choices"][0]["message"]
            
            # Normalize tool call
            tool_call_data = None
            if message.get("tool_calls"):
                first_call = message["tool_calls"][0]
                try:
                    args = json.loads(first_call["function"]["arguments"])
                except:
                    args = {}
                    
                tool_call_data = {
                    "name": first_call["function"]["name"],
                    "arguments": args,
                    "id": first_call["id"]
                }
            
            return {
                "message": message,
                "tool_call": tool_call_data
            }

        except Exception as e:
            logger.error(f"OpenAI Chat Error: {e}", exc_info=True)
            raise


def call_ai_api(prompt: str, system_prompt: str = None, max_tokens: int = 2000) -> Dict[str, Any]:
    """
    Call AI API (OpenAI-compatible).
    In production, you might use OpenAI, Anthropic, or self-hosted models.
    """
    try:
        import requests
        
        headers = {
            'Authorization': f'Bearer {AI_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        
        payload = {
            'model': AI_MODEL,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': 0.7
        }
        
        response = requests.post(
            f'{AI_BASE_URL}/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        return {
            'content': result['choices'][0]['message']['content'],
            'tokens_used': result.get('usage', {}).get('total_tokens', 0),
            'model': result.get('model', AI_MODEL)
        }
    except Exception as e:
        logger.error(f"AI API call failed: {e}", exc_info=True)
        raise


@shared_task
def generate_workflow_from_prompt(generation_id: str):
    """
    Generate workflow JSON from natural language prompt.
    """
    try:
        generation = AIWorkflowGeneration.objects.get(id=generation_id)
        generation.status = 'processing'
        generation.save()
        
        system_prompt = """You are a workflow automation expert. Generate n8n-style workflow JSON from user descriptions.
        
        Workflow JSON format:
        {
            "nodes": [
                {
                    "id": "uuid",
                    "label": "Node Name",
                    "action_type": "webhook|http_request|code|condition|delay|email",
                    "config": {...},
                    "position": {"x": 0, "y": 0}
                }
            ],
            "edges": [
                {
                    "source": "node_id_1",
                    "target": "node_id_2"
                }
            ]
        }
        
        Return ONLY valid JSON, no markdown, no explanations."""
        
        prompt = f"Generate a workflow for: {generation.user_prompt}"
        
        result = call_ai_api(prompt, system_prompt, max_tokens=4000)
        
        # Parse JSON response
        try:
            workflow_json = json.loads(result['content'])
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            content = result['content']
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            workflow_json = json.loads(content.strip())
        
        # Validate workflow structure
        if 'nodes' not in workflow_json or 'edges' not in workflow_json:
            raise ValueError("Invalid workflow structure")
        
        # Create workflow
        workflow = Workflow.objects.create(
            name=f"AI Generated: {generation.user_prompt[:50]}",
            description=generation.user_prompt,
            graph=workflow_json,
            owner=generation.user,
            organization=generation.organization,
            status='draft'
        )
        
        # Update generation
        generation.status = 'completed'
        generation.generated_workflow_json = workflow_json
        generation.workflow = workflow
        generation.tokens_used = result['tokens_used']
        generation.model_used = result['model']
        generation.save()
        
        logger.info(f"Workflow generated: {workflow.id}")
        
    except Exception as e:
        logger.error(f"Workflow generation failed: {e}", exc_info=True)
        generation.status = 'failed'
        generation.error_message = str(e)
        generation.save()


@shared_task
def generate_code_from_prompt(generation_id: str):
    """
    Generate Python code from natural language prompt.
    """
    try:
        generation = AICodeGeneration.objects.get(id=generation_id)
        generation.status = 'processing'
        generation.save()
        
        context_str = json.dumps(generation.context_data, indent=2)
        
        system_prompt = """You are a Python code generator for workflow automation.
        Generate safe, executable Python code that processes workflow items.
        
        Code should:
        - Process items (list of dicts with 'json' and 'binary' keys)
        - Return list of items
        - Be safe (no file system access, no network calls, no dangerous operations)
        - Handle errors gracefully
        
        Example:
        def process(items):
            results = []
            for item in items:
                data = item.get('json', {})
                # Process data
                results.append({'json': processed_data})
            return results"""
        
        prompt = f"""Generate Python code to: {generation.user_prompt}

        Context data:
        {context_str}

        Return ONLY the Python function code, no explanations, no markdown."""
        
        result = call_ai_api(prompt, system_prompt, max_tokens=2000)
        
        # Extract code
        code = result['content'].strip()
        if '```python' in code:
            code = code.split('```python')[1].split('```')[0]
        elif '```' in code:
            code = code.split('```')[1].split('```')[0]
        
        # Test code in sandbox
        try:
            test_result = execute_code_safely(code, generation.context_data)
            generation.execution_result = test_result
        except Exception as e:
            logger.warning(f"Code execution test failed: {e}")
        
        # Update generation
        generation.status = 'completed'
        generation.generated_code = code
        generation.tokens_used = result['tokens_used']
        generation.save()
        
    except Exception as e:
        logger.error(f"Code generation failed: {e}", exc_info=True)
        generation.status = 'failed'
        generation.error_message = str(e)
        generation.save()


def execute_code_safely(code: str, context_data: Dict) -> Dict[str, Any]:
    """
    Execute code in a safe sandbox environment.
    """
    # Restricted globals
    safe_builtins = {
        'abs', 'all', 'any', 'bool', 'dict', 'float', 'int', 'len',
        'list', 'max', 'min', 'range', 'round', 'str', 'sum', 'tuple',
        'zip', 'enumerate', 'sorted', 'reversed'
    }
    
    restricted_globals = {
        '__builtins__': {k: __builtins__[k] for k in safe_builtins if k in __builtins__},
        'json': __import__('json'),
        'math': __import__('math'),
        'datetime': __import__('datetime'),
        're': __import__('re'),
    }
    
    try:
        # Compile and execute
        compiled = compile(code, '<string>', 'exec')
        exec(compiled, restricted_globals)
        
        # Get process function
        if 'process' in restricted_globals:
            process_func = restricted_globals['process']
            # Test with sample data
            test_items = [{'json': context_data}]
            result = process_func(test_items)
            return {'success': True, 'result': result}
        else:
            return {'success': False, 'error': 'No process function found'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@shared_task
def optimize_workflow(workflow_id: str):
    """
    Analyze workflow and generate optimization suggestions.
    """
    try:
        workflow = Workflow.objects.get(id=workflow_id)
        
        # Get execution metrics
        executions = WorkflowExecution.objects.filter(workflow=workflow)
        node_executions = NodeExecution.objects.filter(
            workflow_execution__workflow=workflow
        )
        
        # Calculate metrics
        avg_execution_time = 0
        slow_nodes = []
        node_times = {}
        
        for node_exec in node_executions:
            if node_exec.started_at and node_exec.finished_at:
                duration = (node_exec.finished_at - node_exec.started_at).total_seconds()
                node_id = str(node_exec.node.id) if node_exec.node else 'unknown'
                if node_id not in node_times:
                    node_times[node_id] = []
                node_times[node_id].append(duration)
        
        # Find slow nodes
        for node_id, times in node_times.items():
            avg_time = sum(times) / len(times) if times else 0
            if avg_time > 5:  # More than 5 seconds
                slow_nodes.append({
                    'node_id': node_id,
                    'avg_time': avg_time,
                    'count': len(times)
                })
        
        # Generate optimization suggestions
        suggestions = []
        
        # Parallelism suggestion
        graph = workflow.graph
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        # Find nodes that can run in parallel
        parallel_candidates = []
        for node in nodes:
            node_id = node.get('id')
            # Check if node has no dependencies or dependencies are completed
            incoming = [e for e in edges if e.get('target') == node_id]
            if len(incoming) <= 1:
                parallel_candidates.append(node_id)
        
        if len(parallel_candidates) > 1:
            suggestions.append({
                'type': 'parallelism',
                'suggestion': f"Nodes {', '.join(parallel_candidates)} can run in parallel",
                'predicted_improvement': {'time_reduction': '30-50%'}
            })
        
        # Retry tuning
        if slow_nodes:
            suggestions.append({
                'type': 'retry_tuning',
                'suggestion': f"Slow nodes detected: {[n['node_id'] for n in slow_nodes]}. Consider increasing retry delays.",
                'predicted_improvement': {'reliability': 'increased'}
            })
        
        # Create optimization records
        for suggestion in suggestions:
            AIWorkflowOptimization.objects.create(
                workflow=workflow,
                user=workflow.owner,
                optimization_type=suggestion['type'],
                suggestion=suggestion['suggestion'],
                current_metrics={'slow_nodes': slow_nodes},
                predicted_improvement=suggestion.get('predicted_improvement', {})
            )
        
        logger.info(f"Workflow optimization completed: {workflow_id}")
        
    except Exception as e:
        logger.error(f"Workflow optimization failed: {e}", exc_info=True)


