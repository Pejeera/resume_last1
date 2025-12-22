import json
import boto3
import urllib.parse
import sys
import os

# Add python/ directory to sys.path so Lambda can find dependencies
python_path = os.path.join(os.path.dirname(__file__), 'python')
if python_path not in sys.path:
    sys.path.insert(0, python_path)

import requests
from requests_aws4auth import AWS4Auth

# ---------- OpenSearch config ----------
OPENSEARCH_HOST = "search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com"
INDEX_NAME = "jobs"
REGION = "ap-southeast-2"
SERVICE = "es"

# ---------- AWS auth ----------
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

def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        print(f"Reading file s3://{bucket}/{key}")

        # อ่านไฟล์จาก S3
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read().decode("utf-8")
        jobs = json.loads(body)

        # ใส่ข้อมูลเข้า OpenSearch
        for job in jobs:
            doc_id = job.get("id")
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

    return {
        "statusCode": 200,
        "body": "Indexed jobs successfully"
    }
