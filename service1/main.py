import json
import logging
import os
from datetime import datetime, timezone

import functions_framework
from flask import Response
from google.cloud import logging as cloud_logging
from google.cloud import pubsub_v1
from google.cloud import storage


BUCKET_NAME = os.environ["BUCKET_NAME"]
PROJECT_ID = os.environ["PROJECT_ID"]
TOPIC_ID = os.environ["TOPIC_ID"]

FORBIDDEN_COUNTRIES = {
    "north korea",
    "iran",
    "cuba",
    "myanmar",
    "iraq",
    "libya",
    "sudan",
    "zimbabwe",
    "syria",
}

storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

logging_client = cloud_logging.Client()
logging_client.setup_logging()


def log_error(error_type, message, **extra):
    data = {
        "error_type": error_type,
        "message": message,
        **extra,
    }

    # Structured Cloud Logging
    logging.error(
        message,
        extra={"json_fields": data},
    )

    # Simple print statement, also required by the assignment
    print(json.dumps(data))


def publish_forbidden(country, filename, method):
    message = {
        "country": country,
        "filename": filename,
        "method": method,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    data = json.dumps(message).encode("utf-8")
    future = publisher.publish(topic_path, data)
    future.result()


def get_file(filename):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)

    if not blob.exists():
        return None

    return blob.download_as_bytes()


@functions_framework.http
def file_service(request):
    # Unsupported methods -> 501
    if request.method not in ("GET", "POST"):
        message = f"HTTP method {request.method} is not implemented"

        log_error(
            "method_not_implemented",
            message,
            method=request.method,
        )

        return Response(message, status=501)

    # Extract filename
    if request.method == "GET":
        filename = request.path.strip("/")
    else:
        payload = request.get_json(silent=True)

        if not payload or "file" not in payload:
            return Response(
                'POST body must contain {"file":"filename"}',
                status=400,
            )

        filename = payload["file"]

    # Check X-country
    country = request.headers.get("X-country", "").strip()

    if country.lower() in FORBIDDEN_COUNTRIES:
        publish_forbidden(
            country=country,
            filename=filename,
            method=request.method,
        )

        message = f"Permission denied for requests from {country}"
        print(message)

        return Response(message, status=400)

    # Validate filename
    if not filename:
        return Response("Filename required", status=400)

    # Fetch object from Cloud Storage
    contents = get_file(filename)

    if contents is None:
        message = f"File not found: {filename}"

        log_error(
            "file_not_found",
            message,
            filename=filename,
            method=request.method,
        )

        return Response(message, status=404)

    # Success -> 200
    return Response(
        contents,
        status=200,
        content_type="application/octet-stream",
    )
