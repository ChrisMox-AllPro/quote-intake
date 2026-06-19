import os
import json
import logging
import urllib.request
import urllib.error

import azure.functions as func

BASE_ID = "appG9fV0TBrT52xKt"
TABLE_ID = "tblJhccuxgVZBNZv1"
AIRTABLE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=CORS_HEADERS)

    token = os.environ.get("AIRTABLE_TOKEN")

    if not token:
        env_keys = sorted(os.environ.keys())
        matching = [k for k in env_keys if "AIRTABLE" in k.upper() or "TOKEN" in k.upper()]
        return func.HttpResponse(
            json.dumps({
                "error": "Token not found",
                "matching_env_keys": matching,
                "total_env_vars": len(env_keys),
                "sample_keys": env_keys[:20]
            }),
            status_code=500,
            mimetype="application/json",
            headers=CORS_HEADERS,
        )

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body."}),
            status_code=400,
            mimetype="application/json",
            headers=CORS_HEADERS,
        )

    fields = body.get("fields")
    if not fields or not isinstance(fields, dict):
        return func.HttpResponse(
            json.dumps({"error": "Missing or invalid 'fields' object."}),
            status_code=400,
            mimetype="application/json",
            headers=CORS_HEADERS,
        )

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
        return func.HttpResponse(
            json.dumps({"error": "Failed to submit quote request."}),
            status_code=502,
            mimetype="application/json",
            headers=CORS_HEADERS,
        )
