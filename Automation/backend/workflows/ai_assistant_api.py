"""
🤖 AI ASSISTANT BACKEND API WITH BYTEZ INTEGRATION

This module provides the backend API for the AI workflow assistant,
including natural language processing, workflow generation, and optimization
powered by Bytez AI (Llama-3.1-8B-Instruct).
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import re
import requests
from typing import Dict, List, Any
import uuid
from datetime import datetime
import os

class BytezAIClient:
    """Client for Bytez AI API integration."""
    
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = "https://bytez.com/models"
        self.model_id = "meta-llama/Llama-3.1-8B-Instruct"
        
    def generate_response(self, prompt: str, system_prompt: str = None, max_tokens: int = 1000) -> str:
        """Generate AI response using Bytez API."""
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            messages = []
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user", 
                "content": prompt
            })
            
            payload = {
                "modelId": self.model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "top_p": 0.9
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content'].strip()
                elif 'response' in data:
                    return data['response'].strip()
                else:
                    return "I'm having trouble processing your request right now."
            else:
                print(f"Bytez API error: {response.status_code} - {response.text}")
                return "I'm experiencing technical difficulties. Please try again."
                
        except Exception as e:
            print(f"Bytez AI client error: {e}")
            return "I'm currently unavailable. Please try again later."

class AIWorkflowAssistant:
    """Backend AI assistant for workflow automation."""
    
    def __init__(self):
        self.ai_client = BytezAIClient()
        self.workflow_templates = {
            'email': {
                'name': 'Email Automation Workflow',
                'description': 'Automated email sending workflow',
                'nodes': [
                    {
                        'id': str(uuid.uuid4()),
                        'type': 'webhook',
                        'name': 'Email Trigger',
                        'position': {'x': 100, 'y': 100},
                        'config': {
                            'path': '/webhook/email-trigger',
                            'method': 'POST'
                        }
                    },
                    {
                        'id': str(uuid.uuid4()),
                        'type': 'email',
                        'name': 'Send Email',
                        'position': {'x': 300, 'y': 100},
                        'config': {
                            'to': '{{trigger.email}}',
                            'subject': 'Welcome to our platform!',
                            'body': 'Thank you for signing up. We\'re excited to have you!'
                        }
                    }
                ],
                'edges': []
            },
            'backup': {
                'name': 'Data Backup Workflow',
                'description': 'Automated data backup system',
                'nodes': [
                    {
                        'id': str(uuid.uuid4()),
                        'type': 'schedule',
                        'name': 'Daily Backup Schedule',
                        'position': {'x': 100, 'y': 100},
                        'config': {
                            'cron': '0 2 * * *',
                            'timezone': 'UTC'
                        }
                    },
                    {
                        'id': str(uuid.uuid4()),
                        'type': 'backup',
                        'name': 'Database Backup',
                        'position': {'x': 300, 'y': 100},
                        'config': {
                            'source': 'database',
                            'destination': 's3://backups/',
                            'compression': True
                        }
                    },
                    {
                        'id': str(uuid.uuid4()),
                        'type': 'email',
                        'name': 'Backup Notification',
                        'position': {'x': 500, 'y': 100},
                        'config': {
                            'to': 'admin@company.com',
                            'subject': 'Backup Completed',
                            'body': 'Daily backup completed successfully at {{timestamp}}'
                        }
                    }
                ],
                'edges': []
            },
            'api': {
                'name': 'API Integration Workflow',
                'description': 'API data processing workflow',
                'nodes': [
                    {
                        'id': str(uuid.uuid4()),
                        'type': 'webhook',
                        'name': 'API Webhook',
                        'position': {'x': 100, 'y': 100},
                        'config': {
                            'path': '/webhook/api-data',
                            'method': 'POST'
                        }
                    },
                    {
                        'id': str(uuid.uuid4()),
                        'type': 'transform',
                        'name': 'Data Transform',
                        'position': {'x': 300, 'y': 100},
                        'config': {
                            'mapping': {
                                'user_id': '$.data.id',
                                'email': '$.data.email',
                                'name': '$.data.full_name'
                            }
                        }
                    },
                    {
                        'id': str(uuid.uuid4()),
                        'type': 'http_request',
                        'name': 'External API Call',
                        'position': {'x': 500, 'y': 100},
                        'config': {
                            'method': 'POST',
                            'url': 'https://api.example.com/users',
                            'headers': {
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer {{credentials.api_token}}'
                            }
                        }
                    }
                ],
                'edges': []
            }
        }
        
        self.optimization_rules = [
            {
                'condition': lambda workflow: len(workflow.get('nodes', [])) > 3,
                'suggestion': 'Consider using parallel execution for independent operations to improve performance'
            },
            {
                'condition': lambda workflow: not any(node.get('type') == 'error_handler' for node in workflow.get('nodes', [])),
                'suggestion': 'Add error handling nodes to make your workflow more robust'
            },
            {
                'condition': lambda workflow: any(node.get('type') == 'http_request' for node in workflow.get('nodes', [])),
                'suggestion': 'Consider adding caching for API calls to reduce latency and costs'
            },
            {
                'condition': lambda workflow: not any(node.get('type') == 'logger' for node in workflow.get('nodes', [])),
                'suggestion': 'Add logging nodes to help with debugging and monitoring'
            }
        ]
    
    def process_natural_language(self, message: str) -> Dict[str, Any]:
        """Process natural language input using Bytez AI and determine intent."""
        
        system_prompt = """You are an AI assistant for a workflow automation platform. Your job is to understand user requests and classify their intent.

Analyze the user's message and respond with ONLY a JSON object in this exact format:
{
    "intent": "one of: create_email, create_backup, create_api, create_notification, create_data_processing, optimize, explain, find_errors, general",
    "confidence": 0.0-1.0,
    "workflow_type": "email|backup|api|notification|data_processing|custom",
    "parameters": {
        "trigger_type": "webhook|schedule|manual",
        "description": "brief description of what user wants"
    }
}

Intent classifications:
- create_email: User wants email automation (welcome emails, notifications, etc.)
- create_backup: User wants data backup/sync workflows  
- create_api: User wants API integrations or HTTP requests
- create_notification: User wants alerts, notifications, messaging
- create_data_processing: User wants data transformation, filtering, analysis
- optimize: User wants to improve existing workflow performance
- explain: User wants explanation of workflow functionality
- find_errors: User wants to debug or find issues
- general: General questions or unclear intent

Examples:
"Create an email workflow" -> {"intent": "create_email", "confidence": 0.9, "workflow_type": "email", "parameters": {"trigger_type": "webhook", "description": "email automation workflow"}}
"Build a backup system" -> {"intent": "create_backup", "confidence": 0.9, "workflow_type": "backup", "parameters": {"trigger_type": "schedule", "description": "automated backup system"}}
"Optimize my workflow" -> {"intent": "optimize", "confidence": 0.8, "workflow_type": "custom", "parameters": {"description": "workflow optimization"}}"""

        user_prompt = f"User message: '{message}'"
        
        try:
            ai_response = self.ai_client.generate_response(user_prompt, system_prompt, max_tokens=200)
            
            # Try to parse JSON response
            try:
                # Extract JSON from response if it contains other text
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = ai_response[json_start:json_end]
                    result = json.loads(json_str)
                    
                    # Validate required fields
                    if 'intent' in result and 'confidence' in result:
                        return {
                            'intent': result.get('intent', 'general'),
                            'confidence': float(result.get('confidence', 0.5)),
                            'workflow_type': result.get('workflow_type', 'custom'),
                            'parameters': result.get('parameters', {}),
                            'original_message': message,
                            'ai_analysis': ai_response
                        }
            except (json.JSONDecodeError, ValueError):
                pass
            
            # Fallback to rule-based classification
            return self._fallback_intent_detection(message, ai_response)
            
        except Exception as e:
            print(f"AI processing error: {e}")
            return self._fallback_intent_detection(message)
    
    def _fallback_intent_detection(self, message: str, ai_response: str = None) -> Dict[str, Any]:
        """Fallback intent detection using rules."""
        
        message_lower = message.lower()
        
        # Intent detection patterns
        intents = {
            'create_email': [
                r'create.*email', r'build.*email', r'make.*email',
                r'email.*automation', r'email.*workflow', r'send.*email'
            ],
            'create_backup': [
                r'create.*backup', r'build.*backup', r'make.*backup',
                r'backup.*system', r'backup.*workflow', r'data.*backup'
            ],
            'create_api': [
                r'create.*api', r'build.*api', r'make.*api',
                r'api.*integration', r'api.*workflow', r'connect.*api'
            ],
            'optimize': [
                r'optimize', r'improve', r'enhance', r'better',
                r'performance', r'speed.*up', r'make.*faster'
            ],
            'explain': [
                r'explain', r'what.*does', r'how.*works', r'describe',
                r'tell.*me.*about', r'what.*is'
            ],
            'find_errors': [
                r'find.*error', r'check.*error', r'debug', r'problem',
                r'issue', r'bug', r'fix', r'wrong'
            ]
        }
        
        detected_intent = 'general'
        confidence = 0.0
        
        for intent, patterns in intents.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    detected_intent = intent
                    confidence = 0.7
                    break
            if confidence > 0:
                break
        
        return {
            'intent': detected_intent,
            'confidence': confidence,
            'workflow_type': detected_intent.replace('create_', '') if detected_intent.startswith('create_') else 'custom',
            'parameters': {'description': message},
            'original_message': message,
            'ai_analysis': ai_response or 'Fallback rule-based detection'
        }
    
    def generate_workflow(self, intent: str, message: str, parameters: Dict = None) -> Dict[str, Any]:
        """Generate a workflow using AI based on detected intent and user requirements."""
        
        if not parameters:
            parameters = {}
        
        # Use AI to generate intelligent workflow
        system_prompt = """You are an expert workflow automation designer. Create detailed workflow specifications based on user requirements.

Respond with ONLY a JSON object containing a complete workflow specification:
{
    "name": "Workflow Name",
    "description": "Brief description",
    "nodes": [
        {
            "id": "unique_id",
            "type": "node_type",
            "name": "Node Name", 
            "position": {"x": 100, "y": 100},
            "config": {
                "key": "value"
            }
        }
    ],
    "edges": [
        {
            "id": "edge_id",
            "source": "source_node_id",
            "target": "target_node_id"
        }
    ]
}

Available node types:
- webhook: HTTP endpoint trigger
- schedule: Time-based trigger  
- email: Send emails
- http_request: Make API calls
- transform: Data transformation
- condition: Conditional logic
- logger: Logging
- backup: Data backup
- notification: Send notifications
- database: Database operations

Node positioning: Start at x=100, space nodes 200px apart horizontally.
Always include proper node IDs, configurations, and connections."""

        user_prompt = f"""Create a workflow for: "{message}"
Intent: {intent}
Requirements: {parameters.get('description', message)}
Trigger type preference: {parameters.get('trigger_type', 'webhook')}

Make it practical and production-ready with proper error handling."""

        try:
            ai_response = self.ai_client.generate_response(user_prompt, system_prompt, max_tokens=800)
            
            # Try to parse AI-generated workflow
            try:
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = ai_response[json_start:json_end]
                    workflow = json.loads(json_str)
                    
                    # Validate and enhance workflow
                    if 'nodes' in workflow and 'edges' in workflow:
                        # Ensure all nodes have unique IDs
                        for i, node in enumerate(workflow['nodes']):
                            if 'id' not in node:
                                node['id'] = str(uuid.uuid4())
                        
                        # Ensure all edges have IDs
                        for i, edge in enumerate(workflow['edges']):
                            if 'id' not in edge:
                                edge['id'] = str(uuid.uuid4())
                        
                        return {
                            'success': True,
                            'workflow': workflow,
                            'message': f"✨ I've created a {workflow.get('name', 'custom workflow')} for you! The workflow includes {len(workflow['nodes'])} nodes and is ready to use.",
                            'ai_generated': True
                        }
            except (json.JSONDecodeError, ValueError) as e:
                print(f"AI workflow parsing error: {e}")
                pass
            
            # Fallback to template-based generation
            return self._generate_template_workflow(intent, message)
            
        except Exception as e:
            print(f"AI workflow generation error: {e}")
            return self._generate_template_workflow(intent, message)
    
    def _generate_template_workflow(self, intent: str, message: str) -> Dict[str, Any]:
        """Fallback template-based workflow generation."""
        
        if intent.startswith('create_'):
            workflow_type = intent.replace('create_', '')
            if workflow_type in self.workflow_templates:
                template = self.workflow_templates[workflow_type].copy()
                
                # Connect nodes with edges
                nodes = template['nodes']
                edges = []
                for i in range(len(nodes) - 1):
                    edges.append({
                        'id': str(uuid.uuid4()),
                        'source': nodes[i]['id'],
                        'target': nodes[i + 1]['id']
                    })
                template['edges'] = edges
                
                return {
                    'success': True,
                    'workflow': template,
                    'message': f"✨ I've created a {template['name']} for you! The workflow includes {len(nodes)} nodes and is ready to use.",
                    'ai_generated': False
                }
        
        return {
            'success': False,
            'message': "I couldn't generate a workflow for that request. Try asking for an email, backup, or API workflow.",
            'ai_generated': False
        }
    
    def optimize_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze workflow and provide AI-powered optimization suggestions."""
        
        if not workflow or not workflow.get('nodes'):
            return {
                'success': False,
                'message': "I don't see any workflow to optimize. Please create or open a workflow first!"
            }
        
        # Use AI for intelligent optimization analysis
        system_prompt = """You are a workflow optimization expert. Analyze the provided workflow and suggest specific improvements.

Respond with ONLY a JSON object:
{
    "suggestions": [
        {
            "type": "performance|reliability|security|maintainability",
            "priority": "high|medium|low", 
            "title": "Brief title",
            "description": "Detailed explanation",
            "implementation": "How to implement this suggestion"
        }
    ],
    "overall_score": 1-10,
    "summary": "Brief overall assessment"
}

Focus on:
- Performance bottlenecks
- Error handling gaps
- Security vulnerabilities  
- Scalability issues
- Best practices violations
- Missing monitoring/logging"""

        workflow_description = f"""Workflow Analysis:
Name: {workflow.get('name', 'Unnamed Workflow')}
Nodes: {len(workflow.get('nodes', []))} 
Node Types: {[node.get('type') for node in workflow.get('nodes', [])]}
Connections: {len(workflow.get('edges', []))}

Detailed Structure:
{json.dumps(workflow, indent=2)}"""

        try:
            ai_response = self.ai_client.generate_response(workflow_description, system_prompt, max_tokens=600)
            
            # Try to parse AI optimization suggestions
            try:
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = ai_response[json_start:json_end]
                    analysis = json.loads(json_str)
                    
                    if 'suggestions' in analysis:
                        suggestions = analysis['suggestions']
                        score = analysis.get('overall_score', 7)
                        summary = analysis.get('summary', 'Workflow analysis completed')
                        
                        if suggestions:
                            message = f"🎯 Workflow Optimization Analysis (Score: {score}/10)\n\n{summary}\n\n"
                            message += f"I found {len(suggestions)} optimization opportunities:\n\n"
                            
                            for i, suggestion in enumerate(suggestions, 1):
                                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(suggestion.get('priority', 'medium'), '🟡')
                                message += f"{i}. {priority_emoji} **{suggestion.get('title', 'Optimization')}** ({suggestion.get('priority', 'medium')} priority)\n"
                                message += f"   {suggestion.get('description', 'No description')}\n"
                                if suggestion.get('implementation'):
                                    message += f"   💡 *How to fix: {suggestion.get('implementation')}*\n\n"
                            
                            return {
                                'success': True,
                                'suggestions': suggestions,
                                'score': score,
                                'summary': summary,
                                'message': message,
                                'ai_generated': True
                            }
            except (json.JSONDecodeError, ValueError):
                pass
            
            # Fallback to rule-based optimization
            return self._fallback_optimization(workflow)
            
        except Exception as e:
            print(f"AI optimization error: {e}")
            return self._fallback_optimization(workflow)
    
    def _fallback_optimization(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback rule-based optimization."""
        
        suggestions = []
        for rule in self.optimization_rules:
            if rule['condition'](workflow):
                suggestions.append(rule['suggestion'])
        
        if suggestions:
            return {
                'success': True,
                'suggestions': suggestions,
                'message': f"I found {len(suggestions)} optimization opportunities:\n\n" + 
                          "\n".join(f"• {suggestion}" for suggestion in suggestions),
                'ai_generated': False
            }
        else:
            return {
                'success': True,
                'suggestions': [],
                'message': "Your workflow is already well-optimized! Great job! 🎉",
                'ai_generated': False
            }
    
    def explain_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an AI-powered explanation of the workflow."""
        
        if not workflow or not workflow.get('nodes'):
            return {
                'success': False,
                'message': "I don't see any workflow to explain. Please create or open a workflow first!"
            }
        
        # Use AI for intelligent workflow explanation
        system_prompt = """You are a workflow documentation expert. Explain the provided workflow in a clear, comprehensive way.

Create an explanation that includes:
1. Overview of what the workflow does
2. Step-by-step breakdown of each node
3. Data flow and connections
4. Business value and use cases
5. Potential improvements or considerations

Make it accessible to both technical and non-technical users. Use emojis and clear formatting."""

        workflow_description = f"""Workflow to Explain:
Name: {workflow.get('name', 'Unnamed Workflow')}
Description: {workflow.get('description', 'No description provided')}

Nodes ({len(workflow.get('nodes', []))}):
{json.dumps(workflow.get('nodes', []), indent=2)}

Connections ({len(workflow.get('edges', []))}):
{json.dumps(workflow.get('edges', []), indent=2)}"""

        try:
            ai_response = self.ai_client.generate_response(workflow_description, system_prompt, max_tokens=800)
            
            if ai_response and len(ai_response.strip()) > 50:
                return {
                    'success': True,
                    'explanation': ai_response,
                    'message': ai_response,
                    'ai_generated': True
                }
            else:
                return self._fallback_explanation(workflow)
                
        except Exception as e:
            print(f"AI explanation error: {e}")
            return self._fallback_explanation(workflow)
    
    def _fallback_explanation(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback rule-based explanation."""
        
        nodes = workflow.get('nodes', [])
        node_count = len(nodes)
        node_types = list(set(node.get('type', 'unknown') for node in nodes))
        
        explanation = f"📋 **Workflow Overview**\n\n"
        explanation += f"This workflow contains {node_count} nodes with the following types: {', '.join(node_types)}.\n\n"
        explanation += "**Step-by-Step Breakdown:**\n\n"
        
        for i, node in enumerate(nodes, 1):
            node_type = node.get('type', 'unknown')
            node_name = node.get('name', f'Node {i}')
            description = self.get_node_description(node_type)
            explanation += f"{i}. **{node_name}** ({node_type})\n   {description}\n\n"
        
        return {
            'success': True,
            'explanation': explanation,
            'message': explanation,
            'ai_generated': False
        }
    
    def find_errors(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Find potential errors using AI-powered analysis."""
        
        if not workflow:
            return {
                'success': False,
                'message': "I don't see any workflow to check. Please create or open a workflow first!"
            }
        
        nodes = workflow.get('nodes', [])
        edges = workflow.get('edges', [])
        
        if not nodes:
            return {
                'success': True,
                'errors': [{'type': 'warning', 'message': 'Workflow is empty - add some nodes to get started'}],
                'message': 'Your workflow is empty. Add some nodes to get started!'
            }
        
        # Use AI for intelligent error detection
        system_prompt = """You are a workflow quality assurance expert. Analyze the provided workflow for errors, issues, and potential problems.

Respond with ONLY a JSON object:
{
    "errors": [
        {
            "type": "error|warning|info",
            "severity": "critical|high|medium|low",
            "category": "configuration|connectivity|security|performance|best_practices",
            "message": "Clear description of the issue",
            "node_id": "affected_node_id_if_applicable",
            "suggestion": "How to fix this issue"
        }
    ],
    "overall_health": "excellent|good|fair|poor",
    "summary": "Brief overall assessment"
}

Check for:
- Missing required configurations
- Disconnected nodes
- Security vulnerabilities
- Performance issues
- Best practice violations
- Data flow problems
- Error handling gaps"""

        workflow_analysis = f"""Workflow Error Analysis:
Name: {workflow.get('name', 'Unnamed Workflow')}
Nodes: {len(nodes)}
Edges: {len(edges)}

Node Details:
{json.dumps(nodes, indent=2)}

Edge Details:
{json.dumps(edges, indent=2)}"""

        try:
            ai_response = self.ai_client.generate_response(workflow_analysis, system_prompt, max_tokens=600)
            
            # Try to parse AI error analysis
            try:
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = ai_response[json_start:json_end]
                    analysis = json.loads(json_str)
                    
                    if 'errors' in analysis:
                        errors = analysis['errors']
                        health = analysis.get('overall_health', 'good')
                        summary = analysis.get('summary', 'Analysis completed')
                        
                        if errors:
                            health_emoji = {
                                'excellent': '🟢', 'good': '🟡', 'fair': '🟠', 'poor': '🔴'
                            }.get(health, '🟡')
                            
                            message = f"🔍 **Workflow Health Check** {health_emoji}\n\n"
                            message += f"**Overall Health:** {health.title()}\n"
                            message += f"**Summary:** {summary}\n\n"
                            message += f"**Issues Found:** {len(errors)}\n\n"
                            
                            for i, error in enumerate(errors, 1):
                                severity_emoji = {
                                    'critical': '🚨', 'high': '🔴', 'medium': '🟡', 'low': '🟢'
                                }.get(error.get('severity', 'medium'), '🟡')
                                
                                message += f"{i}. {severity_emoji} **{error.get('message', 'Unknown issue')}**\n"
                                message += f"   *Category:* {error.get('category', 'general')}\n"
                                if error.get('suggestion'):
                                    message += f"   *Fix:* {error.get('suggestion')}\n"
                                message += "\n"
                            
                            return {
                                'success': True,
                                'errors': errors,
                                'health': health,
                                'summary': summary,
                                'message': message,
                                'ai_generated': True
                            }
                        else:
                            return {
                                'success': True,
                                'errors': [],
                                'health': health,
                                'summary': summary,
                                'message': f"🎉 **Excellent!** {summary}\n\nYour workflow looks great with no issues found!",
                                'ai_generated': True
                            }
            except (json.JSONDecodeError, ValueError):
                pass
            
            # Fallback to rule-based error detection
            return self._fallback_error_detection(workflow)
            
        except Exception as e:
            print(f"AI error detection error: {e}")
            return self._fallback_error_detection(workflow)
    
    def _fallback_error_detection(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback rule-based error detection."""
        
        errors = []
        nodes = workflow.get('nodes', [])
        edges = workflow.get('edges', [])
        
        # Check for disconnected nodes
        connected_nodes = set()
        for edge in edges:
            connected_nodes.add(edge.get('source'))
            connected_nodes.add(edge.get('target'))
        
        for node in nodes:
            node_id = node.get('id')
            if node_id not in connected_nodes and len(nodes) > 1:
                errors.append({
                    'type': 'warning',
                    'message': f'Node "{node.get("name", node_id)}" is not connected to other nodes'
                })
        
        # Check for missing configurations
        for node in nodes:
            config = node.get('config', {})
            if not config:
                errors.append({
                    'type': 'error',
                    'message': f'Node "{node.get("name", node.get("id"))}" is missing configuration'
                })
        
        if errors:
            error_summary = f"I found {len(errors)} potential issues:\n\n"
            error_summary += "\n".join(f"• {error['message']} ({error['type']})" for error in errors)
            error_summary += "\n\nWould you like me to help fix these issues?"
            
            return {
                'success': True,
                'errors': errors,
                'message': error_summary,
                'ai_generated': False
            }
        else:
            return {
                'success': True,
                'errors': [],
                'message': "Excellent! I didn't find any issues in your workflow. Everything looks perfect! ✨",
                'ai_generated': False
            }
    
    def get_node_description(self, node_type: str) -> str:
        """Get a human-readable description of a node type."""
        
        descriptions = {
            'webhook': 'Receives HTTP requests to trigger the workflow',
            'schedule': 'Runs the workflow on a scheduled basis',
            'email': 'Sends email notifications',
            'http_request': 'Makes API calls to external services',
            'transform': 'Transforms and processes data',
            'condition': 'Makes decisions based on conditions',
            'logger': 'Logs information for debugging',
            'backup': 'Performs data backup operations',
            'error_handler': 'Handles errors and exceptions'
        }
        
        return descriptions.get(node_type, f'Performs {node_type} operations')
    
    def get_suggestions(self, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get contextual suggestions for the user."""
        
        suggestions = [
            {
                'title': '🚀 Create Email Workflow',
                'description': 'Build an automated email system',
                'example': 'Create an email automation workflow'
            },
            {
                'title': '💾 Create Backup System',
                'description': 'Set up automated data backups',
                'example': 'Build a daily backup system'
            },
            {
                'title': '🔗 Create API Integration',
                'description': 'Connect external services',
                'example': 'Create an API integration workflow'
            },
            {
                'title': '⚡ Optimize Workflow',
                'description': 'Get performance improvements',
                'example': 'Optimize my current workflow'
            },
            {
                'title': '🔍 Find Issues',
                'description': 'Scan for potential problems',
                'example': 'Check my workflow for errors'
            }
        ]
        
        return suggestions

# Global AI assistant instance
ai_assistant = AIWorkflowAssistant()

@csrf_exempt
@require_http_methods(["POST"])
def ai_chat(request):
    """Handle AI chat messages."""
    
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        
        if not message:
            return JsonResponse({
                'success': False,
                'message': 'Please provide a message'
            })
        
        # Process the message
        intent_result = ai_assistant.process_natural_language(message)
        intent = intent_result['intent']
        
        # Generate response based on intent
        if intent.startswith('create_'):
            result = ai_assistant.generate_workflow(intent, message)
        elif intent == 'optimize':
            workflow = data.get('workflow', {})
            result = ai_assistant.optimize_workflow(workflow)
        elif intent == 'explain':
            workflow = data.get('workflow', {})
            result = ai_assistant.explain_workflow(workflow)
        elif intent == 'find_errors':
            workflow = data.get('workflow', {})
            result = ai_assistant.find_errors(workflow)
        else:
            # General response
            result = {
                'success': True,
                'message': "I'm here to help you build amazing workflows! Try asking me to:\n\n" +
                          "• Create an email automation workflow\n" +
                          "• Build a backup system\n" +
                          "• Create an API integration\n" +
                          "• Optimize your current workflow\n" +
                          "• Find errors in your workflow\n\n" +
                          "What would you like to create today?"
            }
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        })

@csrf_exempt
@require_http_methods(["GET"])
def ai_suggestions(request):
    """Get AI suggestions for the user."""
    
    try:
        suggestions = ai_assistant.get_suggestions()
        return JsonResponse({
            'success': True,
            'suggestions': suggestions
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        })

@csrf_exempt
@require_http_methods(["POST"])
def ai_generate_workflow(request):
    """Generate a workflow based on user input."""
    
    try:
        data = json.loads(request.body)
        workflow_type = data.get('type', 'email')
        description = data.get('description', '')
        
        if workflow_type in ai_assistant.workflow_templates:
            template = ai_assistant.workflow_templates[workflow_type].copy()
            
            # Connect nodes with edges
            nodes = template['nodes']
            edges = []
            for i in range(len(nodes) - 1):
                edges.append({
                    'id': str(uuid.uuid4()),
                    'source': nodes[i]['id'],
                    'target': nodes[i + 1]['id']
                })
            template['edges'] = edges
            
            return JsonResponse({
                'success': True,
                'workflow': template,
                'message': f"✨ Generated {template['name']} successfully!"
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Unknown workflow type: {workflow_type}'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        })
