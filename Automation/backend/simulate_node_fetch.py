import requests
import sys

try:
    print("Testing Node Library API...")
    # Add timestamp to mimic cache bust
    url = "http://localhost:8000/api/nodes/types/?_t=123"
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        sys.exit(1)
        
    data = response.json()
    
    # Simulate JS Logic
    # const nodes = data.node_types || data;
    nodes = data.get("node_types") if isinstance(data, dict) else data
    
    print(f"Data Type: {type(data)}")
    print(f"Nodes Parsed Type: {type(nodes)}")
    
    if isinstance(nodes, list):
        print(f"Nodes Count: {len(nodes)}")
        if len(nodes) > 0:
            print("First Node:", nodes[0].get("type"), nodes[0].get("category"))
            print("SUCCESS: Logic matches expected array format.")
        else:
            print("WARNING: Nodes list is empty.")
    else:
        print("FAIL: Nodes is not a list.")

except Exception as e:
    print(f"Exception: {e}")
