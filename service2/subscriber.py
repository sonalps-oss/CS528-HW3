import json
import os

from google.cloud import pubsub_v1
from google.cloud import storage
from google.oauth2 import service_account


PROJECT_ID = "directed-fabric-508221-d2"
SUBSCRIPTION_ID = "forbidden-requests-sub"
BUCKET_NAME = "sonal-graph-2026-sps"

# Keep the service-account key outside the Git repository.
# You can override this path with:
# export HW3_SERVICE_ACCOUNT_KEY="/path/to/hw3-service-account.json"
KEY_FILE = os.environ.get(
    "HW3_SERVICE_ACCOUNT_KEY",
    os.path.expanduser("~/hw3-service-account.json"),
)

LOG_OBJECT = "forbidden_logs/forbidden_requests.log"


credentials = service_account.Credentials.from_service_account_file(
    KEY_FILE
)

subscriber = pubsub_v1.SubscriberClient(
    credentials=credentials
)

storage_client = storage.Client(
    project=PROJECT_ID,
    credentials=credentials
)

subscription_path = subscriber.subscription_path(
    PROJECT_ID,
    SUBSCRIPTION_ID
)


def append_to_bucket(message_text):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(LOG_OBJECT)

    if blob.exists():
        old_contents = blob.download_as_text()
    else:
        old_contents = ""

    new_contents = old_contents + message_text + "\n"

    blob.upload_from_string(
        new_contents,
        content_type="text/plain",
    )


def callback(message):
    try:
        payload = json.loads(message.data.decode("utf-8"))

        country = payload.get("country")
        filename = payload.get("filename")
        method = payload.get("method")
        timestamp = payload.get("timestamp")

        error_message = (
            f"[{timestamp}] FORBIDDEN REQUEST: "
            f"country={country}, "
            f"method={method}, "
            f"file={filename}"
        )

        # Print to stdout as required
        print(error_message)

        # Append to Cloud Storage log
        append_to_bucket(error_message)

        message.ack()

    except Exception as exc:
        print(f"Failed processing message: {exc}")
        message.nack()


print("Service 2 is running...")
print(f"Listening on {subscription_path}")

streaming_pull_future = subscriber.subscribe(
    subscription_path,
    callback=callback,
)

try:
    streaming_pull_future.result()
except KeyboardInterrupt:
    streaming_pull_future.cancel()
    print("Service 2 stopped.")
