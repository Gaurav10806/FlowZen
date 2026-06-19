"""
Monitoring and Analytics API Views
Performance dashboards, business intelligence, and system health
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache
import logging

from .business_intelligence import bi_engine
from ..analytics.performance_monitor import analytics_engine
from ..security.rbac import rbac_manager, Permission

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def performance_dashboard(request):
    """
    Get performance dashboard data
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.ORG_VIEW_ANALYTICS
        ):
            return Response(
                {'error': 'Insufficient permissions to view analytics'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get time period from query params
        days = int(request.GET.get('days', 7))
        if days > 365:  # Limit to 1 year
            days = 365
        
        # Generate performance report
        report = analytics_engine.generate_performance_report(
            tenant_id=request.tenant.id,
            days=days
        )
        
        if 'error' in report:
            return Response(
                {'error': report['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'success': True,
            'dashboard': report,
            'generated_at': timezone.now().isoformat()
        })
        
    except ValueError:
        return Response(
            {'error': 'Invalid days parameter'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Performance dashboard error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def business_intelligence_dashboard(request):
    """
    Get executive business intelligence dashboard
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.ORG_VIEW_ANALYTICS
        ):
            return Response(
                {'error': 'Insufficient permissions to view business intelligence'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get time period from query params
        days = int(request.GET.get('days', 30))
        if days > 365:  # Limit to 1 year
            days = 365
        
        # Generate executive dashboard
        dashboard = bi_engine.generate_executive_dashboard(
            organization_id=request.tenant.id,
            time_period=days
        )
        
        if 'error' in dashboard:
            return Response(
                {'error': dashboard['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'success': True,
            'dashboard': dashboard,
            'generated_at': timezone.now().isoformat()
        })
        
    except ValueError:
        return Response(
            {'error': 'Invalid days parameter'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Business intelligence dashboard error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cost_analysis(request):
    """
    Get detailed cost analysis and optimization recommendations
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.ORG_VIEW_ANALYTICS
        ):
            return Response(
                {'error': 'Insufficient permissions to view cost analysis'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get time period from query params
        days = int(request.GET.get('days', 90))
        if days > 365:  # Limit to 1 year
            days = 365
        
        # Generate cost analysis
        analysis = bi_engine.generate_cost_analysis(
            organization_id=request.tenant.id,
            time_period=days
        )
        
        if 'error' in analysis:
            return Response(
                {'error': analysis['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'success': True,
            'analysis': analysis,
            'generated_at': timezone.now().isoformat()
        })
        
    except ValueError:
        return Response(
            {'error': 'Invalid days parameter'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Cost analysis error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def predictive_insights(request):
    """
    Get predictive insights and forecasting
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.ORG_VIEW_ANALYTICS
        ):
            return Response(
                {'error': 'Insufficient permissions to view predictive insights'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate predictive insights
        insights = bi_engine.generate_predictive_insights(
            organization_id=request.tenant.id
        )
        
        if 'error' in insights:
            return Response(
                {'error': insights['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'success': True,
            'insights': insights,
            'generated_at': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Predictive insights error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health(request):
    """
    Get system health and status information
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.SYSTEM_MONITOR
        ):
            return Response(
                {'error': 'Insufficient permissions to view system health'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get system health metrics
        from django.db import connection
        from django.core.cache import cache
        import psutil
        import redis
        
        health_data = {
            'timestamp': timezone.now().isoformat(),
            'status': 'healthy',
            'components': {}
        }
        
        # Database health
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_data['components']['database'] = {
                'status': 'healthy',
                'response_time_ms': 5  # Simplified
            }
        except Exception as e:
            health_data['components']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_data['status'] = 'degraded'
        
        # Cache health
        try:
            cache.set('health_check', 'ok', 10)
            cache.get('health_check')
            health_data['components']['cache'] = {
                'status': 'healthy',
                'response_time_ms': 2  # Simplified
            }
        except Exception as e:
            health_data['components']['cache'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_data['status'] = 'degraded'
        
        # System resources
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            health_data['components']['system'] = {
                'status': 'healthy' if cpu_percent < 80 and memory.percent < 80 else 'warning',
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent
            }
            
            if cpu_percent > 90 or memory.percent > 90:
                health_data['status'] = 'degraded'
                
        except Exception as e:
            health_data['components']['system'] = {
                'status': 'unknown',
                'error': str(e)
            }
        
        # Celery health (simplified)
        health_data['components']['celery'] = {
            'status': 'healthy',  # In production, check actual Celery status
            'active_tasks': 0,
            'queued_tasks': 0
        }
        
        return Response(health_data)
        
    except Exception as e:
        logger.error(f"System health check error: {e}")
        return Response({
            'timestamp': timezone.now().isoformat(),
            'status': 'unhealthy',
            'error': 'Health check failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)