import json
import boto3
import urllib.parse
import requests
from requests_aws4auth import AWS4Auth

# ================== CONFIG ==================
OPENSEARCH_HOST = "search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com"
INDEX_NAME = "jobs"
REGION = "ap-southeast-2"
SERVICE = "es"

RESUME_BUCKET = "resume-matching-533267343789"
RESUME_PREFIX = "resumes/"
# ============================================

# ---------- AWS clients ----------
session = boto3.Session()
credentials = session.get_credentials()

awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    SERVICE,
    session_token=credentials.token
)

s3 = boto3.client("s3")

# ---------- Helpers ----------
def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }

# ---------- Lambda ----------
def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    # =====================================================
    # 1) HTTP API
    # =====================================================
    if "requestContext" in event:
        path = event.get("rawPath", "")
        method = event["requestContext"]["http"]["method"]

        # ---- health ----
        if path == "/api/health":
            return response(200, {"status": "ok"})

        # ---- list jobs from OpenSearch ----
        if path == "/api/jobs" and method == "GET":
            url = f"https://{OPENSEARCH_HOST}/{INDEX_NAME}/_search"
            query = {
                "size": 1000,
                "query": {"match_all": {}}
            }

            res = requests.get(
                url,
                auth=awsauth,
                headers={"Content-Type": "application/json"},
                data=json.dumps(query)
            )

            if res.status_code != 200:
                return response(500, {"error": res.text})

            hits = res.json()["hits"]["hits"]
            jobs = [h["_source"] for h in hits]

            return response(200, jobs)

        # ---- list resumes from S3 ----
        if path == "/api/resumes" and method == "GET":
            resp = s3.list_objects_v2(
                Bucket=RESUME_BUCKET,
                Prefix=RESUME_PREFIX
            )

            files = []
            for obj in resp.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat()
                })

            return response(200, files)

        return response(404, {"error": "Not found"})

    # =====================================================
    # 2) S3 EVENT → index jobs
    # =====================================================
    if "Records" in event:
        for record in event["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

            obj = s3.get_object(Bucket=bucket, Key=key)
            jobs = json.loads(obj["Body"].read().decode("utf-8"))

            for job in jobs:
                doc_id = job.get("id")
                if not doc_id:
                    continue

                # ห้ามมี _id ใน body
                job.pop("_id", None)

                url = f"https://{OPENSEARCH_HOST}/{INDEX_NAME}/_doc/{doc_id}"

                res = requests.put(
                    url,
                    auth=awsauth,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(job)
                )

                if res.status_code not in (200, 201):
                    print("ERROR:", res.text)
                else:
                    print(f"Indexed job {doc_id}")

        return response(200, {"message": "Indexed jobs successfully"})

    # =====================================================
    return response(400, {"error": "Unknown event"})
