import os
import json
import logging
import urllib.request
import urllib.error

import azure.functions as func

# ── Where information requests (contact-info.html) land ──────────────────────────────────────────────────────────
# Defaults point at the rebuilt Airtable base. To change them WITHOUT editing code, set the
# application settings CONTACT_BASE_ID / CONTACT_TABLE_ID (Azure portal > Environment variables).
BASE_ID  = os.environ.get("CONTACT_BASE_ID",  "appG9PIjoFYdwW3u1")
TABLE_ID = os.environ.get("CONTACT_TABLE_ID", "tblRWzcCd3rD2euAh")
AIRTABLE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"

# The internal operations base. By design the public forms never touch it: submissions stay in their own
# separate base, and nothing here copies or syncs them across. If a setting ever points this function at
# the ops base, it refuses to run rather than write there. (The real safeguard is the token: give
# AIRTABLE_TOKEN access to the public base ONLY.)
OPS_BASE_ID = "app6C2KGLGqPjZ59B"

# Only these fields are accepted from the public form. This endpoint is open to anyone, so it must
# never pass along a field the page doesn't send. The names must match the Airtable column
# names EXACTLY (capitals and punctuation included).
ALLOWED_FIELDS = {
    "Name",
    "Email",
    "Phone Number",
    "Company",
    "Address for work to be completed",
    "Urgent Need",
    "Notes (Any known details to allow us to better assist you)",
}

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _json(body, status):
    return func.HttpResponse(
        json.dumps(body),
        status_code=status,
        mimetype="application/json",
        headers=CORS_HEADERS,
    )


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=CORS_HEADERS)

    if BASE_ID == OPS_BASE_ID:
        logging.error("Refusing to run: this function is pointed at the internal ops base.")
        return _json({"error": "Server misconfiguration."}, 500)

    # Set this under: Static Web App > Environment variables. Needs an Airtable personal access
    # token with the data.records:write scope and access to the base above.
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        logging.error("AIRTABLE_TOKEN application setting is not configured.")
        return _json({"error": "Server misconfiguration."}, 500)

    try:
        body = req.get_json()
    except ValueError:
        return _json({"error": "Invalid JSON body."}, 400)

    fields = body.get("fields") if isinstance(body, dict) else None
    if not fields or not isinstance(fields, dict):
        return _json({"error": "Missing or invalid 'fields' object."}, 400)

    unexpected = sorted(k for k in fields if k not in ALLOWED_FIELDS)
    if unexpected:
        logging.warning(f"Rejected unexpected field(s): {unexpected}")
        return _json({"error": "Unexpected field(s): " + ", ".join(unexpected)}, 400)

    payload = json.dumps({"fields": fields}).encode("utf-8")

    request = urllib.request.Request(
        AIRTABLE_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            resp_body = resp.read()
            return func.HttpResponse(
                resp_body,
                status_code=resp.status,
                mimetype="application/json",
                headers=CORS_HEADERS,
            )
    except urllib.error.HTTPError as e:
        error_body = e.read()
        logging.error(f"Airtable error {e.code}: {error_body}")
        return func.HttpResponse(
            error_body,
            status_code=e.code,
            mimetype="application/json",
            headers=CORS_HEADERS,
        )
    except Exception as e:
        logging.error(f"Unexpected error submitting to Airtable: {e}")
        return _json({"error": "Failed to submit request."}, 502)
