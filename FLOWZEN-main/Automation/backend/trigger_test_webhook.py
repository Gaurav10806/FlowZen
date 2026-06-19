
import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL = "http://localhost:8000/api/webhooks/whatsapp/"
PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123456789",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "1234567890",
                            "phone_number_id": "915877344952476"
                        },
                        "contacts": [
                            {
                                "profile": {
                                    "name": "Test User"
                                },
                                "wa_id": "1234567890"
                            }
                        ],
                        "messages": [
                            {
                                "from": "1234567890",
                                "id": "wamid.test",
                                "timestamp": "1678888888",
                                "text": {
                                    "body": "Hello World"
                                },
                                "type": "text"
                            }
                        ]
                    },
                    "field": "messages"
                }
            ]
        }
    ]
}

try:
    print(f"Sending POST to {URL}")
    response = requests.post(URL, json=PAYLOAD)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
