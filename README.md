# CS528 Homework 3

This repository contains my solution for **CS528 Homework 3**.

The assignment implements two microservices:

1. **Service 1** — a Google Cloud Function that serves files from Cloud Storage over HTTP.
2. **Service 2** — a local Python subscriber that receives forbidden-country requests through Pub/Sub and appends them to a log file in Cloud Storage.

---

## Architecture

```text
Browser / curl / provided http-client
                |
                v
        Service 1: Cloud Function
        - GET /<file>
        - POST {"file":"<file>"}
        - 404 for missing objects
        - 501 for unsupported methods
        - X-country filtering
          |                     |
          | normal request      | forbidden request
          v                     v
   Cloud Storage          Pub/Sub topic
sonal-graph-2026-sps     forbidden-requests
                                |
                                v
                      Service 2 on local laptop
                                |
                                v
                     forbidden_logs/
                     forbidden_requests.log
```

---

## Project Configuration

- **Google Cloud Project:** `directed-fabric-508221-d2`
- **Region:** `us-central1`
- **Cloud Storage Bucket:** `sonal-graph-2026-sps`
- **Test File:** `graph_data/1654.html`
- **Cloud Function:** `file-service`
- **Service Account:** `hw3-microservice@directed-fabric-508221-d2.iam.gserviceaccount.com`
- **Pub/Sub Topic:** `forbidden-requests`
- **Pub/Sub Subscription:** `forbidden-requests-sub`
- **Forbidden Request Log:** `gs://sonal-graph-2026-sps/forbidden_logs/forbidden_requests.log`

---

## Repository Structure

```text
CS528-HW3/
├── service1/
│   ├── main.py
│   └── requirements.txt
├── service2/
│   ├── subscriber.py
│   └── requirements.txt
├── .gitignore
└── README.md
```

---

## Service 1

Service 1 is an HTTP-triggered Google Cloud Function.

It supports:

- HTTP GET
- HTTP POST
- HTTP 404 for nonexistent files
- HTTP 501 for unsupported methods
- Cloud Logging for erroneous requests
- `X-country` header filtering
- Pub/Sub publishing for forbidden-country requests

---

### GET Request

For GET requests, the requested object is provided in the URL path.

```bash
curl -s -D - \
  "$FUNCTION_URL/graph_data/1654.html" \
  -o /dev/null
```

Expected response:

```text
HTTP/2 200
```

---

### POST Request

For POST requests, the requested file is provided in the JSON payload.

```bash
curl -s -D - \
  -X POST \
  "$FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -d '{"file":"graph_data/1654.html"}' \
  -o /dev/null
```

Expected response:

```text
HTTP/2 200
```

---

### 404 Handling

Requests for nonexistent objects return HTTP 404.

```bash
curl -i \
  "$FUNCTION_URL/graph_data/does-not-exist.html"
```

Expected response:

```text
HTTP/2 404
File not found: graph_data/does-not-exist.html
```

The error is also written to Cloud Logging using structured logging and a simple print statement.

---

### 501 Handling

Unsupported HTTP methods such as PUT return HTTP 501.

```bash
curl -i \
  -X PUT \
  "$FUNCTION_URL/graph_data/1654.html"
```

Expected response:

```text
HTTP/2 501
HTTP method PUT is not implemented
```

The error is also logged to Cloud Logging.

---

## Country Restriction

The Cloud Function reads the `X-country` request header.

The following countries are treated as forbidden for this assignment:

- North Korea
- Iran
- Cuba
- Myanmar
- Iraq
- Libya
- Sudan
- Zimbabwe
- Syria

Example:

```bash
curl -i \
  "$FUNCTION_URL/graph_data/1654.html" \
  -H "X-country: Iran"
```

Expected response:

```text
HTTP/2 400
Permission denied for requests from Iran
```

When a forbidden request is detected:

1. The file is not returned.
2. HTTP 400 is returned.
3. A JSON event is published to the `forbidden-requests` Pub/Sub topic.

---

## Service 2

Service 2 runs locally on the laptop.

It subscribes to:

```text
forbidden-requests-sub
```

When a message is received, the service:

1. Decodes the JSON message.
2. Prints the forbidden request to stdout.
3. Appends the request to:

```text
gs://sonal-graph-2026-sps/forbidden_logs/forbidden_requests.log
```

4. Acknowledges the Pub/Sub message.

Example output:

```text
FORBIDDEN REQUEST: country=Iran, method=GET, file=graph_data/1654.html
```

---

## Local Authentication

Service 2 uses the same service account as Service 1.

The local program explicitly loads a service-account JSON credential instead of using:

```text
gcloud auth application-default login
```

The service-account key is stored outside the repository.

By default, Service 2 expects the key at:

```text
~/hw3-service-account.json
```

A custom path can also be configured:

```bash
export HW3_SERVICE_ACCOUNT_KEY="/absolute/path/to/hw3-service-account.json"
```

The service-account key must never be committed to GitHub.

---

## Cloud Function Deployment

Set the required environment variables:

```bash
PROJECT_ID="directed-fabric-508221-d2"
BUCKET_NAME="sonal-graph-2026-sps"
REGION="us-central1"
TOPIC="forbidden-requests"
SA_EMAIL="hw3-microservice@directed-fabric-508221-d2.iam.gserviceaccount.com"
```

Deploy Service 1:

```bash
gcloud functions deploy file-service \
  --gen2 \
  --runtime=python312 \
  --region=$REGION \
  --source=service1 \
  --entry-point=file_service \
  --trigger-http \
  --allow-unauthenticated \
  --service-account=$SA_EMAIL \
  --set-env-vars=BUCKET_NAME=$BUCKET_NAME,PROJECT_ID=$PROJECT_ID,TOPIC_ID=$TOPIC
```

Retrieve the deployed URL:

```bash
FUNCTION_URL=$(gcloud functions describe file-service \
  --gen2 \
  --region=us-central1 \
  --format="value(serviceConfig.uri)")
```

Verify:

```bash
echo $FUNCTION_URL
```

Deployed endpoint used during testing:

```text
https://file-service-buj4luyjvq-uc.a.run.app
```

---

## Service 2 Setup

Go to the Service 2 directory:

```bash
cd service2
```

Create a virtual environment:

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the subscriber:

```bash
python subscriber.py
```

Expected startup output:

```text
Service 2 is running...
Listening on projects/directed-fabric-508221-d2/subscriptions/forbidden-requests-sub
```

---

## Cloud Logging

Structured logs are generated for:

- missing files
- unsupported HTTP methods

Example 404 structured log:

```text
ERROR_TYPE: file_not_found
FILENAME: graph_data/does-not-exist.html
METHOD: GET
MESSAGE: File not found: graph_data/does-not-exist.html
```

Example 501 structured log:

```text
ERROR_TYPE: method_not_implemented
METHOD: PUT
MESSAGE: HTTP method PUT is not implemented
```

---

## 100-Request HTTP Client Test

The instructor-provided macOS `http-client` executable was used to send 100 GET requests.

```bash
time ./http-client \
  -d file-service-buj4luyjvq-uc.a.run.app \
  -b none \
  -w graph_data \
  -n 100 \
  -i 11999 \
  -p 443 \
  -s \
  -t 10 \
  > /dev/null
```

The test completed successfully.

Measured total time:

```text
1:08.88
```

---

## Security Notes

The following files should never be committed:

```text
hw3-service-account.json
.env
```

The repository `.gitignore` excludes service-account JSON files, virtual environments, and local environment files.

Service-account keys are long-lived credentials, so in a production environment a short-lived mechanism such as service-account impersonation or workload identity would be preferable.

---

## Technologies Used

- Python
- Google Cloud Functions
- Google Cloud Storage
- Google Cloud Pub/Sub
- Google Cloud Logging
- Google IAM
- Flask / Functions Framework
- curl
- Chrome DevTools
- instructor-provided `http-client`

---

## Repository

https://github.com/sonalps-oss/CS528-HW3
