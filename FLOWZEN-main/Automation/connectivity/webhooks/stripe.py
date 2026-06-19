"""
Stripe webhook handlers for subscription management.
"""
import json
import stripe
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from .models import Organization, Subscription, Invoice, SubscriptionPlan

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')


@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook events."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        return HttpResponse(status=400)
    
    # Handle event
    event_type = event['type']
    data = event['data']['object']
    
    try:
        if event_type == 'customer.subscription.created':
            handle_subscription_created(data)
        elif event_type == 'customer.subscription.updated':
            handle_subscription_updated(data)
        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(data)
        elif event_type == 'invoice.paid':
            handle_invoice_paid(data)
        elif event_type == 'invoice.payment_failed':
            handle_invoice_payment_failed(data)
        elif event_type == 'customer.subscription.trial_will_end':
            handle_trial_will_end(data)
        else:
            logger.info(f"Unhandled event type: {event_type}")
        
        return HttpResponse(status=200)
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        return HttpResponse(status=500)


def handle_subscription_created(data):
    """Handle subscription.created event."""
    stripe_subscription_id = data['id']
    stripe_customer_id = data['customer']
    
    # Find organization by customer ID
    try:
        subscription = Subscription.objects.get(stripe_customer_id=stripe_customer_id)
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found for customer: {stripe_customer_id}")
        return
    
    # Update subscription
    subscription.stripe_subscription_id = stripe_subscription_id
    subscription.status = data['status']
    from datetime import datetime
    subscription.current_period_start = datetime.fromtimestamp(
        data['current_period_start'], tz=timezone.utc
    )
    subscription.current_period_end = datetime.fromtimestamp(
        data['current_period_end'], tz=timezone.utc
    )
    subscription.save()
    
    # Update usage limits based on plan
    update_usage_limits(subscription.organization, subscription.plan)
    
    logger.info(f"Subscription created: {stripe_subscription_id}")


def handle_subscription_updated(data):
    """Handle subscription.updated event."""
    stripe_subscription_id = data['id']
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found: {stripe_subscription_id}")
        return
    
    # Update subscription
    subscription.status = data['status']
    from datetime import datetime
    subscription.current_period_start = datetime.fromtimestamp(
        data['current_period_start'], tz=timezone.utc
    )
    subscription.current_period_end = datetime.fromtimestamp(
        data['current_period_end'], tz=timezone.utc
    )
    subscription.cancel_at_period_end = data.get('cancel_at_period_end', False)
    subscription.save()
    
    # Update usage limits
    update_usage_limits(subscription.organization, subscription.plan)
    
    logger.info(f"Subscription updated: {stripe_subscription_id}")


def handle_subscription_deleted(data):
    """Handle subscription.deleted event."""
    stripe_subscription_id = data['id']
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found: {stripe_subscription_id}")
        return
    
    # Cancel subscription
    subscription.status = 'canceled'
    subscription.save()
    
    # Downgrade to free plan
    free_plan = SubscriptionPlan.objects.get(name='free')
    subscription.plan = free_plan
    subscription.save()
    
    # Update usage limits
    update_usage_limits(subscription.organization, free_plan)
    
    logger.info(f"Subscription deleted: {stripe_subscription_id}")


def handle_invoice_paid(data):
    """Handle invoice.paid event."""
    stripe_invoice_id = data['id']
    stripe_customer_id = data['customer']
    
    # Find organization
    try:
        subscription = Subscription.objects.get(stripe_customer_id=stripe_customer_id)
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found for customer: {stripe_customer_id}")
        return
    
    # Create or update invoice
    invoice, created = Invoice.objects.get_or_create(
        stripe_invoice_id=stripe_invoice_id,
        defaults={
            'organization': subscription.organization,
            'subscription': subscription,
            'amount_due': data['amount_due'] / 100,  # Convert from cents
            'amount_paid': data['amount_paid'] / 100,
            'currency': data['currency'],
            'status': 'paid',
            'paid_at': timezone.now(),
            'stripe_pdf_url': data.get('invoice_pdf'),
        }
    )
    
    if not created:
        invoice.status = 'paid'
        invoice.amount_paid = data['amount_paid'] / 100
        invoice.paid_at = timezone.now()
        invoice.save()
    
    logger.info(f"Invoice paid: {stripe_invoice_id}")


def handle_invoice_payment_failed(data):
    """Handle invoice.payment_failed event."""
    stripe_invoice_id = data['id']
    stripe_customer_id = data['customer']
    
    # Find organization
    try:
        subscription = Subscription.objects.get(stripe_customer_id=stripe_customer_id)
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found for customer: {stripe_customer_id}")
        return
    
    # Update invoice
    try:
        invoice = Invoice.objects.get(stripe_invoice_id=stripe_invoice_id)
        invoice.status = 'open'
        invoice.save()
    except Invoice.DoesNotExist:
        # Create invoice if doesn't exist
        Invoice.objects.create(
            organization=subscription.organization,
            subscription=subscription,
            stripe_invoice_id=stripe_invoice_id,
            amount_due=data['amount_due'] / 100,
            currency=data['currency'],
            status='open',
        )
    
    # Update subscription status
    subscription.status = 'past_due'
    subscription.save()
    
    logger.warning(f"Invoice payment failed: {stripe_invoice_id}")


def handle_trial_will_end(data):
    """Handle trial_will_end event."""
    stripe_subscription_id = data['id']
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
    except Subscription.DoesNotExist:
        return
    
    # Send notification (implement notification system)
    logger.info(f"Trial will end for subscription: {stripe_subscription_id}")


def update_usage_limits(organization, plan):
    """Update organization usage limits based on subscription plan."""
    from .models import UsageLimit
    
    usage_limit, _ = UsageLimit.objects.get_or_create(organization=organization)
    
    usage_limit.max_executions_per_month = plan.max_executions_per_month
    usage_limit.max_webhook_hits_per_day = plan.max_webhook_hits_per_day
    usage_limit.max_active_workflows = plan.max_active_workflows
    usage_limit.max_active_credentials = plan.max_active_credentials
    usage_limit.max_team_members = plan.max_team_members
    usage_limit.save()

