import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.getcwd())

# Mock google libraries before import
sys.modules['googleapiclient'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google.oauth2.credentials'] = MagicMock()
sys.modules['google.auth'] = MagicMock()
sys.modules['google.auth.transport'] = MagicMock()
sys.modules['google.auth.transport.requests'] = MagicMock()
sys.modules['discord'] = MagicMock()

# Mock Django settings
from django.conf import settings
if not settings.configured:
    settings.configure(
        CELERY_BROKER_URL='redis://localhost:6379/0',
        INSTALLED_APPS=['workflows'],
        # Mock other needed settings
    )
import django
# No django.setup() needed if we just check module imports that don't hit DB models at top level

try:
    # We must mock 'workflows.expression_evaluator' if it imports django models
    # But let's try importing actions directly.
    # actions.py imports ExpressionEvaluator
    
    from workflows import actions
    print("✅ Module 'workflows.actions' imported successfully.")
    
    registry = actions.ACTION_REGISTRY
    
    expected_nodes = ['google_sheets', 'google_drive', 'youtube', 'discord', 'memory']
    missing = [n for n in expected_nodes if n not in registry]
    
    if missing:
        print(f"❌ Missing nodes in registry: {missing}")
        sys.exit(1)
        
    print("✅ All new nodes found in ACTION_REGISTRY:")
    for n in expected_nodes:
        print(f"   - {n}: {registry[n].__name__}")

except Exception as e:
    print(f"❌ Verification Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
