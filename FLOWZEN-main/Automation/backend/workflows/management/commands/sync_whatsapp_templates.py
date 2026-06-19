import requests
from django.core.management.base import BaseCommand
from workflows.models import Credential, WhatsAppTemplate
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync WhatsApp Templates from Meta for all configured credentials'

    def handle(self, *args, **options):
        credentials = Credential.objects.filter(type='meta_whatsapp')
        self.stdout.write(f"Found {credentials.count()} WhatsApp credentials to sync.")

        for cred in credentials:
            self.sync_credential_templates(cred)

    def sync_credential_templates(self, credential):
        data = credential.encrypted_data
        phone_number_id = data.get('phone_number_id')
        access_token = data.get('access_token')
        
        # We need the WABA ID (WhatsApp Business Account ID) to fetch templates.
        # Often phone_number_id is distinct from WABA ID.
        # Strategy: From phone_number_id, fetch account info to get WABA ID?
        # Endpoint: GET /v19.0/{phone_number_id}?fields=start_time,status,business_profile,id
        # Actually, templates are owned by the *WABA*.
        # Start by hitting: GET /v19.0/{phone_number_id}/whatsapp_business_profile? Oops no.
        # Better: GET /v19.0/{phone_number_id} -> returns "metadata" maybe?
        
        # Meta Graph API: GET /v19.0/{whatsapp-business-account-id}/message_templates
        # We might not have WABA stored.
        # Attempt to derive WABA ID from phone number ID via:
        # GET /{phone_number_id}?fields=id,name,platform_type
        # Doesn't explicitly give WABA?
        # Actually, best practice is to store WABA ID in Credential.
        # Current Schema: phone_number_id, access_token, app_secret, webhook_verify_token.
        # Fallback: We can try to fetch templates directly if endpoint allows `me` or similar? 
        # No, templates are account level.
        
        # Workaround: Use the access token to get "me" accounts?
        # GET /me/accounts -> find the WABA?
        
        # Strict approach: Ask user to provide WABA ID. 
        # But we can't change schema in this phase easily (user said "No architecture rewrite").
        # Let's try to fetch WABA from the phone number endpoint.
        # GET /{phone-number-id}?fields=id,name,verification_status,business_management_manager
        
        # Actually, official docs say you list templates from WABA.
        # Let's try to find WABA ID from the Access Token debug endpoint?
        # GET /debug_token?input_token={access_token}
        
        # Simpler: Make a call to /{phone_number_id} using the token.
        # Often the response includes the WABA ID in `business_account`.
        # Or `GET /v19.0/{phone_number_id}?fields=id,name,whatsapp_business_account`? (Hypothetical)
        
        # Let's try fetching WABA ID first.
        waba_id = self.fetch_waba_id(phone_number_id, access_token)
        if not waba_id:
            self.stdout.write(self.style.ERROR(f"Could not resolve WABA ID for {credential.name}"))
            return

        # Fetch Templates
        url = f"https://graph.facebook.com/v19.0/{waba_id}/message_templates"
        self.fetch_and_save_pages(url, access_token, credential)
            
    def fetch_waba_id(self, phone_id, token):
        # Allow user to manually put WABA ID in encrypted_data if code fails
        # But let's try to fetch it.
        # Endpoint: GET /{phone-number-id}?fields=billing_account_ids
        url = f"https://graph.facebook.com/v19.0/{phone_id}"
        # We try to get business account info.
        # Actually, from v17+, you can look up.
        # Let's try generic query.
        try:
            res = requests.get(url, params={"access_token": token, "fields": "id,name"}, timeout=10)
            if res.status_code == 200:
                # This returns Phone Number info. Not WABA.
                pass
            
            # Try fetching the Phone Number with WABA field?
            # 'v19.0/{phone-id}?fields=name,whatsapp_business_account' ??
            res = requests.get(url, params={"access_token": token, "fields": "id,name,whatsapp_business_account"}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data.get('whatsapp_business_account', {}).get('id')
                
        except Exception as e:
            logger.error(f"Error fetching WABA: {e}")
            
        return None

    def fetch_and_save_pages(self, url, token, credential):
        while url:
            try:
                res = requests.get(url, params={"access_token": token}, timeout=15)
                res.raise_for_status()
                data = res.json()
                
                templates = data.get('data', [])
                for tpl in templates:
                    self.save_template(credential, tpl)
                    
                # Pagination
                url = data.get('paging', {}).get('next')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error fetching templates: {e}"))
                url = None

    def save_template(self, credential, tpl_data):
        name = tpl_data.get('name')
        lang = tpl_data.get('language')
        status = tpl_data.get('status') # APPROVED, REJECTED, PENDING
        category = tpl_data.get('category')
        
        # Map Status to our model (pending, approved, rejected)
        # Meta returns: APPROVED, REJECTED, PENDING, PAUSED, DISABLED, APPEAL_REQUESTED...
        status_map = {
            'APPROVED': 'approved',
            'REJECTED': 'rejected',
            'PENDING': 'pending'
        }
        db_status = status_map.get(status, 'pending') # Default to pending for unknown
        
        WhatsAppTemplate.objects.update_or_create(
            credential=credential,
            name=name,
            language=lang,
            defaults={
                'status': db_status,
                'category': category,
                'content_schema': tpl_data, # Store full structure
                # 'rejection_reason': tpl_data.get('rejected_reason') # if available
            }
        )
        self.stdout.write(f"Synced {name} ({lang}) -> {db_status}")
