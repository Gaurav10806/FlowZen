from rest_framework.throttling import SimpleRateThrottle
from .models import Workflow


class TenantExecutionRateThrottle(SimpleRateThrottle):
    scope = "tenant_execution"

    def get_cache_key(self, request, view):
        try:
            workflow_id = request.data.get("workflow")
            if not workflow_id:
                return None
            workflow = Workflow.objects.filter(id=workflow_id).only("tenant_id", "organization_id").first()
            if not workflow:
                return None
            tenant_part = str(workflow.tenant_id or "none")
            org_part = str(workflow.organization_id or "none")
            ident = f"{tenant_part}:{org_part}"
            return self.cache_format % {"scope": self.scope, "ident": ident}
        except Exception:
            return None


class TenantWebhookRateThrottle(SimpleRateThrottle):
    scope = "tenant_webhook"

    def get_ident(self, request):
        return super().get_ident(request)

    def get_cache_key(self, request, view):
        try:
            workflow_id = getattr(view, "kwargs", {}).get("workflow_id")
            if not workflow_id and hasattr(request, "parser_context"):
                workflow_id = request.parser_context.get("kwargs", {}).get("workflow_id")
            if not workflow_id:
                return None
            workflow = Workflow.objects.filter(id=workflow_id).only("tenant_id", "organization_id").first()
            if not workflow:
                return None
            tenant_part = str(workflow.tenant_id or "none")
            org_part = str(workflow.organization_id or "none")
            ident = f"{tenant_part}:{org_part}"
            return self.cache_format % {"scope": self.scope, "ident": ident}
        except Exception:
            return None
