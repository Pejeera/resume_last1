import json
import boto3
import urllib.parse
import requests
from requests_aws4auth import AWS4Auth
import io

# ================== CONFIG ==================
OPENSEARCH_HOST = "search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com"
INDEX_NAME = "jobs"
REGION = "ap-southeast-2"
SERVICE = "es"

RESUME_BUCKET = "resume-matching-533267343789"
RESUME_PREFIX = "resumes/"

# Bedrock config
BEDROCK_REGION = "ap-southeast-1"
BEDROCK_EMBEDDING_MODEL = "cohere.embed-multilingual-v3"
BEDROCK_RERANK_MODEL = "us.amazon.nova-lite-v1:0"
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
bedrock_runtime = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

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

        # ---- CORS preflight (OPTIONS) ----
        if method == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization"
                },
                "body": ""
            }

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

        # ---- search jobs by resume (Mode A) ----
        if path == "/api/jobs/search_by_resume" and method == "POST":
            try:
                body = json.loads(event.get("body", "{}"))
                resume_key = body.get("resume_key") or body.get("resume_id")
                
                if not resume_key:
                    return response(400, {"error": "resume_key or resume_id is required"})
                
                # Ensure resume_key includes full path if it's just filename
                if not resume_key.startswith(RESUME_PREFIX):
                    if resume_key.startswith("Candidate/"):
                        resume_key = f"{RESUME_PREFIX}{resume_key}"
                    else:
                        resume_key = f"{RESUME_PREFIX}Candidate/{resume_key}"
                
                print(f"Searching jobs for resume: {resume_key}")
                
                # 1. Get resume from S3
                try:
                    obj = s3.get_object(Bucket=RESUME_BUCKET, Key=resume_key)
                    file_content = obj["Body"].read()
                    file_name = resume_key.split("/")[-1]
                except Exception as e:
                    print(f"Error fetching resume from S3: {str(e)}")
                    return response(404, {"error": f"Resume not found in S3: {resume_key}"})
                
                # 2. Extract text (simple version - for PDF only)
                resume_text = ""
                try:
                    if file_name.lower().endswith('.pdf'):
                        import PyPDF2
                        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                        resume_text = "\n".join([page.extract_text() for page in pdf_reader.pages])
                    elif file_name.lower().endswith('.txt'):
                        resume_text = file_content.decode('utf-8')
                    else:
                        resume_text = f"Resume file: {file_name}"
                except Exception as e:
                    print(f"Error extracting text: {str(e)}")
                    resume_text = f"Resume file: {file_name}"
                
                if not resume_text or len(resume_text.strip()) < 10:
                    return response(400, {"error": "Could not extract text from resume"})
                
                # 3. Generate embedding (optional - will use text search if fails)
                resume_embedding = None
                try:
                    # Cohere model has max 2048 chars limit
                    embedding_body = {
                        "texts": [resume_text[:2048]],  # Limit to 2048 chars for Cohere
                        "input_type": "search_document"
                    }
                    embedding_response = bedrock_runtime.invoke_model(
                        modelId=BEDROCK_EMBEDDING_MODEL,
                        body=json.dumps(embedding_body)
                    )
                    embedding_result = json.loads(embedding_response["body"].read())
                    resume_embedding = embedding_result.get("embeddings", [])[0]
                    print(f"Generated embedding successfully (dimension: {len(resume_embedding)})")
                except Exception as e:
                    print(f"Warning: Could not generate embedding: {str(e)}")
                    print("Will use text-based search instead")
                    resume_embedding = None
                
                # 4. Search in OpenSearch (vector search if available, otherwise text search)
                search_url = f"https://{OPENSEARCH_HOST}/{INDEX_NAME}/_search"
                search_res = None
                use_vector_search = False
                
                # Try vector search if embedding is available
                if resume_embedding:
                    try:
                        search_query = {
                            "size": 3,
                            "query": {
                                "knn": {
                                    "embeddings": {
                                        "vector": resume_embedding,
                                        "k": 3
                                    }
                                }
                            }
                        }
                        
                        search_res = requests.post(
                            search_url,
                            auth=awsauth,
                            headers={"Content-Type": "application/json"},
                            json=search_query,
                            timeout=10
                        )
                        
                        if search_res.status_code == 200:
                            use_vector_search = True
                            print("Using vector search")
                        else:
                            print(f"Vector search failed ({search_res.status_code}), trying text search...")
                    except Exception as e:
                        print(f"Vector search error: {str(e)}, trying text search...")
                
                # Fallback to text-based search
                if not use_vector_search:
                    search_query = {
                        "size": 3,
                        "query": {
                            "multi_match": {
                                "query": resume_text[:500],
                                "fields": ["title", "description", "text_excerpt"],
                                "type": "best_fields"
                            }
                        }
                    }
                    
                    search_res = requests.post(
                        search_url,
                        auth=awsauth,
                        headers={"Content-Type": "application/json"},
                        json=search_query,
                        timeout=10
                    )
                    
                    if search_res.status_code != 200:
                        print(f"OpenSearch search error: {search_res.status_code} - {search_res.text}")
                        return response(500, {"error": f"OpenSearch search error: {search_res.text}"})
                
                # 5. Format results to match frontend expectations
                hits = search_res.json().get("hits", {}).get("hits", [])
                results = []
                for i, hit in enumerate(hits, 1):
                    source = hit.get("_source", {})
                    raw_score = hit.get("_score", 0.0)
                    # Normalize score to 0-1 range (OpenSearch scores can be > 1)
                    normalized_score = min(raw_score / 10.0, 1.0) if raw_score > 0 else 0.0
                    
                    results.append({
                        "rank": i,
                        "job_id": hit.get("_id", ""),
                        "job_title": source.get("title", "N/A"),  # Frontend expects job_title
                        "title": source.get("title", "N/A"),  # Keep for backward compatibility
                        "description": source.get("description", ""),
                        "text_excerpt": source.get("text_excerpt", ""),
                        "metadata": source.get("metadata", {}),
                        "match_score": normalized_score,  # Frontend expects match_score (0-1)
                        "rerank_score": normalized_score,  # Use same score for rerank (no reranking yet)
                        "score": raw_score,  # Keep original score for backward compatibility
                        "reasons": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {raw_score:.4f}",  # Frontend expects reasons
                        "match_reason": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {raw_score:.4f}"  # Keep for backward compatibility
                    })
                
                return response(200, {
                    "resume_id": resume_key,
                    "results": results,
                    "total": len(results)
                })
                
            except Exception as e:
                print(f"Error in search_by_resume: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return response(500, {"error": str(e)})

        # ---- search resumes by job (Mode B) ----
        if path == "/api/resumes/search_by_job" and method == "POST":
            try:
                # Get job_id from query string
                query_params = event.get("queryStringParameters") or {}
                job_id = query_params.get("job_id")
                
                if not job_id:
                    return response(400, {"error": "job_id is required"})
                
                body = json.loads(event.get("body", "{}"))
                resume_keys = body.get("resume_keys") or body.get("resume_ids") or []
                
                print(f"Searching resumes for job: {job_id}, resume_keys: {len(resume_keys)}")
                
                # 1. Get job from OpenSearch
                job_url = f"https://{OPENSEARCH_HOST}/{INDEX_NAME}/_doc/{job_id}"
                job_res = requests.get(job_url, auth=awsauth, timeout=10)
                
                if job_res.status_code != 200:
                    return response(404, {"error": f"Job {job_id} not found"})
                
                job_data = job_res.json().get("_source", {})
                job_description = job_data.get("description", job_data.get("text_excerpt", ""))
                
                if not job_description:
                    return response(400, {"error": "Job has no description"})
                
                # 2. Generate embedding for job
                try:
                    embedding_body = {
                        "texts": [job_description[:5000]],
                        "input_type": "search_query"
                    }
                    embedding_response = bedrock_runtime.invoke_model(
                        modelId=BEDROCK_EMBEDDING_MODEL,
                        body=json.dumps(embedding_body)
                    )
                    embedding_result = json.loads(embedding_response["body"].read())
                    job_embedding = embedding_result.get("embeddings", [])[0]
                except Exception as e:
                    print(f"Error generating embedding: {str(e)}")
                    return response(500, {"error": f"Failed to generate embedding: {str(e)}"})
                
                # 3. If resume_keys provided, search only those resumes
                # Otherwise, we'd need a resumes index - for now, return placeholder
                if resume_keys:
                    # Process each resume and calculate similarity
                    results = []
                    for resume_key in resume_keys[:10]:  # Limit to 10
                        try:
                            # Get resume from S3
                            if not resume_key.startswith(RESUME_PREFIX):
                                if resume_key.startswith("Candidate/"):
                                    resume_key = f"{RESUME_PREFIX}{resume_key}"
                                else:
                                    resume_key = f"{RESUME_PREFIX}Candidate/{resume_key}"
                            
                            obj = s3.get_object(Bucket=RESUME_BUCKET, Key=resume_key)
                            file_content = obj["Body"].read()
                            file_name = resume_key.split("/")[-1]
                            
                            # Extract text
                            resume_text = ""
                            if file_name.lower().endswith('.pdf'):
                                import PyPDF2
                                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                                resume_text = "\n".join([page.extract_text() for page in pdf_reader.pages])
                            elif file_name.lower().endswith('.txt'):
                                resume_text = file_content.decode('utf-8')
                            
                            if resume_text:
                                # Generate embedding for resume
                                resume_embed_body = {
                                    "texts": [resume_text[:5000]],
                                    "input_type": "search_document"
                                }
                                resume_emb_res = bedrock_runtime.invoke_model(
                                    modelId=BEDROCK_EMBEDDING_MODEL,
                                    body=json.dumps(resume_emb_body)
                                )
                                resume_emb_result = json.loads(resume_emb_res["body"].read())
                                resume_embedding = resume_emb_result.get("embeddings", [])[0]
                                
                                # Calculate cosine similarity (without numpy)
                                dot_product = sum(a * b for a, b in zip(job_embedding, resume_embedding))
                                norm_job = sum(a * a for a in job_embedding) ** 0.5
                                norm_resume = sum(a * a for a in resume_embedding) ** 0.5
                                similarity = dot_product / (norm_job * norm_resume) if (norm_job * norm_resume) > 0 else 0
                                
                                results.append({
                                    "resume_id": resume_key,
                                    "resume_name": file_name,
                                    "score": float(similarity),
                                    "text_excerpt": resume_text[:200] + "..." if len(resume_text) > 200 else resume_text
                                })
                        except Exception as e:
                            print(f"Error processing resume {resume_key}: {str(e)}")
                            continue
                    
                    # Sort by score descending
                    results.sort(key=lambda x: x["score"], reverse=True)
                    
                    # Add rank
                    for i, result in enumerate(results, 1):
                        result["rank"] = i
                    
                    return response(200, {
                        "query": {
                            "job_id": job_id,
                            "job_description": job_description[:100] + "..." if len(job_description) > 100 else job_description
                        },
                        "results": results,
                        "total": len(results)
                    })
                else:
                    return response(200, {
                        "query": {
                            "job_id": job_id
                        },
                        "results": [],
                        "total": 0,
                        "message": "Please provide resume_keys in request body"
                    })
                
            except Exception as e:
                print(f"Error in search_by_job: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return response(500, {"error": str(e)})

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
