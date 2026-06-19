"""
Advanced Performance Monitoring and Analytics System
Real-time metrics, predictive analytics, and business intelligence
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Avg, Sum, Q
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """
    Prometheus metrics for workflow performance monitoring
    """
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # Workflow execution metrics
        self.workflow_executions_total = Counter(
            'workflow_executions_total',
            'Total number of workflow executions',
            ['tenant_id', 'workflow_name', 'status'],
            registry=self.registry
        )
        
        self.workflow_execution_duration = Histogram(
            'workflow_execution_duration_seconds',
            'Workflow execution duration in seconds',
            ['tenant_id', 'workflow_name'],
            registry=self.registry
        )
        
        self.node_executions_total = Counter(
            'node_executions_total',
            'Total number of node executions',
            ['tenant_id', 'node_type', 'status'],
            registry=self.registry
        )
        
        self.node_execution_duration = Histogram(
            'node_execution_duration_seconds',
            'Node execution duration in seconds',
            ['tenant_id', 'node_type'],
            registry=self.registry
        )
        
        # System metrics
        self.active_executions = Gauge(
            'active_executions',
            'Number of currently active executions',
            ['tenant_id'],
            registry=self.registry
        )
        
        self.queue_size = Gauge(
            'celery_queue_size',
            'Number of tasks in Celery queues',
            ['queue_name'],
            registry=self.registry
        )
        
        self.error_rate = Gauge(
            'workflow_error_rate',
            'Workflow error rate percentage',
            ['tenant_id', 'time_window'],
            registry=self.registry
        )
        
        # Business metrics
        self.cost_per_execution = Gauge(
            'cost_per_execution_dollars',
            'Average cost per workflow execution',
            ['tenant_id', 'workflow_name'],
            registry=self.registry
        )
        
        self.sla_compliance = Gauge(
            'sla_compliance_percentage',
            'SLA compliance percentage',
            ['tenant_id', 'sla_type'],
            registry=self.registry
        )

class AnalyticsEngine:
    """
    Advanced analytics engine for workflow intelligence
    """
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.scaler = StandardScaler()
    
    def record_workflow_execution(self, execution):
        """Record workflow execution metrics"""
        try:
            # Update Prometheus metrics
            self.metrics.workflow_executions_total.labels(
                tenant_id=execution.tenant_id,
                workflow_name=execution.workflow.name,
                status=execution.status
            ).inc()
            
            if execution.completed_at and execution.started_at:
                duration = (execution.completed_at - execution.started_at).total_seconds()
                self.metrics.workflow_execution_duration.labels(
                    tenant_id=execution.tenant_id,
                    workflow_name=execution.workflow.name
                ).observe(duration)
            
            # Store detailed analytics data
            self._store_execution_analytics(execution)
            
        except Exception as e:
            logger.error(f"Error recording workflow execution metrics: {e}")
    
    def record_node_execution(self, node_execution):
        """Record node execution metrics"""
        try:
            self.metrics.node_executions_total.labels(
                tenant_id=node_execution.tenant_id,
                node_type=node_execution.node_type,
                status=node_execution.status
            ).inc()
            
            if node_execution.completed_at and node_execution.started_at:
                duration = (node_execution.completed_at - node_execution.started_at).total_seconds()
                self.metrics.node_execution_duration.labels(
                    tenant_id=node_execution.tenant_id,
                    node_type=node_execution.node_type
                ).observe(duration)
            
        except Exception as e:
            logger.error(f"Error recording node execution metrics: {e}")
    
    def _store_execution_analytics(self, execution):
        """Store detailed execution analytics"""
        from ..models import ExecutionAnalytics
        
        try:
            # Calculate execution metrics
            duration = None
            if execution.completed_at and execution.started_at:
                duration = (execution.completed_at - execution.started_at).total_seconds()
            
            # Count nodes and connections
            node_count = execution.node_executions.count()
            failed_nodes = execution.node_executions.filter(status='failed').count()
            
            # Calculate cost (simplified)
            base_cost = 0.001  # $0.001 per execution
            node_cost = node_count * 0.0001  # $0.0001 per node
            duration_cost = (duration or 0) * 0.00001  # $0.00001 per second
            total_cost = base_cost + node_cost + duration_cost
            
            ExecutionAnalytics.objects.create(
                execution=execution,
                tenant_id=execution.tenant_id,
                workflow_name=execution.workflow.name,
                duration_seconds=duration,
                node_count=node_count,
                failed_node_count=failed_nodes,
                cost_dollars=total_cost,
                memory_usage_mb=self._estimate_memory_usage(execution),
                cpu_usage_seconds=self._estimate_cpu_usage(execution),
                created_at=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error storing execution analytics: {e}")
    
    def _estimate_memory_usage(self, execution) -> float:
        """Estimate memory usage for execution"""
        # Simplified estimation based on node types and data size
        base_memory = 10  # 10MB base
        node_memory = execution.node_executions.count() * 2  # 2MB per node
        return base_memory + node_memory
    
    def _estimate_cpu_usage(self, execution) -> float:
        """Estimate CPU usage for execution"""
        # Simplified estimation
        if execution.completed_at and execution.started_at:
            return (execution.completed_at - execution.started_at).total_seconds() * 0.1
        return 0
    
    def detect_anomalies(self, tenant_id: str, time_window: int = 24) -> List[Dict[str, Any]]:
        """Detect anomalies in workflow executions"""
        try:
            from ..models import ExecutionAnalytics
            
            # Get recent execution data
            since = timezone.now() - timedelta(hours=time_window)
            analytics = ExecutionAnalytics.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=since
            ).values(
                'duration_seconds',
                'node_count',
                'failed_node_count',
                'cost_dollars',
                'memory_usage_mb',
                'cpu_usage_seconds'
            )
            
            if len(analytics) < 10:  # Need minimum data points
                return []
            
            # Prepare data for anomaly detection
            df = pd.DataFrame(analytics)
            df = df.fillna(0)  # Handle null values
            
            # Scale features
            scaled_data = self.scaler.fit_transform(df)
            
            # Detect anomalies
            anomaly_labels = self.anomaly_detector.fit_predict(scaled_data)
            
            # Get anomalous executions
            anomalies = []
            for i, label in enumerate(anomaly_labels):
                if label == -1:  # Anomaly
                    anomaly_data = df.iloc[i].to_dict()
                    anomaly_data['anomaly_score'] = self.anomaly_detector.score_samples([scaled_data[i]])[0]
                    anomalies.append(anomaly_data)
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []
    
    def generate_performance_report(self, tenant_id: str, days: int = 7) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        try:
            from ..models import WorkflowExecution, ExecutionAnalytics
            
            since = timezone.now() - timedelta(days=days)
            
            # Basic execution statistics
            executions = WorkflowExecution.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=since
            )
            
            total_executions = executions.count()
            successful_executions = executions.filter(status='completed').count()
            failed_executions = executions.filter(status='failed').count()
            
            success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
            
            # Performance metrics
            analytics = ExecutionAnalytics.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=since
            )
            
            avg_duration = analytics.aggregate(Avg('duration_seconds'))['duration_seconds__avg'] or 0
            total_cost = analytics.aggregate(Sum('cost_dollars'))['cost_dollars__sum'] or 0
            avg_memory = analytics.aggregate(Avg('memory_usage_mb'))['memory_usage_mb__avg'] or 0
            
            # Top workflows by execution count
            top_workflows = executions.values('workflow__name').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # Error analysis
            error_patterns = executions.filter(status='failed').values(
                'error_message'
            ).annotate(count=Count('id')).order_by('-count')[:5]
            
            # Trend analysis
            daily_stats = []
            for i in range(days):
                day = timezone.now() - timedelta(days=i)
                day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                
                day_executions = executions.filter(
                    created_at__gte=day_start,
                    created_at__lt=day_end
                )
                
                daily_stats.append({
                    'date': day_start.date().isoformat(),
                    'total_executions': day_executions.count(),
                    'successful_executions': day_executions.filter(status='completed').count(),
                    'failed_executions': day_executions.filter(status='failed').count(),
                })
            
            report = {
                'period': {
                    'start_date': since.date().isoformat(),
                    'end_date': timezone.now().date().isoformat(),
                    'days': days
                },
                'summary': {
                    'total_executions': total_executions,
                    'successful_executions': successful_executions,
                    'failed_executions': failed_executions,
                    'success_rate_percentage': round(success_rate, 2),
                    'average_duration_seconds': round(avg_duration, 2),
                    'total_cost_dollars': round(total_cost, 4),
                    'average_memory_usage_mb': round(avg_memory, 2)
                },
                'top_workflows': list(top_workflows),
                'error_patterns': list(error_patterns),
                'daily_trends': daily_stats,
                'anomalies': self.detect_anomalies(tenant_id, days * 24)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {}
    
    def predict_resource_usage(self, tenant_id: str, hours_ahead: int = 24) -> Dict[str, Any]:
        """Predict future resource usage using time series analysis"""
        try:
            from ..models import ExecutionAnalytics
            
            # Get historical data
            since = timezone.now() - timedelta(days=30)  # 30 days of history
            analytics = ExecutionAnalytics.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=since
            ).order_by('created_at')
            
            if analytics.count() < 100:  # Need sufficient data
                return {'error': 'Insufficient historical data for prediction'}
            
            # Prepare time series data
            df = pd.DataFrame(analytics.values(
                'created_at', 'duration_seconds', 'memory_usage_mb', 'cpu_usage_seconds'
            ))
            
            df['created_at'] = pd.to_datetime(df['created_at'])
            df.set_index('created_at', inplace=True)
            
            # Resample to hourly data
            hourly_data = df.resample('H').agg({
                'duration_seconds': 'mean',
                'memory_usage_mb': 'mean',
                'cpu_usage_seconds': 'sum'
            }).fillna(0)
            
            # Simple linear trend prediction (in production, use more sophisticated models)
            predictions = {}
            
            for column in ['duration_seconds', 'memory_usage_mb', 'cpu_usage_seconds']:
                # Calculate trend
                values = hourly_data[column].values
                x = np.arange(len(values))
                
                # Fit linear trend
                coeffs = np.polyfit(x, values, 1)
                trend = np.poly1d(coeffs)
                
                # Predict future values
                future_x = np.arange(len(values), len(values) + hours_ahead)
                future_values = trend(future_x)
                
                predictions[column] = {
                    'current_average': float(values[-24:].mean()) if len(values) >= 24 else float(values.mean()),
                    'predicted_average': float(future_values.mean()),
                    'trend': 'increasing' if coeffs[0] > 0 else 'decreasing',
                    'confidence': 'low'  # Simplified confidence
                }
            
            # Resource recommendations
            recommendations = []
            
            if predictions['memory_usage_mb']['trend'] == 'increasing':
                recommendations.append({
                    'type': 'memory',
                    'message': 'Consider increasing memory allocation for workers',
                    'priority': 'medium'
                })
            
            if predictions['cpu_usage_seconds']['trend'] == 'increasing':
                recommendations.append({
                    'type': 'cpu',
                    'message': 'Consider scaling up worker instances',
                    'priority': 'high'
                })
            
            return {
                'predictions': predictions,
                'recommendations': recommendations,
                'prediction_horizon_hours': hours_ahead,
                'confidence_level': 'medium'
            }
            
        except Exception as e:
            logger.error(f"Error predicting resource usage: {e}")
            return {'error': str(e)}
    
    def calculate_sla_compliance(self, tenant_id: str, sla_config: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate SLA compliance metrics"""
        try:
            from ..models import WorkflowExecution
            
            # Get SLA configuration
            max_duration = sla_config.get('max_duration_seconds', 300)  # 5 minutes default
            min_success_rate = sla_config.get('min_success_rate_percentage', 99.0)
            time_window_hours = sla_config.get('time_window_hours', 24)
            
            since = timezone.now() - timedelta(hours=time_window_hours)
            executions = WorkflowExecution.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=since,
                status__in=['completed', 'failed']
            )
            
            total_executions = executions.count()
            if total_executions == 0:
                return {'compliance': 100.0, 'details': 'No executions in time window'}
            
            # Success rate compliance
            successful_executions = executions.filter(status='completed').count()
            actual_success_rate = (successful_executions / total_executions) * 100
            success_rate_compliant = actual_success_rate >= min_success_rate
            
            # Duration compliance
            duration_compliant_count = 0
            for execution in executions.filter(status='completed'):
                if execution.completed_at and execution.started_at:
                    duration = (execution.completed_at - execution.started_at).total_seconds()
                    if duration <= max_duration:
                        duration_compliant_count += 1
            
            duration_compliance_rate = (duration_compliant_count / successful_executions * 100) if successful_executions > 0 else 0
            duration_compliant = duration_compliance_rate >= min_success_rate
            
            # Overall compliance
            overall_compliant = success_rate_compliant and duration_compliant
            overall_compliance_score = min(actual_success_rate, duration_compliance_rate)
            
            # Update Prometheus metrics
            self.metrics.sla_compliance.labels(
                tenant_id=tenant_id,
                sla_type='success_rate'
            ).set(actual_success_rate)
            
            self.metrics.sla_compliance.labels(
                tenant_id=tenant_id,
                sla_type='duration'
            ).set(duration_compliance_rate)
            
            return {
                'overall_compliant': overall_compliant,
                'overall_compliance_score': round(overall_compliance_score, 2),
                'success_rate': {
                    'actual': round(actual_success_rate, 2),
                    'required': min_success_rate,
                    'compliant': success_rate_compliant
                },
                'duration': {
                    'compliance_rate': round(duration_compliance_rate, 2),
                    'max_allowed_seconds': max_duration,
                    'compliant': duration_compliant
                },
                'time_window_hours': time_window_hours,
                'total_executions': total_executions
            }
            
        except Exception as e:
            logger.error(f"Error calculating SLA compliance: {e}")
            return {'error': str(e)}

# Global analytics engine instance
analytics_engine = AnalyticsEngine()