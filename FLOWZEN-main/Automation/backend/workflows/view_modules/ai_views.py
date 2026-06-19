"""
AI-powered workflow API endpoints
Natural language to workflow conversion and optimization
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import logging

from ..ai.workflow_generator import workflow_generator, workflow_optimizer
from ..models import Workflow, WorkflowExecution
from ..serializers import WorkflowSerializer
from ..security.rbac import rbac_manager, Permission

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_workflow(request):
    """
    Generate workflow from natural language description
    """
    try:
        # Check AI permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.AI_USE_BASIC
        ):
            return Response(
                {'error': 'Insufficient permissions for AI features'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate input
        description = request.data.get('description', '').strip()
        if not description:
            return Response(
                {'error': 'Description is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(description) > 2000:
            return Response(
                {'error': 'Description too long (max 2000 characters)'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user context
        user_context = request.data.get('user_context', {})
        user_context.update({
            'user_id': request.user.id,
            'tenant_id': request.tenant.id,
            'organization': request.tenant.name
        })
        
        # Generate workflow
        result = workflow_generator.generate_workflow(description, user_context)
        
        if not result['success']:
            return Response(
                {'error': result['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Optionally save the workflow
        save_workflow = request.data.get('save_workflow', False)
        workflow_id = None
        
        if save_workflow:
            workflow_data = result['workflow']
            workflow = Workflow.objects.create(
                name=workflow_data['name'],
                description=workflow_data['description'],
                definition=workflow_data,
                tenant=request.tenant,
                created_by=request.user,
                is_active=True
            )
            workflow_id = workflow.id
            
            # Log the creation
            rbac_manager.log_security_action(
                user=request.user,
                organization=request.tenant,
                action='ai_generate_workflow',
                resource_type='workflow',
                resource_id=str(workflow.id),
                success=True,
                details={
                    'description': description[:100] + '...' if len(description) > 100 else description,
                    'ai_confidence': result.get('ai_confidence', 0)
                },
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        return Response({
            'success': True,
            'workflow': result['workflow'],
            'workflow_id': workflow_id,
            'ai_confidence': result.get('ai_confidence', 0),
            'original_description': description,
            'suggestions': workflow_generator.suggest_improvements(result['workflow'])
        })
        
    except Exception as e:
        logger.error(f"AI workflow generation error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def optimize_workflow(request):
    """
    Optimize existing workflow using AI
    """
    try:
        # Check AI permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.AI_USE_ADVANCED
        ):
            return Response(
                {'error': 'Insufficient permissions for advanced AI features'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get workflow data
        workflow_data = request.data.get('workflow')
        if not workflow_data:
            return Response(
                {'error': 'Workflow data is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get execution statistics
        execution_stats = request.data.get('execution_stats', {})
        
        # If workflow ID is provided, get real execution stats
        workflow_id = request.data.get('workflow_id')
        if workflow_id:
            try:
                workflow = Workflow.objects.get(id=workflow_id, tenant=request.tenant)
                
                # Check read permission
                if not rbac_manager.check_permission(
                    request.user, 
                    request.tenant, 
                    Permission.WORKFLOW_READ,
                    'workflow',
                    str(workflow.id)
                ):
                    return Response(
                        {'error': 'No permission to access this workflow'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Calculate real execution stats
                executions = WorkflowExecution.objects.filter(
                    workflow=workflow,
                    tenant=request.tenant
                ).order_by('-created_at')[:100]  # Last 100 executions
                
                if executions:
                    total_executions = len(executions)
                    successful_executions = sum(1 for e in executions if e.status == 'completed')
                    
                    # Calculate average duration
                    durations = []
                    for execution in executions:
                        if execution.completed_at and execution.started_at:
                            duration = (execution.completed_at - execution.started_at).total_seconds()
                            durations.append(duration)
                    
                    avg_duration = sum(durations) / len(durations) if durations else 0
                    success_rate = (successful_executions / total_executions) * 100
                    
                    execution_stats = {
                        'avg_duration': avg_duration,
                        'success_rate': success_rate,
                        'total_executions': total_executions,
                        'slow_nodes': [],  # TODO: Implement slow node detection
                        'error_patterns': []  # TODO: Implement error pattern analysis
                    }
                
            except Workflow.DoesNotExist:
                return Response(
                    {'error': 'Workflow not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Optimize workflow
        result = workflow_optimizer.optimize_performance(workflow_data, execution_stats)
        
        if not result['success']:
            return Response(
                {'error': result['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Detect anti-patterns
        anti_patterns = workflow_optimizer.detect_anti_patterns(workflow_data)
        
        # Log the optimization
        rbac_manager.log_security_action(
            user=request.user,
            organization=request.tenant,
            action='ai_optimize_workflow',
            resource_type='workflow',
            resource_id=workflow_id or '',
            success=True,
            details={
                'optimization_type': 'performance',
                'anti_patterns_found': len(anti_patterns)
            },
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'success': True,
            'optimized_workflow': result.get('optimized_workflow'),
            'explanation': result.get('explanation', ''),
            'estimated_improvement': result.get('estimated_improvement', ''),
            'anti_patterns': anti_patterns,
            'suggestions': result.get('suggestions', [])
        })
        
    except Exception as e:
        logger.error(f"AI workflow optimization error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_workflow(request):
    """
    Analyze workflow for insights and recommendations
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.AI_USE_BASIC
        ):
            return Response(
                {'error': 'Insufficient permissions for AI features'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        workflow_data = request.data.get('workflow')
        if not workflow_data:
            return Response(
                {'error': 'Workflow data is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate suggestions
        suggestions = workflow_generator.suggest_improvements(workflow_data)
        
        # Detect anti-patterns
        anti_patterns = workflow_optimizer.detect_anti_patterns(workflow_data)
        
        # Calculate complexity metrics
        nodes = workflow_data.get('nodes', [])
        edges = workflow_data.get('edges', [])
        
        complexity_metrics = {
            'node_count': len(nodes),
            'connection_count': len(edges),
            'complexity_score': len(nodes) * 2 + len(edges),
            'has_error_handling': any(node.get('type') == 'condition' for node in nodes),
            'has_loops': any(node.get('type') == 'loop' for node in nodes),
            'external_dependencies': sum(1 for node in nodes if node.get('type') in ['http_request', 'email', 'slack'])
        }
        
        # Estimate execution time
        estimated_time = 0
        for node in nodes:
            node_type = node.get('type', '')
            if node_type == 'delay':
                config = node.get('config', {})
                amount = config.get('amount', 1)
                unit = config.get('unit', 'minutes')
                multipliers = {'seconds': 1, 'minutes': 60, 'hours': 3600}
                estimated_time += amount * multipliers.get(unit, 60)
            elif node_type in ['http_request', 'ai_processing']:
                estimated_time += 10  # 10 seconds average
            elif node_type == 'email':
                estimated_time += 2   # 2 seconds average
            else:
                estimated_time += 1   # 1 second default
        
        return Response({
            'success': True,
            'analysis': {
                'complexity_metrics': complexity_metrics,
                'estimated_execution_time_seconds': estimated_time,
                'suggestions': suggestions,
                'anti_patterns': anti_patterns,
                'risk_assessment': {
                    'level': 'low' if len(anti_patterns) == 0 else 'medium' if len(anti_patterns) < 3 else 'high',
                    'factors': [pattern['type'] for pattern in anti_patterns]
                }
            }
        })
        
    except Exception as e:
        logger.error(f"AI workflow analysis error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_documentation(request):
    """
    Generate comprehensive documentation for workflow
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.AI_USE_BASIC
        ):
            return Response(
                {'error': 'Insufficient permissions for AI features'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        workflow_data = request.data.get('workflow')
        if not workflow_data:
            return Response(
                {'error': 'Workflow data is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate documentation
        documentation = workflow_generator.generate_documentation(workflow_data)
        
        return Response({
            'success': True,
            'documentation': documentation,
            'format': 'markdown'
        })
        
    except Exception as e:
        logger.error(f"AI documentation generation error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_capabilities(request):
    """
    Get available AI capabilities and limits
    """
    try:
        # Check user's AI permissions
        has_basic_ai = rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.AI_USE_BASIC
        )
        
        has_advanced_ai = rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.AI_USE_ADVANCED
        )
        
        capabilities = {
            'workflow_generation': {
                'available': has_basic_ai,
                'description': 'Generate workflows from natural language descriptions',
                'limits': {
                    'max_description_length': 2000,
                    'daily_limit': 50 if has_basic_ai else 0
                }
            },
            'workflow_optimization': {
                'available': has_advanced_ai,
                'description': 'AI-powered workflow performance optimization',
                'limits': {
                    'daily_limit': 20 if has_advanced_ai else 0
                }
            },
            'workflow_analysis': {
                'available': has_basic_ai,
                'description': 'Analyze workflows for insights and recommendations',
                'limits': {
                    'daily_limit': 100 if has_basic_ai else 0
                }
            },
            'documentation_generation': {
                'available': has_basic_ai,
                'description': 'Generate comprehensive workflow documentation',
                'limits': {
                    'daily_limit': 30 if has_basic_ai else 0
                }
            }
        }
        
        return Response({
            'success': True,
            'capabilities': capabilities,
            'ai_models': {
                'text_generation': 'gpt-4',
                'image_analysis': 'gpt-4-vision-preview',
                'optimization': 'gpt-4'
            }
        })
        
    except Exception as e:
        logger.error(f"AI capabilities error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def developer_assistant(request):
    """
    AI assistant for developers - provides contextual help, debugging, and code assistance
    """
    try:
        # Check AI permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.AI_USE_BASIC
        ):
            return Response(
                {'error': 'Insufficient permissions for AI features'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate input
        message = request.data.get('message', '').strip()
        if not message:
            return Response(
                {'error': 'Message is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(message) > 2000:
            return Response(
                {'error': 'Message too long (max 2000 characters)'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get context
        context = request.data.get('context', 'developer')
        current_section = request.data.get('current_section', 'unknown')
        conversation_history = request.data.get('conversation_history', [])
        
        # Generate developer-focused response
        result = workflow_generator.generate_developer_response(
            message, 
            context, 
            current_section, 
            conversation_history
        )
        
        if not result['success']:
            return Response(
                {'error': result['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Log the interaction
        rbac_manager.log_security_action(
            user=request.user,
            organization=request.tenant,
            action='ai_developer_assistant',
            resource_type='ai_chat',
            resource_id='',
            success=True,
            details={
                'message_length': len(message),
                'context': context,
                'current_section': current_section
            },
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'success': True,
            'message': result['message'],
            'code': result.get('code'),
            'suggestions': result.get('suggestions', []),
            'actions': result.get('actions', []),
            'context': context
        })
        
    except Exception as e:
        logger.error(f"AI developer assistant error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_conversation(request):
    """
    General AI chat conversation endpoint for both user and developer contexts
    """
    try:
        # Check AI permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.AI_USE_BASIC
        ):
            return Response(
                {'error': 'Insufficient permissions for AI features'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate input
        message = request.data.get('message', '').strip()
        if not message:
            return Response(
                {'error': 'Message is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get context and conversation data
        context = request.data.get('context', 'user')  # 'user' or 'developer'
        conversation_history = request.data.get('conversation_history', [])
        user_context = request.data.get('user_context', {})
        
        # Route to appropriate handler based on context
        if context == 'developer':
            result = workflow_generator.generate_developer_response(
                message, 
                context, 
                user_context.get('current_section', 'unknown'), 
                conversation_history
            )
        else:
            # Check if this looks like a workflow generation request
            workflow_keywords = ['workflow', 'automate', 'create', 'build', 'when', 'trigger', 'send', 'email']
            is_workflow_request = any(keyword in message.lower() for keyword in workflow_keywords)
            
            if is_workflow_request:
                # Use workflow generation
                result = workflow_generator.generate_workflow(message, user_context)
                if result['success']:
                    result['message'] = f"I can help you create that workflow! Here's what I suggest:\n\n{result.get('workflow', {}).get('description', 'A custom workflow for your needs.')}"
            else:
                # Use general chat response
                result = workflow_generator.generate_chat_response(message, conversation_history, user_context)
        
        if not result['success']:
            return Response(
                {'error': result['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'success': True,
            'message': result['message'],
            'workflow': result.get('workflow'),
            'code': result.get('code'),
            'suggestions': result.get('suggestions', []),
            'actions': result.get('actions', []),
            'context': context
        })
        
    except Exception as e:
        logger.error(f"AI chat conversation error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )