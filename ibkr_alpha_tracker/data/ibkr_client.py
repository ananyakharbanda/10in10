import time
import xml.etree.ElementTree as ET
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

class FlexError(Exception):
    """IBKR returned a failure status."""


def parse_reference_code(xml_text):
    """Pull the reference code out of a SendRequest response.
    Raises FlexError if IBKR reported a failure."""
    root = ET.fromstring(xml_text)

    status = root.findtext("Status")
    if status != "Success":
        code = root.findtext("ErrorCode")
        message = root.findtext("ErrorMessage")
        raise FlexError(f"SendRequest failed [{code}]: {message}")

    return root.findtext("ReferenceCode")

