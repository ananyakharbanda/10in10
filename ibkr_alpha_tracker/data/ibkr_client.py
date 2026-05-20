import time
import requests

# IBKR Flex Web Service v3 endpoints
BASE = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
SEND_URL = f"{BASE}/SendRequest"
GET_URL = f"{BASE}/GetStatement"

# IBKR rejects requests with no User-Agent header, so we set one.
HEADERS = {"User-Agent": "ibkr-alpha-tracker/0.1"}

def send_request(token, query_id):
    """Trigger report generation. Returns the reference code."""
    resp = requests.get(
        SEND_URL,
        params={"t": token, "q": query_id, "v": "3"},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text

if __name__ == "__main__":
    token = "PASTE_YOUR_TOKEN"
    query_id = "PASTE_YOUR_TRADES_QUERY_ID"
    print(send_request(token, query_id))
