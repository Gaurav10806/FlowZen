"""
Prompt Management System - Versioned Prompts with Templates and Testing

This module provides a comprehensive prompt management system with:
- Versioned prompts with rollback capability
- Template system with variable substitution
- A/B testing and performance monitoring
- Safety validation and content filtering
"""

import json
import uuid
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import re
import hashlib

from ..security_validators import PayloadSecurityValidator


logger = logging.getLogger(__name__)


class PromptType(Enum):
    """Types of prompts in the system."""
    AGENT_REACTIVE = "agent_reactive"
    AGENT_PLANNING = "agent_planning"
    AGENT_CONVERSATIONAL = "agent_conversational"
    AGENT_ANALYTICAL = "agent_analytical"
    TOOL_SELECTION = "tool_selection"
    SAFETY_CHECK = "safety_check"
    VALIDATION = "validation"
    CUSTOM = "custom"


class PromptStatus(Enum):
    """Prompt version status."""
    DRAFT = "draft"
    TESTING = "testing"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class PromptTemplate:
    """Represents a prompt template with variables."""
    template_id: str
    name: str
    prompt_type: PromptType
    template_content: str
    variables: List[str]
    required_variables: List[str]
    optional_variables: List[str]
    default_values: Dict[str, Any]
    validation_rules: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class PromptVersion:
    """Represents a specific version of a prompt."""
    version_id: str
    template_id: str
    version_number: int
    content: str
    status: PromptStatus
    created_by: str
    created_at: str
    activated_at: Optional[str]
    performance_metrics: Dict[str, Any]
    test_results: List[Dict[str, Any]]
    rollback_info: Optional[Dict[str, Any]]


@dataclass
class PromptExecution:
    """Records a prompt execution for monitoring."""
    execution_id: str
    template_id: str
    version_id: str
    variables: Dict[str, Any]
    rendered_prompt: str
    response: Optional[str]
    success: bool
    error_message: Optional[str]
    execution_time_ms: int
    tokens_used: int
    user_id: str
    tenant_id: str
    timestamp: str


class PromptManager:
    """
    Prompt Management System
    
    Manages versioned prompts with templates, variables, testing, and monitoring.
    Provides safe prompt rendering with validation and performance tracking.
    """
    
    def __init__(self):
        self.safety_validator = PayloadSecurityValidator()
        
        # Storage (in production, these would be database tables)
        self.templates: Dict[str, PromptTemplate] = {}
        self.versions: Dict[str, List[PromptVersion]] = {}  # template_id -> versions
        self.active_versions: Dict[str, str] = {}  # template_id -> active_version_id
        self.executions: List[PromptExecution] = []
        
        # Performance tracking
        self.performance_cache: Dict[str, Dict[str, Any]] = {}
        
        # Initialize built-in prompts
        self._initialize_built_in_prompts()
    
    def create_template(self, name: str, prompt_type: PromptType, template_content: str,
                       variables: List[str], required_variables: List[str] = None,
                       default_values: Dict[str, Any] = None, 
                       validation_rules: Dict[str, Any] = None,
                       metadata: Dict[str, Any] = None) -> str:
        """
        Create a new prompt template.
        
        Args:
            name: Template name
            prompt_type: Type of prompt
            template_content: Template content with variables
            variables: List of all variables in template
            required_variables: Variables that must be provided
            default_values: Default values for optional variables
            validation_rules: Validation rules for variables
            metadata: Additional metadata
            
        Returns:
            Template ID
        """
        template_id = str(uuid.uuid4())
        
        # Validate template content
        self._validate_template_content(template_content, variables)
        
        # Extract variables from template if not provided
        if not variables:
            variables = self._extract_variables(template_content)
        
        # Set defaults
        required_variables = required_variables or []
        optional_variables = [v for v in variables if v not in required_variables]
        default_values = default_values or {}
        validation_rules = validation_rules or {}
        metadata = metadata or {}
        
        # Create template
        template = PromptTemplate(
            template_id=template_id,
            name=name,
            prompt_type=prompt_type,
            template_content=template_content,
            variables=variables,
            required_variables=required_variables,
            optional_variables=optional_variables,
            default_values=default_values,
            validation_rules=validation_rules,
            metadata=metadata
        )
        
        # Store template
        self.templates[template_id] = template
        self.versions[template_id] = []
        
        logger.info(f"Created prompt template: {name} ({template_id})")
        
        return template_id
    
    def create_version(self, template_id: str, content: str, created_by: str,
                      status: PromptStatus = PromptStatus.DRAFT) -> str:
        """
        Create a new version of a prompt template.
        
        Args:
            template_id: Template ID
            content: Prompt content for this version
            created_by: User creating the version
            status: Initial status
            
        Returns:
            Version ID
        """
        if template_id not in self.templates:
            raise ValueError(f"Template {template_id} not found")
        
        template = self.templates[template_id]
        
        # Validate content against template
        self._validate_template_content(content, template.variables)
        
        # Generate version info
        version_id = str(uuid.uuid4())
        version_number = len(self.versions[template_id]) + 1
        
        # Create version
        version = PromptVersion(
            version_id=version_id,
            template_id=template_id,
            version_number=version_number,
            content=content,
            status=status,
            created_by=created_by,
            created_at=datetime.utcnow().isoformat(),
            activated_at=None,
            performance_metrics={},
            test_results=[],
            rollback_info=None
        )
        
        # Store version
        self.versions[template_id].append(version)
        
        logger.info(f"Created prompt version: {template.name} v{version_number} ({version_id})")
        
        return version_id
    
    def activate_version(self, template_id: str, version_id: str, activated_by: str) -> bool:
        """
        Activate a specific version of a prompt template.
        
        Args:
            template_id: Template ID
            version_id: Version ID to activate
            activated_by: User activating the version
            
        Returns:
            True if successful
        """
        if template_id not in self.templates:
            raise ValueError(f"Template {template_id} not found")
        
        # Find the version
        version = None
        for v in self.versions[template_id]:
            if v.version_id == version_id:
                version = v
                break
        
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        # Store rollback info for current active version
        if template_id in self.active_versions:
            current_version_id = self.active_versions[template_id]
            current_version = next(
                (v for v in self.versions[template_id] if v.version_id == current_version_id),
                None
            )
            if current_version:
                current_version.status = PromptStatus.DEPRECATED
        
        # Activate new version
        version.status = PromptStatus.ACTIVE
        version.activated_at = datetime.utcnow().isoformat()
        self.active_versions[template_id] = version_id
        
        logger.info(f"Activated prompt version: {version_id} for template {template_id}")
        
        return True
    
    def build_prompt(self, prompt_name: str, variables: Dict[str, Any],
                    user_id: str = "", tenant_id: str = "") -> str:
        """
        Build a prompt from template with variable substitution.
        
        Args:
            prompt_name: Name of the prompt template or prompt type
            variables: Variables to substitute
            user_id: User ID for logging
            tenant_id: Tenant ID for logging
            
        Returns:
            Rendered prompt
        """
        start_time = datetime.utcnow()
        
        # Find template by name or type
        template = self._find_template(prompt_name)
        if not template:
            raise ValueError(f"Prompt template '{prompt_name}' not found")
        
        # Get active version
        if template.template_id not in self.active_versions:
            raise ValueError(f"No active version for template '{prompt_name}'")
        
        version_id = self.active_versions[template.template_id]
        version = next(
            (v for v in self.versions[template.template_id] if v.version_id == version_id),
            None
        )
        
        if not version:
            raise ValueError(f"Active version {version_id} not found")
        
        try:
            # Validate variables
            validated_variables = self._validate_variables(template, variables)
            
            # Render prompt
            rendered_prompt = self._render_template(version.content, validated_variables)
            
            # Validate rendered prompt
            self._validate_rendered_prompt(rendered_prompt)
            
            # Calculate execution time
            end_time = datetime.utcnow()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Log execution
            execution = PromptExecution(
                execution_id=str(uuid.uuid4()),
                template_id=template.template_id,
                version_id=version_id,
                variables=validated_variables,
                rendered_prompt=rendered_prompt,
                response=None,
                success=True,
                error_message=None,
                execution_time_ms=execution_time_ms,
                tokens_used=len(rendered_prompt.split()),  # Rough token estimate
                user_id=user_id,
                tenant_id=tenant_id,
                timestamp=start_time.isoformat()
            )
            
            self.executions.append(execution)
            
            return rendered_prompt
            
        except Exception as e:
            # Log failed execution
            end_time = datetime.utcnow()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            execution = PromptExecution(
                execution_id=str(uuid.uuid4()),
                template_id=template.template_id,
                version_id=version_id,
                variables=variables,
                rendered_prompt="",
                response=None,
                success=False,
                error_message=str(e),
                execution_time_ms=execution_time_ms,
                tokens_used=0,
                user_id=user_id,
                tenant_id=tenant_id,
                timestamp=start_time.isoformat()
            )
            
            self.executions.append(execution)
            
            raise ValueError(f"Failed to build prompt: {str(e)}")
    
    def test_prompt_version(self, template_id: str, version_id: str, 
                           test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Test a prompt version with multiple test cases.
        
        Args:
            template_id: Template ID
            version_id: Version ID to test
            test_cases: List of test cases with variables and expected outcomes
            
        Returns:
            Test results
        """
        if template_id not in self.templates:
            raise ValueError(f"Template {template_id} not found")
        
        template = self.templates[template_id]
        version = next(
            (v for v in self.versions[template_id] if v.version_id == version_id),
            None
        )
        
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        test_results = []
        
        for i, test_case in enumerate(test_cases):
            test_id = f"test_{i+1}"
            test_variables = test_case.get('variables', {})
            expected_outcome = test_case.get('expected_outcome', {})
            
            try:
                # Validate variables
                validated_variables = self._validate_variables(template, test_variables)
                
                # Render prompt
                rendered_prompt = self._render_template(version.content, validated_variables)
                
                # Validate rendered prompt
                self._validate_rendered_prompt(rendered_prompt)
                
                # Check expected outcomes
                outcome_checks = self._check_expected_outcomes(rendered_prompt, expected_outcome)
                
                test_result = {
                    'test_id': test_id,
                    'success': True,
                    'rendered_prompt': rendered_prompt,
                    'outcome_checks': outcome_checks,
                    'error': None
                }
                
            except Exception as e:
                test_result = {
                    'test_id': test_id,
                    'success': False,
                    'rendered_prompt': "",
                    'outcome_checks': {},
                    'error': str(e)
                }
            
            test_results.append(test_result)
        
        # Calculate overall test metrics
        successful_tests = len([r for r in test_results if r['success']])
        success_rate = successful_tests / len(test_results) if test_results else 0
        
        # Store test results
        version.test_results.append({
            'test_run_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'test_cases_count': len(test_cases),
            'successful_tests': successful_tests,
            'success_rate': success_rate,
            'results': test_results
        })
        
        return {
            'test_run_id': version.test_results[-1]['test_run_id'],
            'success_rate': success_rate,
            'successful_tests': successful_tests,
            'total_tests': len(test_results),
            'results': test_results
        }
    
    def get_performance_metrics(self, template_id: str, time_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Get performance metrics for a prompt template.
        
        Args:
            template_id: Template ID
            time_range: Optional time range filter
            
        Returns:
            Performance metrics
        """
        if template_id not in self.templates:
            raise ValueError(f"Template {template_id} not found")
        
        # Filter executions
        template_executions = [
            exec for exec in self.executions
            if exec.template_id == template_id
        ]
        
        if time_range:
            start_time = time_range.get('start')
            end_time = time_range.get('end')
            
            if start_time:
                template_executions = [
                    exec for exec in template_executions
                    if exec.timestamp >= start_time
                ]
            
            if end_time:
                template_executions = [
                    exec for exec in template_executions
                    if exec.timestamp <= end_time
                ]
        
        if not template_executions:
            return {
                'total_executions': 0,
                'success_rate': 0,
                'average_execution_time_ms': 0,
                'total_tokens_used': 0,
                'error_rate': 0,
                'common_errors': []
            }
        
        # Calculate metrics
        total_executions = len(template_executions)
        successful_executions = len([e for e in template_executions if e.success])
        success_rate = successful_executions / total_executions
        
        total_execution_time = sum(e.execution_time_ms for e in template_executions)
        average_execution_time = total_execution_time / total_executions
        
        total_tokens = sum(e.tokens_used for e in template_executions)
        
        # Error analysis
        failed_executions = [e for e in template_executions if not e.success]
        error_rate = len(failed_executions) / total_executions
        
        error_counts = {}
        for execution in failed_executions:
            error = execution.error_message or "Unknown error"
            error_counts[error] = error_counts.get(error, 0) + 1
        
        common_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_executions': total_executions,
            'success_rate': success_rate,
            'average_execution_time_ms': average_execution_time,
            'total_tokens_used': total_tokens,
            'error_rate': error_rate,
            'common_errors': common_errors,
            'executions_by_version': self._get_executions_by_version(template_executions)
        }
    
    def rollback_version(self, template_id: str, target_version_id: str, rollback_by: str) -> bool:
        """
        Rollback to a previous version of a prompt template.
        
        Args:
            template_id: Template ID
            target_version_id: Version ID to rollback to
            rollback_by: User performing rollback
            
        Returns:
            True if successful
        """
        if template_id not in self.templates:
            raise ValueError(f"Template {template_id} not found")
        
        # Find target version
        target_version = next(
            (v for v in self.versions[template_id] if v.version_id == target_version_id),
            None
        )
        
        if not target_version:
            raise ValueError(f"Target version {target_version_id} not found")
        
        # Store current version info for rollback tracking
        current_version_id = self.active_versions.get(template_id)
        
        # Activate target version
        self.activate_version(template_id, target_version_id, rollback_by)
        
        # Update rollback info
        target_version.rollback_info = {
            'rollback_from': current_version_id,
            'rollback_by': rollback_by,
            'rollback_at': datetime.utcnow().isoformat(),
            'reason': 'Manual rollback'
        }
        
        logger.info(f"Rolled back template {template_id} to version {target_version_id}")
        
        return True
    
    def _initialize_built_in_prompts(self) -> None:
        """Initialize built-in prompt templates."""
        
        # Agent Reactive Prompt
        reactive_template_id = self.create_template(
            name="agent_reactive",
            prompt_type=PromptType.AGENT_REACTIVE,
            template_content="""You are an AI assistant helping users with their requests.

Goal: {{goal}}

User Input:
{{input_data}}

{% if memory_context %}
Relevant Context:
{{memory_context}}
{% endif %}

{% if available_tools %}
Available Tools: {{available_tools}}
{% endif %}

Please provide a helpful response to the user's request. Be concise and accurate.""",
            variables=["goal", "input_data", "memory_context", "available_tools"],
            required_variables=["goal", "input_data"],
            default_values={
                "memory_context": "",
                "available_tools": []
            }
        )
        
        self.create_version(reactive_template_id, self.templates[reactive_template_id].template_content, "system")
        self.activate_version(reactive_template_id, self.versions[reactive_template_id][0].version_id, "system")
        
        # Agent Planning Prompt
        planning_template_id = self.create_template(
            name="agent_planning",
            prompt_type=PromptType.AGENT_PLANNING,
            template_content="""You are an AI agent that creates detailed execution plans.

Goal: {{goal}}

Input Data:
{{input_data}}

{% if memory_context %}
Context from Memory:
{{memory_context}}
{% endif %}

Available Tools:
{% for tool in available_tools %}
- {{tool.name}}: {{tool.description}}
{% endfor %}

Create a step-by-step plan to achieve the goal. Format your response as:

PLAN:
1. [Step description] - Tool: [tool_name]
2. [Step description] - Tool: [tool_name]
...

REASONING:
[Explain your reasoning for this plan]

CONFIDENCE: [0.0-1.0]""",
            variables=["goal", "input_data", "memory_context", "available_tools"],
            required_variables=["goal", "input_data", "available_tools"]
        )
        
        self.create_version(planning_template_id, self.templates[planning_template_id].template_content, "system")
        self.activate_version(planning_template_id, self.versions[planning_template_id][0].version_id, "system")
        
        # Agent Conversational Prompt
        conversational_template_id = self.create_template(
            name="agent_conversational",
            prompt_type=PromptType.AGENT_CONVERSATIONAL,
            template_content="""You are an AI assistant engaged in a conversation with a user.

Goal: {{goal}}

Current Message:
{{input_data}}

{% if conversation_history %}
Conversation History:
{% for message in conversation_history %}
{{message.type}}: {{message.content}}
{% endfor %}
{% endif %}

{% if memory_context %}
Relevant Memory:
{{memory_context}}
{% endif %}

{% if available_tools %}
Available Tools: {{available_tools}}
{% endif %}

Continue the conversation naturally. If you need to use tools to help the user, indicate which tools you would use and why.""",
            variables=["goal", "input_data", "conversation_history", "memory_context", "available_tools"],
            required_variables=["goal", "input_data"]
        )
        
        self.create_version(conversational_template_id, self.templates[conversational_template_id].template_content, "system")
        self.activate_version(conversational_template_id, self.versions[conversational_template_id][0].version_id, "system")
        
        # Agent Analytical Prompt
        analytical_template_id = self.create_template(
            name="agent_analytical",
            prompt_type=PromptType.AGENT_ANALYTICAL,
            template_content="""You are an AI analyst performing deep analysis.

Goal: {{goal}}

Data to Analyze:
{{current_analysis}}

{% if previous_analysis_steps %}
Previous Analysis Steps:
{% for step in previous_analysis_steps %}
Step {{loop.index}}: {{step.content.analysis}}
{% endfor %}
{% endif %}

{% if memory_context %}
Relevant Context:
{{memory_context}}
{% endif %}

Perform the next step of analysis. Consider:
1. What insights can be drawn from the data?
2. What patterns or trends are evident?
3. What questions remain unanswered?
4. Should analysis continue?

Format your response as:
ANALYSIS: [Your analysis]
INSIGHTS: [Key insights]
NEXT_STEP_NEEDED: [true/false]
CONFIDENCE: [0.0-1.0]""",
            variables=["goal", "current_analysis", "previous_analysis_steps", "memory_context", "available_tools"],
            required_variables=["goal", "current_analysis"]
        )
        
        self.create_version(analytical_template_id, self.templates[analytical_template_id].template_content, "system")
        self.activate_version(analytical_template_id, self.versions[analytical_template_id][0].version_id, "system")
    
    def _validate_template_content(self, content: str, variables: List[str]) -> None:
        """Validate template content for safety and correctness."""
        # Check for dangerous patterns
        self.safety_validator._scan_for_dangerous_content(content)
        
        # Validate template syntax (simplified Jinja2-like validation)
        if '{{' in content and '}}' not in content:
            raise ValueError("Unmatched template brackets")
        
        # Check that all referenced variables are declared
        referenced_vars = self._extract_variables(content)
        undeclared_vars = set(referenced_vars) - set(variables)
        if undeclared_vars:
            raise ValueError(f"Undeclared variables in template: {undeclared_vars}")
    
    def _extract_variables(self, template_content: str) -> List[str]:
        """Extract variable names from template content."""
        # Simple regex to find {{variable}} patterns
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
        matches = re.findall(pattern, template_content)
        return list(set(matches))
    
    def _find_template(self, prompt_name: str) -> Optional[PromptTemplate]:
        """Find template by name or type."""
        # First try by name
        for template in self.templates.values():
            if template.name == prompt_name:
                return template
        
        # Then try by type
        try:
            prompt_type = PromptType(prompt_name)
            for template in self.templates.values():
                if template.prompt_type == prompt_type:
                    return template
        except ValueError:
            pass
        
        return None
    
    def _validate_variables(self, template: PromptTemplate, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and prepare variables for template rendering."""
        validated_variables = {}
        
        # Check required variables
        for var in template.required_variables:
            if var not in variables:
                raise ValueError(f"Required variable '{var}' not provided")
            validated_variables[var] = variables[var]
        
        # Add optional variables with defaults
        for var in template.optional_variables:
            if var in variables:
                validated_variables[var] = variables[var]
            elif var in template.default_values:
                validated_variables[var] = template.default_values[var]
        
        # Validate variable values
        for var, value in validated_variables.items():
            if var in template.validation_rules:
                self._validate_variable_value(var, value, template.validation_rules[var])
        
        # Sanitize variables
        for var, value in validated_variables.items():
            if isinstance(value, str):
                validated_variables[var] = self.safety_validator._sanitize_payload(value)
        
        return validated_variables
    
    def _validate_variable_value(self, var_name: str, value: Any, rules: Dict[str, Any]) -> None:
        """Validate a variable value against rules."""
        if 'type' in rules:
            expected_type = rules['type']
            if expected_type == 'string' and not isinstance(value, str):
                raise ValueError(f"Variable '{var_name}' must be a string")
            elif expected_type == 'number' and not isinstance(value, (int, float)):
                raise ValueError(f"Variable '{var_name}' must be a number")
            elif expected_type == 'list' and not isinstance(value, list):
                raise ValueError(f"Variable '{var_name}' must be a list")
        
        if 'max_length' in rules and isinstance(value, str):
            if len(value) > rules['max_length']:
                raise ValueError(f"Variable '{var_name}' exceeds maximum length")
    
    def _render_template(self, template_content: str, variables: Dict[str, Any]) -> str:
        """Render template with variables (simplified Jinja2-like rendering)."""
        rendered = template_content
        
        # Simple variable substitution
        for var, value in variables.items():
            pattern = r'\{\{\s*' + re.escape(var) + r'\s*\}\}'
            if isinstance(value, (list, dict)):
                value_str = json.dumps(value, indent=2)
            else:
                value_str = str(value)
            rendered = re.sub(pattern, value_str, rendered)
        
        # Handle conditional blocks (simplified)
        rendered = self._process_conditionals(rendered, variables)
        
        # Handle loops (simplified)
        rendered = self._process_loops(rendered, variables)
        
        return rendered
    
    def _process_conditionals(self, content: str, variables: Dict[str, Any]) -> str:
        """Process conditional blocks in template."""
        # Simple {% if variable %} ... {% endif %} processing
        pattern = r'\{\%\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\%\}(.*?)\{\%\s*endif\s*\%\}'
        
        def replace_conditional(match):
            var_name = match.group(1)
            block_content = match.group(2)
            
            if var_name in variables and variables[var_name]:
                return block_content
            else:
                return ""
        
        return re.sub(pattern, replace_conditional, content, flags=re.DOTALL)
    
    def _process_loops(self, content: str, variables: Dict[str, Any]) -> str:
        """Process loop blocks in template."""
        # Simple {% for item in list %} ... {% endfor %} processing
        pattern = r'\{\%\s*for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\%\}(.*?)\{\%\s*endfor\s*\%\}'
        
        def replace_loop(match):
            item_var = match.group(1)
            list_var = match.group(2)
            loop_content = match.group(3)
            
            if list_var not in variables or not isinstance(variables[list_var], list):
                return ""
            
            result = ""
            for i, item in enumerate(variables[list_var]):
                loop_iteration = loop_content
                
                # Replace item variable
                item_pattern = r'\{\{\s*' + re.escape(item_var) + r'\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
                
                def replace_item_attr(attr_match):
                    attr_name = attr_match.group(1)
                    if isinstance(item, dict) and attr_name in item:
                        return str(item[attr_name])
                    return ""
                
                loop_iteration = re.sub(item_pattern, replace_item_attr, loop_iteration)
                
                # Replace loop variable
                loop_iteration = loop_iteration.replace('{{loop.index}}', str(i + 1))
                
                result += loop_iteration
            
            return result
        
        return re.sub(pattern, replace_loop, content, flags=re.DOTALL)
    
    def _validate_rendered_prompt(self, prompt: str) -> None:
        """Validate the final rendered prompt."""
        if not prompt.strip():
            raise ValueError("Rendered prompt is empty")
        
        if len(prompt) > 50000:  # 50KB limit
            raise ValueError("Rendered prompt is too long")
        
        # Check for remaining unresolved variables
        if '{{' in prompt and '}}' in prompt:
            unresolved = re.findall(r'\{\{[^}]+\}\}', prompt)
            if unresolved:
                raise ValueError(f"Unresolved variables in prompt: {unresolved}")
    
    def _check_expected_outcomes(self, rendered_prompt: str, expected_outcome: Dict[str, Any]) -> Dict[str, bool]:
        """Check if rendered prompt meets expected outcomes."""
        checks = {}
        
        for check_name, check_value in expected_outcome.items():
            if check_name == 'contains':
                checks[check_name] = check_value in rendered_prompt
            elif check_name == 'not_contains':
                checks[check_name] = check_value not in rendered_prompt
            elif check_name == 'length_min':
                checks[check_name] = len(rendered_prompt) >= check_value
            elif check_name == 'length_max':
                checks[check_name] = len(rendered_prompt) <= check_value
            elif check_name == 'starts_with':
                checks[check_name] = rendered_prompt.startswith(check_value)
            elif check_name == 'ends_with':
                checks[check_name] = rendered_prompt.endswith(check_value)
        
        return checks
    
    def _get_executions_by_version(self, executions: List[PromptExecution]) -> Dict[str, Dict[str, Any]]:
        """Group executions by version and calculate metrics."""
        version_stats = {}
        
        for execution in executions:
            version_id = execution.version_id
            
            if version_id not in version_stats:
                version_stats[version_id] = {
                    'count': 0,
                    'success_count': 0,
                    'total_time_ms': 0,
                    'total_tokens': 0
                }
            
            stats = version_stats[version_id]
            stats['count'] += 1
            if execution.success:
                stats['success_count'] += 1
            stats['total_time_ms'] += execution.execution_time_ms
            stats['total_tokens'] += execution.tokens_used
        
        # Calculate averages
        for version_id, stats in version_stats.items():
            if stats['count'] > 0:
                stats['success_rate'] = stats['success_count'] / stats['count']
                stats['avg_time_ms'] = stats['total_time_ms'] / stats['count']
                stats['avg_tokens'] = stats['total_tokens'] / stats['count']
        
        return version_stats