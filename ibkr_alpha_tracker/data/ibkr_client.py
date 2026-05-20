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

def get_statement(token, reference_code, max_attempts=24, wait_seconds=5):
    """Poll GetStatement until the report is ready. Returns the XML report."""
    for attempt in range(max_attempts):
        resp = requests.get(
            GET_URL,
            params={"t": token, "q": reference_code, "v": "3"},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.text

        # If the report is ready, the body is the actual FlexQueryResponse.
        if body.lstrip().startswith("<FlexQueryResponse"):
            return body

        # Otherwise it's a status envelope - check why.
        root = ET.fromstring(body)
        code = root.findtext("ErrorCode")
        if code == "1019":
            # "Statement generation in progress" - wait and retry.
            time.sleep(wait_seconds)
            continue

        # Any other error is terminal.
        message = root.findtext("ErrorMessage")
        raise FlexError(f"GetStatement failed [{code}]: {message}")

    raise FlexError(f"Report not ready after {max_attempts * wait_seconds}s")

def fetch_flex_report(token, query_id):
    """Run a Flex query end to end. Returns the raw XML report."""
    response = send_request(token, query_id)
    reference_code = parse_reference_code(response)
    return get_statement(token, reference_code)

