"""
Business Intelligence and Advanced Analytics
Executive dashboards, ROI analysis, and predictive insights
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.core.cache import cache
import logging

from ..models import WorkflowExecution, ExecutionAnalytics, Organization
from ..analytics.performance_monitor import analytics_engine

logger = logging.getLogger(__name__)

class BusinessIntelligenceEngine:
    """
    Advanced business intelligence and analytics engine
    """
    
    def __init__(self):
        self.cache_timeout = 1800  # 30 minutes
    
    def generate_executive_dashboard(self, organization_id: str, time_period: int = 30) -> Dict[str, Any]:
        """
        Generate executive dashboard with key business metrics
        """
        try:
            cache_key = f"executive_dashboard:{organization_id}:{time_period}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
            
            since = timezone.now() - timedelta(days=time_period)
            
            # Core metrics
            executions = WorkflowExecution.objects.filter(
                tenant_id=organization_id,
                created_at__gte=since
            )
            
            total_executions = executions.count()
            successful_executions = executions.filter(status='completed').count()
            failed_executions = executions.filter(status='failed').count()
            
            success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
            
            # Cost analysis
            analytics = ExecutionAnalytics.objects.filter(
                tenant_id=organization_id,
                created_at__gte=since
            )
            
            total_cost = analytics.aggregate(Sum('cost_dollars'))['cost_dollars__sum'] or 0
            avg_cost_per_execution = total_cost / total_executions if total_executions > 0 else 0
            
            # Time savings calculation (estimated)
            total_duration = analytics.aggregate(Sum('duration_seconds'))['duration_seconds__sum'] or 0
            estimated_manual_time = total_executions * 1800  # 30 minutes per manual task
            time_saved_hours = (estimated_manual_time - total_duration) / 3600
            
            # ROI calculation
            estimated_hourly_rate = 50  # $50/hour average
            cost_savings = time_saved_hours * estimated_hourly_rate
            roi_percentage = ((cost_savings - total_cost) / total_cost * 100) if total_cost > 0 else 0
            
            # Workflow performance
            top_workflows = executions.values('workflow__name').annotate(
                execution_count=Count('id'),
                success_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
            ).order_by('-execution_count')[:10]
            
            # Trend analysis
            daily_trends = self._calculate_daily_trends(organization_id, time_period)
            
            # Error analysis
            error_categories = self._analyze_error_patterns(organization_id, time_period)
            
            # Resource utilization
            resource_metrics = self._calculate_resource_utilization(organization_id, time_period)
            
            dashboard_data = {
                'period': {
                    'days': time_period,
                    'start_date': since.date().isoformat(),
                    'end_date': timezone.now().date().isoformat()
                },
                'key_metrics': {
                    'total_executions': total_executions,
                    'success_rate_percentage': round(success_rate, 2),
                    'total_cost_dollars': round(total_cost, 2),
                    'cost_per_execution': round(avg_cost_per_execution, 4),
                    'time_saved_hours': round(time_saved_hours, 1),
                    'roi_percentage': round(roi_percentage, 1),
                    'cost_savings_dollars': round(cost_savings, 2)
                },
                'performance': {
                    'top_workflows': list(top_workflows),
                    'daily_trends': daily_trends,
                    'resource_utilization': resource_metrics
                },
                'quality': {
                    'error_categories': error_categories,
                    'reliability_score': min(100, success_rate + 5)  # Adjusted reliability score
                },
                'insights': self._generate_executive_insights(
                    success_rate, roi_percentage, time_saved_hours, error_categories
                )
            }
            
            cache.set(cache_key, dashboard_data, self.cache_timeout)
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error generating executive dashboard: {e}")
            return {'error': str(e)}
    
    def _calculate_daily_trends(self, organization_id: str, days: int) -> List[Dict[str, Any]]:
        """Calculate daily execution trends"""
        trends = []
        
        for i in range(days):
            day = timezone.now() - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_executions = WorkflowExecution.objects.filter(
                tenant_id=organization_id,
                created_at__gte=day_start,
                created_at__lt=day_end
            )
            
            day_analytics = ExecutionAnalytics.objects.filter(
                tenant_id=organization_id,
                created_at__gte=day_start,
                created_at__lt=day_end
            )
            
            total = day_executions.count()
            successful = day_executions.filter(status='completed').count()
            cost = day_analytics.aggregate(Sum('cost_dollars'))['cost_dollars__sum'] or 0
            
            trends.append({
                'date': day_start.date().isoformat(),
                'executions': total,
                'success_rate': (successful / total * 100) if total > 0 else 0,
                'cost': round(cost, 2)
            })
        
        return list(reversed(trends))  # Chronological order
    
    def _analyze_error_patterns(self, organization_id: str, days: int) -> List[Dict[str, Any]]:
        """Analyze error patterns and categorize them"""
        since = timezone.now() - timedelta(days=days)
        
        failed_executions = WorkflowExecution.objects.filter(
            tenant_id=organization_id,
            created_at__gte=since,
            status='failed'
        ).values('error_message').annotate(count=Count('id')).order_by('-count')[:10]
        
        # Categorize errors
        error_categories = {
            'network': ['timeout', 'connection', 'network', 'dns'],
            'authentication': ['auth', 'unauthorized', 'forbidden', 'token'],
            'validation': ['validation', 'invalid', 'missing', 'required'],
            'rate_limit': ['rate limit', 'throttle', 'quota'],
            'system': ['internal', 'server error', 'database', 'memory']
        }
        
        categorized_errors = {}
        
        for error in failed_executions:
            message = (error['error_message'] or '').lower()
            category = 'other'
            
            for cat, keywords in error_categories.items():
                if any(keyword in message for keyword in keywords):
                    category = cat
                    break
            
            if category not in categorized_errors:
                categorized_errors[category] = {'count': 0, 'examples': []}
            
            categorized_errors[category]['count'] += error['count']
            if len(categorized_errors[category]['examples']) < 3:
                categorized_errors[category]['examples'].append(error['error_message'])
        
        return [
            {
                'category': category,
                'count': data['count'],
                'examples': data['examples']
            }
            for category, data in sorted(categorized_errors.items(), key=lambda x: x[1]['count'], reverse=True)
        ]
    
    def _calculate_resource_utilization(self, organization_id: str, days: int) -> Dict[str, Any]:
        """Calculate resource utilization metrics"""
        since = timezone.now() - timedelta(days=days)
        
        analytics = ExecutionAnalytics.objects.filter(
            tenant_id=organization_id,
            created_at__gte=since
        )
        
        if not analytics.exists():
            return {
                'cpu_utilization': 0,
                'memory_utilization': 0,
                'storage_utilization': 0,
                'network_utilization': 0
            }
        
        avg_cpu = analytics.aggregate(Avg('cpu_usage_seconds'))['cpu_usage_seconds__avg'] or 0
        avg_memory = analytics.aggregate(Avg('memory_usage_mb'))['memory_usage_mb__avg'] or 0
        
        # Simplified utilization calculation (in production, use real metrics)
        return {
            'cpu_utilization': min(100, avg_cpu / 10),  # Normalize to percentage
            'memory_utilization': min(100, avg_memory / 100),  # Normalize to percentage
            'storage_utilization': 45,  # Placeholder
            'network_utilization': 30   # Placeholder
        }
    
    def _generate_executive_insights(self, success_rate: float, roi: float, 
                                   time_saved: float, errors: List[Dict]) -> List[Dict[str, Any]]:
        """Generate actionable insights for executives"""
        insights = []
        
        # Success rate insights
        if success_rate < 95:
            insights.append({
                'type': 'warning',
                'title': 'Reliability Concern',
                'message': f'Success rate of {success_rate:.1f}% is below target of 95%',
                'recommendation': 'Review error patterns and implement additional error handling',
                'priority': 'high'
            })
        elif success_rate > 98:
            insights.append({
                'type': 'success',
                'title': 'Excellent Reliability',
                'message': f'Success rate of {success_rate:.1f}% exceeds industry standards',
                'recommendation': 'Consider expanding automation to additional processes',
                'priority': 'low'
            })
        
        # ROI insights
        if roi > 200:
            insights.append({
                'type': 'success',
                'title': 'Strong ROI Performance',
                'message': f'ROI of {roi:.1f}% demonstrates significant value creation',
                'recommendation': 'Scale successful workflows to maximize returns',
                'priority': 'medium'
            })
        elif roi < 50:
            insights.append({
                'type': 'warning',
                'title': 'ROI Below Target',
                'message': f'ROI of {roi:.1f}% may indicate optimization opportunities',
                'recommendation': 'Review workflow efficiency and cost optimization',
                'priority': 'high'
            })
        
        # Time savings insights
        if time_saved > 100:
            insights.append({
                'type': 'success',
                'title': 'Significant Time Savings',
                'message': f'{time_saved:.1f} hours saved through automation',
                'recommendation': 'Document and share success stories across organization',
                'priority': 'low'
            })
        
        # Error pattern insights
        if errors:
            top_error = errors[0]
            insights.append({
                'type': 'info',
                'title': 'Primary Error Category',
                'message': f'Most common errors are {top_error["category"]}-related ({top_error["count"]} occurrences)',
                'recommendation': f'Focus improvement efforts on {top_error["category"]} error handling',
                'priority': 'medium'
            })
        
        return insights
    
    def generate_cost_analysis(self, organization_id: str, time_period: int = 90) -> Dict[str, Any]:
        """
        Generate detailed cost analysis and optimization recommendations
        """
        try:
            since = timezone.now() - timedelta(days=time_period)
            
            analytics = ExecutionAnalytics.objects.filter(
                tenant_id=organization_id,
                created_at__gte=since
            )
            
            if not analytics.exists():
                return {'error': 'No data available for cost analysis'}
            
            # Cost breakdown by workflow
            workflow_costs = analytics.values('workflow_name').annotate(
                total_cost=Sum('cost_dollars'),
                execution_count=Count('id'),
                avg_cost=Avg('cost_dollars')
            ).order_by('-total_cost')[:20]
            
            # Cost trends over time
            cost_trends = []
            for i in range(0, time_period, 7):  # Weekly intervals
                week_start = since + timedelta(days=i)
                week_end = week_start + timedelta(days=7)
                
                week_cost = analytics.filter(
                    created_at__gte=week_start,
                    created_at__lt=week_end
                ).aggregate(Sum('cost_dollars'))['cost_dollars__sum'] or 0
                
                cost_trends.append({
                    'week_start': week_start.date().isoformat(),
                    'cost': round(week_cost, 2)
                })
            
            # Cost optimization opportunities
            optimization_opportunities = []
            
            # High-cost, low-efficiency workflows
            inefficient_workflows = analytics.values('workflow_name').annotate(
                total_cost=Sum('cost_dollars'),
                avg_duration=Avg('duration_seconds'),
                failure_rate=Count('id', filter=Q(failed_node_count__gt=0)) * 100.0 / Count('id')
            ).filter(total_cost__gt=1.0, failure_rate__gt=10).order_by('-total_cost')[:5]
            
            for workflow in inefficient_workflows:
                optimization_opportunities.append({
                    'type': 'efficiency',
                    'workflow': workflow['workflow_name'],
                    'issue': f"High cost (${workflow['total_cost']:.2f}) with {workflow['failure_rate']:.1f}% failure rate",
                    'recommendation': 'Review error handling and optimize node configuration',
                    'potential_savings': workflow['total_cost'] * 0.3  # Estimated 30% savings
                })
            
            # Resource optimization
            high_memory_workflows = analytics.filter(
                memory_usage_mb__gt=500
            ).values('workflow_name').annotate(
                avg_memory=Avg('memory_usage_mb'),
                total_cost=Sum('cost_dollars')
            ).order_by('-avg_memory')[:5]
            
            for workflow in high_memory_workflows:
                optimization_opportunities.append({
                    'type': 'resource',
                    'workflow': workflow['workflow_name'],
                    'issue': f"High memory usage ({workflow['avg_memory']:.1f}MB average)",
                    'recommendation': 'Optimize data processing and consider streaming approaches',
                    'potential_savings': workflow['total_cost'] * 0.2  # Estimated 20% savings
                })
            
            total_cost = analytics.aggregate(Sum('cost_dollars'))['cost_dollars__sum'] or 0
            total_potential_savings = sum(opp['potential_savings'] for opp in optimization_opportunities)
            
            return {
                'period': {
                    'days': time_period,
                    'start_date': since.date().isoformat(),
                    'end_date': timezone.now().date().isoformat()
                },
                'summary': {
                    'total_cost': round(total_cost, 2),
                    'average_daily_cost': round(total_cost / time_period, 2),
                    'cost_per_execution': round(total_cost / analytics.count(), 4),
                    'potential_savings': round(total_potential_savings, 2),
                    'optimization_percentage': round(total_potential_savings / total_cost * 100, 1) if total_cost > 0 else 0
                },
                'breakdown': {
                    'by_workflow': list(workflow_costs),
                    'trends': cost_trends
                },
                'optimization_opportunities': optimization_opportunities
            }
            
        except Exception as e:
            logger.error(f"Error generating cost analysis: {e}")
            return {'error': str(e)}
    
    def generate_predictive_insights(self, organization_id: str) -> Dict[str, Any]:
        """
        Generate predictive insights using historical data
        """
        try:
            # Get 90 days of historical data
            since = timezone.now() - timedelta(days=90)
            
            analytics = ExecutionAnalytics.objects.filter(
                tenant_id=organization_id,
                created_at__gte=since
            ).order_by('created_at')
            
            if analytics.count() < 30:  # Need minimum data
                return {'error': 'Insufficient historical data for predictions'}
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(analytics.values(
                'created_at', 'duration_seconds', 'cost_dollars', 
                'memory_usage_mb', 'node_count'
            ))
            
            df['created_at'] = pd.to_datetime(df['created_at'])
            df.set_index('created_at', inplace=True)
            
            # Resample to daily data
            daily_data = df.resample('D').agg({
                'duration_seconds': 'mean',
                'cost_dollars': 'sum',
                'memory_usage_mb': 'mean',
                'node_count': 'mean'
            }).fillna(0)
            
            predictions = {}
            
            # Simple trend-based predictions (in production, use more sophisticated models)
            for column in daily_data.columns:
                values = daily_data[column].values
                if len(values) >= 7:  # Need at least a week of data
                    # Calculate 7-day moving average trend
                    recent_avg = values[-7:].mean()
                    older_avg = values[-14:-7].mean() if len(values) >= 14 else values[:-7].mean()
                    
                    trend = (recent_avg - older_avg) / older_avg * 100 if older_avg > 0 else 0
                    
                    # Predict next 30 days
                    if abs(trend) > 5:  # Significant trend
                        predicted_change = trend * 4  # Extrapolate monthly
                        predicted_value = recent_avg * (1 + predicted_change / 100)
                    else:
                        predicted_value = recent_avg
                    
                    predictions[column] = {
                        'current_average': round(recent_avg, 2),
                        'predicted_monthly': round(predicted_value, 2),
                        'trend_percentage': round(trend, 1),
                        'confidence': 'medium' if abs(trend) < 20 else 'low'
                    }
            
            # Generate recommendations based on predictions
            recommendations = []
            
            if 'cost_dollars' in predictions:
                cost_trend = predictions['cost_dollars']['trend_percentage']
                if cost_trend > 15:
                    recommendations.append({
                        'type': 'cost_management',
                        'priority': 'high',
                        'message': f'Costs trending upward by {cost_trend:.1f}%',
                        'action': 'Review and optimize high-cost workflows'
                    })
            
            if 'memory_usage_mb' in predictions:
                memory_trend = predictions['memory_usage_mb']['trend_percentage']
                if memory_trend > 20:
                    recommendations.append({
                        'type': 'resource_planning',
                        'priority': 'medium',
                        'message': f'Memory usage increasing by {memory_trend:.1f}%',
                        'action': 'Plan for additional memory resources'
                    })
            
            return {
                'predictions': predictions,
                'recommendations': recommendations,
                'data_quality': {
                    'days_analyzed': len(daily_data),
                    'confidence_level': 'medium' if len(daily_data) >= 30 else 'low'
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating predictive insights: {e}")
            return {'error': str(e)}

# Global business intelligence engine
bi_engine = BusinessIntelligenceEngine()