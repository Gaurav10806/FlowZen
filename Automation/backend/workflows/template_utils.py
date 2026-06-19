import os
from django.http import HttpResponse, Http404
from django.conf import settings
from django.shortcuts import render

def serve_frontend_template(template_name, request=None, context=None):
    """
    Helper to serve a static HTML file from frontend/templates using Django's render.
    Supports both local dev (sibling) and Docker (child) directory structures.
    """
    # Use Django's render function to process template tags
    return render(request, template_name, context)
