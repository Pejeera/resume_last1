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
        if (path == "/api/jobs" or path == "/api/jobs/list") and method == "GET":
            try:
                url = f"https://{OPENSEARCH_HOST}/{INDEX_NAME}/_search"
                query = {
                    "size": 1000,
                    "query": {"match_all": {}}
                }

                res = requests.get(
                    url,
                    auth=awsauth,
                    headers={"Content-Type": "application/json"},
                    json=query,
                    timeout=10
                )

                if res.status_code != 200:
                    print(f"OpenSearch error: {res.status_code} - {res.text}")
                    return response(500, {"error": f"OpenSearch error: {res.text}", "jobs": []})

                hits = res.json().get("hits", {}).get("hits", [])
                jobs = [h.get("_source", {}) for h in hits]

                return response(200, {"jobs": jobs})
            except Exception as e:
                print(f"Error fetching jobs: {str(e)}")
                return response(500, {"error": str(e), "jobs": []})

        # ---- list resumes from S3 ----
        if (path == "/api/resumes" or path == "/api/resumes/list") and method == "GET":
            try:
                # Only list files in Candidate folder
                candidate_prefix = f"{RESUME_PREFIX}Candidate/"
                resp = s3.list_objects_v2(
                    Bucket=RESUME_BUCKET,
                    Prefix=candidate_prefix
                )

                files = []
                for obj in resp.get("Contents", []):
                    key = obj["Key"]
                    # Skip directories (keys ending with /)
                    if key.endswith("/"):
                        continue
                    
                    # Only include files in Candidate folder
                    if not key.startswith(candidate_prefix):
                        continue
                    
                    # Extract filename from key (remove resumes/Candidate/ prefix)
                    filename = key.replace(candidate_prefix, "")
                    
                    files.append({
                        "key": key,
                        "filename": filename,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat()
                    })

                return response(200, {"resumes": files})
            except Exception as e:
                print(f"Error fetching resumes: {str(e)}")
                return response(500, {"error": str(e), "resumes": []})

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
