import time
import xml.etree.ElementTree as ET
import requests

BASE = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
SEND_URL = f"{BASE}/SendRequest"
GET_URL = f"{BASE}/GetStatement"
HEADERS = {"User-Agent": "ibkr-alpha-tracker/0.1"}


class FlexError(Exception):
    """IBKR returned a failure status."""


def send_request(token, query_id, from_date=None, to_date=None):
    """Trigger report generation. Optional from_date/to_date (yyyymmdd strings)
    override the query's configured period - used to fetch a historical window
    up to 365 days, so we can backfill trades that aged out of the rolling one."""
    params = {"t": token, "q": query_id, "v": "3"}
    if from_date and to_date:
        params["fd"] = from_date
        params["td"] = to_date
    resp = requests.get(SEND_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_reference_code(xml_text):
    root = ET.fromstring(xml_text)
    status = root.findtext("Status")
    if status != "Success":
        code = root.findtext("ErrorCode")
        message = root.findtext("ErrorMessage")
        raise FlexError(f"SendRequest failed [{code}]: {message}")
    return root.findtext("ReferenceCode")


def get_statement(token, reference_code, max_attempts=24, wait_seconds=5):
    for _ in range(max_attempts):
        resp = requests.get(GET_URL, params={"t": token, "q": reference_code, "v": "3"},
                            headers=HEADERS, timeout=30)
        resp.raise_for_status()
        body = resp.text
        if body.lstrip().startswith("<FlexQueryResponse"):
            return body
        root = ET.fromstring(body)
        code = root.findtext("ErrorCode")
        if code == "1019":
            time.sleep(wait_seconds)
            continue
        message = root.findtext("ErrorMessage")
        raise FlexError(f"GetStatement failed [{code}]: {message}")
    raise FlexError(f"Report not ready after {max_attempts * wait_seconds}s")


def fetch_flex_report(token, query_id, from_date=None, to_date=None):
    """Run a Flex query end to end. Pass from_date/to_date (yyyymmdd) to fetch
    a specific historical window instead of the query's configured period."""
    response = send_request(token, query_id, from_date=from_date, to_date=to_date)
    reference_code = parse_reference_code(response)
    return get_statement(token, reference_code)
