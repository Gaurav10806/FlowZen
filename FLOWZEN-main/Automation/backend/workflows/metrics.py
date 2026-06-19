"""
Prometheus metrics exporter for workflow automation platform.
"""
from prometheus_client import Counter, Histogram, Gauge
from django.core.cache import cache

# Execution metrics
workflow_executions_total = Counter(
    'workflow_executions_total',
    'Total number of workflow executions',
    ['status', 'workflow_id', 'organization_id']
)

workflow_execution_duration = Histogram(
    'workflow_execution_duration_seconds',
    'Workflow execution duration in seconds',
    ['workflow_id', 'organization_id']
)

node_executions_total = Counter(
    'node_executions_total',
    'Total number of node executions',
    ['status', 'action_type', 'workflow_id']
)

node_execution_duration = Histogram(
    'node_execution_duration_seconds',
    'Node execution duration in seconds',
    ['action_type', 'workflow_id']
)

# Usage metrics
active_workflows = Gauge(
    'active_workflows',
    'Number of active workflows',
    ['organization_id']
)

active_executions = Gauge(
    'active_executions',
    'Number of currently running executions',
    ['organization_id']
)

webhook_requests_total = Counter(
    'webhook_requests_total',
    'Total number of webhook requests',
    ['workflow_id', 'status']
)

# Error metrics
workflow_errors_total = Counter(
    'workflow_errors_total',
    'Total number of workflow errors',
    ['error_type', 'workflow_id']
)

# Billing metrics
subscription_count = Gauge(
    'subscriptions_total',
    'Number of active subscriptions',
    ['plan_name', 'status']
)

usage_limit_usage = Gauge(
    'usage_limit_usage',
    'Current usage vs limit',
    ['organization_id', 'limit_type']
)


def record_workflow_execution(workflow_id, organization_id, status, duration=None):
    """Record workflow execution metric."""
    workflow_executions_total.labels(
        status=status,
        workflow_id=str(workflow_id),
        organization_id=str(organization_id) if organization_id else 'none'
    ).inc()
    
    if duration is not None:
        workflow_execution_duration.labels(
            workflow_id=str(workflow_id),
            organization_id=str(organization_id) if organization_id else 'none'
        ).observe(duration)


def record_node_execution(node_id, action_type, workflow_id, status, duration=None):
    """Record node execution metric."""
    node_executions_total.labels(
        status=status,
        action_type=action_type,
        workflow_id=str(workflow_id)
    ).inc()
    
    if duration is not None:
        node_execution_duration.labels(
            action_type=action_type,
            workflow_id=str(workflow_id)
        ).observe(duration)


def record_webhook_request(workflow_id, status):
    """Record webhook request metric."""
    webhook_requests_total.labels(
        workflow_id=str(workflow_id),
        status=status
    ).inc()


def record_workflow_error(error_type, workflow_id):
    """Record workflow error metric."""
    workflow_errors_total.labels(
        error_type=error_type,
        workflow_id=str(workflow_id)
    ).inc()


def update_active_workflows(organization_id, count):
    """Update active workflows gauge."""
    active_workflows.labels(
        organization_id=str(organization_id) if organization_id else 'none'
    ).set(count)


def update_active_executions(organization_id, count):
    """Update active executions gauge."""
    active_executions.labels(
        organization_id=str(organization_id) if organization_id else 'none'
    ).set(count)


def update_subscription_metrics():
    """Update subscription metrics."""
    from .models import Subscription
    
    for plan_name in ['free', 'pro', 'team', 'enterprise']:
        for status in ['active', 'canceled', 'past_due']:
            count = Subscription.objects.filter(
                plan__name=plan_name,
                status=status
            ).count()
            subscription_count.labels(
                plan_name=plan_name,
                status=status
            ).set(count)


def update_usage_limit_metrics(organization_id, limit_type, usage, limit):
    """Update usage limit metrics."""
    usage_limit_usage.labels(
        organization_id=str(organization_id),
        limit_type=limit_type
    ).set(usage / limit if limit > 0 else 0)


