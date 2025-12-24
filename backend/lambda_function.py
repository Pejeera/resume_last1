import json
import boto3
import urllib.parse
import sys
import os

# Add python/ directory to path for dependencies
current_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.join(current_dir, 'python')
if os.path.exists(python_dir) and python_dir not in sys.path:
    sys.path.insert(0, python_dir)

import requests
from requests_aws4auth import AWS4Auth
from requests.auth import HTTPBasicAuth
import io
import os

# ================== CONFIG ==================
OPENSEARCH_HOST = "search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com"
INDEX_NAME = "jobs_index"  # Changed from "jobs" to "jobs_index" to match sync data
REGION = "ap-southeast-2"
SERVICE = "es"

RESUME_BUCKET = "resume-matching-533267343789"
RESUME_PREFIX = "resumes/"

# Bedrock config
BEDROCK_REGION = "us-east-1"
BEDROCK_EMBEDDING_MODEL = "cohere.embed-multilingual-v3"
# Use model ID directly instead of inference profile
BEDROCK_RERANK_MODEL = "amazon.nova-lite-v1:0"  # Changed from us.amazon.nova-lite-v1:0

# OpenSearch credentials (from environment or default)
OPENSEARCH_USERNAME = os.environ.get("OPENSEARCH_USERNAME", "Admin")
OPENSEARCH_PASSWORD = os.environ.get("OPENSEARCH_PASSWORD", "P@ssw0rd")
# ============================================

# ---------- AWS clients ----------
session = boto3.Session()
credentials = session.get_credentials()

# Use HTTPBasicAuth for OpenSearch (username/password)
opensearch_auth = HTTPBasicAuth(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD)

# Keep AWS4Auth for other AWS services if needed
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    SERVICE,
    session_token=credentials.token
) if credentials else None

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
    print("=== Lambda Handler Started ===")
    print("EVENT:", json.dumps(event))

    # =====================================================
    # 1) HTTP API
    # =====================================================
    if "requestContext" in event:
        path = event.get("rawPath", "")
        method = event["requestContext"]["http"]["method"]
        print(f"HTTP Request: {method} {path}")
        print(f"Query params: {event.get('queryStringParameters', {})}")
        print(f"Body: {event.get('body', '')[:500]}")  # First 500 chars of body

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

        # ---- list jobs from S3 directory: resumes/jobs/ ----
        if (path == "/api/jobs" or path == "/api/jobs/list") and method == "GET":
            try:
                jobs_prefix = f"{RESUME_PREFIX}jobs/"
                jobs_data = []
                
                # List all objects in resumes/jobs/ prefix
                paginator = s3.get_paginator('list_objects_v2')
                
                for page in paginator.paginate(Bucket=RESUME_BUCKET, Prefix=jobs_prefix):
                    if 'Contents' not in page:
                        continue
                    
                    for obj in page['Contents']:
                        s3_key = obj['Key']
                        
                        # Only process .json files (skip directories)
                        if not s3_key.endswith('.json'):
                            continue
                        
                        try:
                            # Get and parse JSON file
                            file_obj = s3.get_object(Bucket=RESUME_BUCKET, Key=s3_key)
                            content = file_obj['Body'].read().decode('utf-8')
                            job_data = json.loads(content)
                            
                            # Each file should contain 1 job object (dict)
                            if isinstance(job_data, dict):
                                jobs_data.append(job_data)
                            elif isinstance(job_data, list):
                                # If file contains array, add all items
                                jobs_data.extend(job_data)
                        except json.JSONDecodeError as e:
                            print(f"Failed to parse JSON from {s3_key}: {e}")
                            continue
                        except Exception as e:
                            print(f"Error processing {s3_key}: {e}")
                            continue
                
                # Format jobs for frontend
                result = [
                    {
                        "job_id": job.get("_id", job.get("id", job.get("job_id", ""))),
                        "title": job.get("title", "N/A"),
                        "description": job.get("description", job.get("text_excerpt", ""))[:200],
                        "created_at": job.get("created_at", "")
                    }
                    for job in jobs_data
                ]
                
                print(f"Loaded {len(result)} jobs from S3: {jobs_prefix}")
                return response(200, {"jobs": result, "total": len(result)})
            except Exception as e:
                print(f"Error fetching jobs from S3: {str(e)}")
                return response(500, {"error": str(e), "jobs": [], "total": 0})

        # ---- sync jobs from S3 to OpenSearch (with embeddings) ----
        if path == "/api/jobs/sync_from_s3" and method == "POST":
            try:
                print("Starting sync jobs from S3 to OpenSearch...")
                jobs_prefix = f"{RESUME_PREFIX}jobs/"
                jobs_data = []
                
                # 1. Load all jobs from S3
                paginator = s3.get_paginator('list_objects_v2')
                
                for page in paginator.paginate(Bucket=RESUME_BUCKET, Prefix=jobs_prefix):
                    if 'Contents' not in page:
                        continue
                    
                    for obj in page['Contents']:
                        s3_key = obj['Key']
                        
                        if not s3_key.endswith('.json'):
                            continue
                        
                        try:
                            file_obj = s3.get_object(Bucket=RESUME_BUCKET, Key=s3_key)
                            content = file_obj['Body'].read().decode('utf-8')
                            job_data = json.loads(content)
                            
                            if isinstance(job_data, dict):
                                jobs_data.append(job_data)
                            elif isinstance(job_data, list):
                                jobs_data.extend(job_data)
                        except Exception as e:
                            print(f"Error loading {s3_key}: {e}")
                            continue
                
                if not jobs_data:
                    return response(200, {
                        "message": "No jobs found in S3",
                        "synced": 0,
                        "skipped": 0,
                        "total": 0
                    })
                
                print(f"Found {len(jobs_data)} jobs in S3, starting sync...")
                
                # 2. Ensure index exists
                index_url = f"https://{OPENSEARCH_HOST}/jobs_index"
                index_mapping = {
                    "mappings": {
                        "properties": {
                            "id": {"type": "keyword"},
                            "title": {"type": "text"},
                            "description": {"type": "text"},
                            "text_excerpt": {"type": "text"},
                            "embeddings": {
                                "type": "knn_vector",
                                "dimension": 1024
                            },
                            "metadata": {"type": "object"},
                            "created_at": {"type": "date"}
                        }
                    }
                }
                
                # Check if index exists
                check_res = requests.head(index_url, auth=opensearch_auth, timeout=10)
                if check_res.status_code == 404:
                    # Create index
                    create_res = requests.put(
                        index_url,
                        auth=opensearch_auth,
                        headers={"Content-Type": "application/json"},
                        json=index_mapping,
                        timeout=30
                    )
                    if create_res.status_code not in [200, 201]:
                        print(f"Warning: Could not create index: {create_res.text}")
                    else:
                        print("Created jobs_index in OpenSearch")
                
                # 3. Sync each job with embedding
                synced_count = 0
                skipped_count = 0
                
                for job_data in jobs_data:
                    try:
                        job_id = job_data.get("_id") or job_data.get("job_id") or job_data.get("id")
                        
                        if not job_id:
                            print(f"Skipping job: no ID found in {job_data}")
                            skipped_count += 1
                            continue
                        
                        # Prepare document - normalize structure
                        document = {k: v for k, v in job_data.items() if k != "_id"}
                        document["id"] = job_id
                        
                        # Build description from available fields
                        if "description" not in document or not document.get("description"):
                            desc_parts = []
                            if document.get("title"):
                                desc_parts.append(f"Title: {document.get('title')}")
                            if document.get("skills"):
                                desc_parts.append(f"Skills: {', '.join(document.get('skills', []))}")
                            if document.get("responsibilities"):
                                desc_parts.append(f"Responsibilities: {' '.join(document.get('responsibilities', []))}")
                            if document.get("requirements"):
                                desc_parts.append(f"Requirements: {' '.join(document.get('requirements', []))}")
                            document["description"] = "\n".join(desc_parts)
                        
                        # Create text_excerpt
                        if "text_excerpt" not in document:
                            document["text_excerpt"] = document.get("description", "")[:500]
                        
                        # Create metadata object
                        if "metadata" not in document:
                            metadata = {}
                            for key in ["department", "location", "employment_type", "experience_years", "skills", "responsibilities", "requirements"]:
                                if key in document:
                                    metadata[key] = document[key]
                            document["metadata"] = metadata
                        
                        # Generate embedding if not present
                        if "embeddings" not in document or not document.get("embeddings"):
                            try:
                                full_text = f"{document.get('title', '')}\n{document.get('description', '')}"
                                embedding_body = {
                                    "texts": [full_text[:2048]],  # Cohere limit
                                    "input_type": "search_document"
                                }
                                embedding_response = bedrock_runtime.invoke_model(
                                    modelId=BEDROCK_EMBEDDING_MODEL,
                                    body=json.dumps(embedding_body)
                                )
                                embedding_result = json.loads(embedding_response["body"].read())
                                document["embeddings"] = embedding_result.get("embeddings", [])[0]
                                print(f"Generated embedding for job {job_id} (dimension: {len(document['embeddings'])})")
                            except Exception as e:
                                print(f"Warning: Failed to generate embedding for job {job_id}: {e}")
                                import traceback
                                traceback.print_exc()
                                # Continue without embedding
                        
                        # Index to OpenSearch
                        index_doc_url = f"https://{OPENSEARCH_HOST}/jobs_index/_doc/{job_id}"
                        index_res = requests.put(
                            index_doc_url,
                            auth=opensearch_auth,
                            headers={"Content-Type": "application/json"},
                            json=document,
                            timeout=10
                        )
                        
                        if index_res.status_code in [200, 201]:
                            synced_count += 1
                            print(f"Synced job {job_id} to OpenSearch")
                        else:
                            print(f"Failed to index job {job_id}: {index_res.status_code} - {index_res.text}")
                            skipped_count += 1
                            
                    except Exception as e:
                        print(f"Error syncing job {job_data.get('_id', job_data.get('job_id', 'unknown'))}: {e}")
                        import traceback
                        traceback.print_exc()
                        skipped_count += 1
                
                print(f"Sync completed: {synced_count} synced, {skipped_count} skipped")
                return response(200, {
                    "message": f"Successfully synced {synced_count} jobs from S3 to OpenSearch",
                    "synced": synced_count,
                    "skipped": skipped_count,
                    "total": len(jobs_data)
                })
                
            except Exception as e:
                print(f"Error syncing jobs: {str(e)}")
                import traceback
                traceback.print_exc()
                return response(500, {"error": str(e), "synced": 0, "skipped": 0, "total": 0})

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

        # ---- sync resumes from S3 to OpenSearch (with embeddings) ----
        if path == "/api/resumes/sync_from_s3" and method == "POST":
            try:
                print("Starting sync resumes from S3 to OpenSearch...")
                resumes_prefix = f"{RESUME_PREFIX}Candidate/"
                
                # 1. List all resume files from S3
                resp = s3.list_objects_v2(
                    Bucket=RESUME_BUCKET,
                    Prefix=resumes_prefix
                )
                
                resume_files = []
                for obj in resp.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith("/"):
                        resume_files.append(key)
                
                if not resume_files:
                    return response(200, {
                        "message": "No resumes found in S3",
                        "synced": 0,
                        "skipped": 0,
                        "total": 0
                    })
                
                print(f"Found {len(resume_files)} resume files in S3, starting sync...")
                
                # 2. Ensure index exists
                index_url = f"https://{OPENSEARCH_HOST}/resumes_index"
                index_mapping = {
                    "mappings": {
                        "properties": {
                            "id": {"type": "keyword"},
                            "filename": {"type": "text"},
                            "full_text": {"type": "text"},
                            "text_excerpt": {"type": "text"},
                            "embeddings": {
                                "type": "knn_vector",
                                "dimension": 1024
                            },
                            "metadata": {"type": "object"},
                            "created_at": {"type": "date"}
                        }
                    }
                }
                
                check_res = requests.head(index_url, auth=opensearch_auth, timeout=10)
                if check_res.status_code == 404:
                    create_res = requests.put(
                        index_url,
                        auth=opensearch_auth,
                        headers={"Content-Type": "application/json"},
                        json=index_mapping,
                        timeout=30
                    )
                    if create_res.status_code not in [200, 201]:
                        print(f"Warning: Could not create index: {create_res.text}")
                    else:
                        print("Created resumes_index in OpenSearch")
                
                # 3. Process each resume
                synced_count = 0
                skipped_count = 0
                
                for resume_key in resume_files:
                    try:
                        # Extract resume_id from key
                        resume_id = resume_key.split("/")[-1].replace(".pdf", "").replace(".docx", "").replace(".txt", "")
                        if not resume_id:
                            resume_id = resume_key.replace("/", "_").replace(".", "_")
                        
                        print(f"Processing resume: {resume_key} (ID: {resume_id})")
                        
                        # Get file from S3
                        file_obj = s3.get_object(Bucket=RESUME_BUCKET, Key=resume_key)
                        file_content = file_obj["Body"].read()
                        file_name = resume_key.split("/")[-1]
                        
                        # Extract text
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
                            print(f"Warning: Could not extract text from {file_name}: {e}")
                            resume_text = f"Resume file: {file_name}"
                        
                        if not resume_text or len(resume_text.strip()) < 10:
                            print(f"Skipping {resume_id}: No text extracted")
                            skipped_count += 1
                            continue
                        
                        # Prepare document
                        document = {
                            "id": resume_id,
                            "filename": file_name,
                            "full_text": resume_text,
                            "text_excerpt": resume_text[:500],
                            "metadata": {
                                "s3_key": resume_key,
                                "file_size": len(file_content)
                            }
                        }
                        
                        # Generate embedding
                        try:
                            embedding_body = {
                                "texts": [resume_text[:2048]],  # Cohere limit
                                "input_type": "search_document"
                            }
                            embedding_response = bedrock_runtime.invoke_model(
                                modelId=BEDROCK_EMBEDDING_MODEL,
                                body=json.dumps(embedding_body)
                            )
                            embedding_result = json.loads(embedding_response["body"].read())
                            document["embeddings"] = embedding_result.get("embeddings", [])[0]
                            print(f"Generated embedding for resume {resume_id} (dimension: {len(document['embeddings'])})")
                        except Exception as e:
                            print(f"Warning: Failed to generate embedding for resume {resume_id}: {e}")
                            # Continue without embedding
                        
                        # Index to OpenSearch
                        index_doc_url = f"https://{OPENSEARCH_HOST}/resumes_index/_doc/{resume_id}"
                        index_res = requests.put(
                            index_doc_url,
                            auth=opensearch_auth,
                            headers={"Content-Type": "application/json"},
                            json=document,
                            timeout=10
                        )
                        
                        if index_res.status_code in [200, 201]:
                            synced_count += 1
                            print(f"Synced resume {resume_id} to OpenSearch")
                        else:
                            print(f"Failed to index resume {resume_id}: {index_res.status_code} - {index_res.text}")
                            skipped_count += 1
                            
                    except Exception as e:
                        print(f"Error syncing resume {resume_key}: {e}")
                        import traceback
                        traceback.print_exc()
                        skipped_count += 1
                
                print(f"Sync completed: {synced_count} synced, {skipped_count} skipped")
                return response(200, {
                    "message": f"Successfully synced {synced_count} resumes from S3 to OpenSearch",
                    "synced": synced_count,
                    "skipped": skipped_count,
                    "total": len(resume_files)
                })
                
            except Exception as e:
                print(f"Error syncing resumes: {str(e)}")
                import traceback
                traceback.print_exc()
                return response(500, {"error": str(e), "synced": 0, "skipped": 0, "total": 0})

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
                            "size": 100,  # Search all jobs first, then select Top 3
                            "query": {
                                "knn": {
                                    "embeddings": {
                                        "vector": resume_embedding,
                                        "k": 100  # Get top 100 for reranking
                                    }
                                }
                            }
                        }
                        
                        search_res = requests.post(
                            search_url,
                            auth=opensearch_auth,
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
                        "size": 100,  # Search all jobs first, then select Top 3
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
                        auth=opensearch_auth,
                        headers={"Content-Type": "application/json"},
                        json=search_query,
                        timeout=10
                    )
                    
                    if search_res.status_code != 200:
                        print(f"OpenSearch search error: {search_res.status_code} - {search_res.text}")
                        return response(500, {"error": f"OpenSearch search error: {search_res.text}"})
                
                # 5. Prepare candidates for reranking
                hits = search_res.json().get("hits", {}).get("hits", [])
                all_candidates = []
                for hit in hits:
                    source = hit.get("_source", {})
                    raw_score = hit.get("_score", 0.0)
                    normalized_score = min(raw_score / 10.0, 1.0) if raw_score > 0 else 0.0
                    
                    all_candidates.append({
                        "job_id": hit.get("_id", ""),
                        "title": source.get("title", "N/A"),
                        "description": source.get("description", ""),
                        "text_excerpt": source.get("text_excerpt", ""),
                        "metadata": source.get("metadata", {}),
                        "vector_score": normalized_score,
                        "raw_score": raw_score
                    })
                
                # Sort by embedding score and select Top 3
                all_candidates.sort(key=lambda x: x["vector_score"], reverse=True)
                candidates = all_candidates[:3]  # Select Top 3 based on embedding score
                print(f"Selected Top 3 candidates from {len(all_candidates)} total jobs based on embedding score")
                
                # 6. Rerank with Nova Lite v1
                results = []
                try:
                    print(f"Attempting reranking with Nova Lite ({BEDROCK_RERANK_MODEL})...")
                    
                    # Build prompt for reranking
                    resume_summary = resume_text[:500] + "..." if len(resume_text) > 500 else resume_text
                    candidates_text = "\n".join([
                        f"{i+1}. {c.get('title', 'N/A')} - {c.get('text_excerpt', '')[:200]}..."
                        for i, c in enumerate(candidates)
                    ])
                    
                    rerank_prompt = f"""คุณเป็น AI ที่เชี่ยวชาญในการจับคู่ Resume กับ Job

**Resume Summary:**
{resume_summary}

**รายการตำแหน่งงาน (Jobs):**
{candidates_text}

**งานของคุณ:**
1. วิเคราะห์และจัดอันดับ Top 3 ตำแหน่งงานที่เหมาะสมที่สุดกับ Resume นี้
2. ให้เหตุผลสั้นๆ กระชับ (2-3 ประโยค) ว่าทำไมถึงเหมาะ
3. ระบุจุดเด่น (highlighted_skills) และจุดที่ขาด (gaps) ถ้ามี
4. แนะนำคำถามสำหรับสัมภาษณ์ (recommended_questions_for_interview)

**ข้อกำหนด:**
- ห้ามสร้างข้อมูลที่ไม่มีในรายการ
- ถ้าข้อมูลไม่พอ ให้ระบุว่า "ข้อมูลไม่เพียงพอ"
- ใช้ภาษาไทยในการให้เหตุผล
- คะแนน rerank_score ควรอยู่ระหว่าง 0.0-1.0

**รูปแบบผลลัพธ์ (JSON):**
{{
  "ranked_candidates": [
    {{
      "candidate_index": 0,
      "rerank_score": 0.95,
      "reasons": "เหตุผลสั้นๆ",
      "highlighted_skills": ["skill1", "skill2"],
      "gaps": ["gap1"],
      "recommended_questions_for_interview": ["คำถาม1", "คำถาม2"]
    }}
  ]
}}

กรุณาให้ผลลัพธ์เป็น JSON เท่านั้น:"""
                    
                    # Call Nova Lite for reranking (Nova Lite format)
                    rerank_body = json.dumps({
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "text": rerank_prompt
                                    }
                                ]
                            }
                        ],
                        "inferenceConfig": {
                            "maxTokens": 5000,
                            "temperature": 0.3,
                            "topP": 0.9
                        }
                    })
                    
                    rerank_response = bedrock_runtime.invoke_model(
                        modelId=BEDROCK_RERANK_MODEL,
                        body=rerank_body
                    )
                    
                    # Parse Nova Lite response format: {"output": {"message": {"content": [{"text": "..."}]}}}
                    rerank_result = json.loads(rerank_response["body"].read())
                    output = rerank_result.get("output", {})
                    message = output.get("message", {})
                    content = message.get("content", [])
                    
                    if content:
                        result_text = content[0].get("text", "{}")
                        # Extract JSON from markdown code blocks if present
                        if "```json" in result_text:
                            result_text = result_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in result_text:
                            result_text = result_text.split("```")[1].split("```")[0].strip()
                        
                        ranked_data = json.loads(result_text)
                        ranked_list = ranked_data.get("ranked_candidates", [])
                        
                        if ranked_list and len(ranked_list) > 0:
                            # Map reranked results back to candidates
                            for item in ranked_list:
                                idx = item.get("candidate_index", 0)
                                if 0 <= idx < len(candidates):
                                    candidate = candidates[idx]
                                    results.append({
                                        "rank": len(results) + 1,
                                        "job_id": candidate["job_id"],
                                        "job_title": candidate["title"],
                                        "title": candidate["title"],
                                        "description": candidate["description"],
                                        "text_excerpt": candidate["text_excerpt"],
                                        "metadata": candidate["metadata"],
                                        "match_score": candidate["vector_score"],
                                        "rerank_score": float(item.get("rerank_score", 0.0)),
                                        "score": candidate["raw_score"],
                                        "reasons": item.get("reasons", "ไม่มีข้อมูล"),
                                        "highlighted_skills": item.get("highlighted_skills", []),
                                        "gaps": item.get("gaps", []),
                                        "recommended_questions_for_interview": item.get("recommended_questions_for_interview", []),
                                        "match_reason": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}"
                                    })
                            print(f"Reranked {len(results)} candidates using Nova Lite")
                        else:
                            print("Warning: Nova Lite returned empty ranked list, using original results")
                            # Fallback to original results
                            for i, candidate in enumerate(candidates, 1):
                                results.append({
                                    "rank": i,
                                    "job_id": candidate["job_id"],
                                    "job_title": candidate["title"],
                                    "title": candidate["title"],
                                    "description": candidate["description"],
                                    "text_excerpt": candidate["text_excerpt"],
                                    "metadata": candidate["metadata"],
                                    "match_score": candidate["vector_score"],
                                    "rerank_score": candidate["vector_score"],
                                    "score": candidate["raw_score"],
                                    "reasons": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}",
                                    "match_reason": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}"
                                })
                    else:
                        print("Warning: Nova Lite returned no content, using original results")
                        # Fallback to original results
                        for i, candidate in enumerate(candidates, 1):
                            results.append({
                                "rank": i,
                                "job_id": candidate["job_id"],
                                "job_title": candidate["title"],
                                "title": candidate["title"],
                                "description": candidate["description"],
                                "text_excerpt": candidate["text_excerpt"],
                                "metadata": candidate["metadata"],
                                "match_score": candidate["vector_score"],
                                "rerank_score": candidate["vector_score"],
                                "score": candidate["raw_score"],
                                "reasons": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}",
                                "match_reason": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}"
                            })
                except Exception as e:
                    print(f"Warning: Reranking with Nova Lite failed: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                    print("Falling back to original results without reranking")
                    # Fallback: use original results without reranking
                    for i, candidate in enumerate(candidates, 1):
                        results.append({
                            "rank": i,
                            "job_id": candidate["job_id"],
                            "job_title": candidate["title"],
                            "title": candidate["title"],
                            "description": candidate["description"],
                            "text_excerpt": candidate["text_excerpt"],
                            "metadata": candidate["metadata"],
                            "match_score": candidate["vector_score"],
                            "rerank_score": candidate["vector_score"],
                            "score": candidate["raw_score"],
                            "reasons": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}",
                            "match_reason": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}"
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
            print(">>> Mode B endpoint matched! <<<")
            try:
                # Get job_id from query string
                query_params = event.get("queryStringParameters") or {}
                job_id = query_params.get("job_id")
                
                if not job_id:
                    return response(400, {"error": "job_id is required"})
                
                body = json.loads(event.get("body", "{}"))
                resume_keys = body.get("resume_keys") or body.get("resume_ids") or []
                
                print(f"=== Mode B: Searching resumes for job ===")
                print(f"Job ID: {job_id}")
                print(f"Resume keys count: {len(resume_keys)}")
                print(f"Resume keys received: {resume_keys}")
                print(f"Body received: {body}")
                
                if not resume_keys or len(resume_keys) == 0:
                    print("WARNING: No resume keys provided!")
                    return response(400, {"error": "resume_keys or resume_ids is required and cannot be empty"})
                
                # 1. Get job from OpenSearch
                job_url = f"https://{OPENSEARCH_HOST}/{INDEX_NAME}/_doc/{job_id}"
                job_res = requests.get(job_url, auth=opensearch_auth, timeout=10)
                
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
                    # Process each resume and calculate similarity (process ALL resumes first)
                    results = []
                    print(f"Processing {len(resume_keys)} resumes (all resumes will be processed)...")
                    print(f"Resume keys to process: {resume_keys}")
                    for idx, resume_key in enumerate(resume_keys):  # Process ALL resumes
                        try:
                            original_key = resume_key
                            # Get resume from S3
                            if not resume_key.startswith(RESUME_PREFIX):
                                if resume_key.startswith("Candidate/"):
                                    resume_key = f"{RESUME_PREFIX}{resume_key}"
                                else:
                                    resume_key = f"{RESUME_PREFIX}Candidate/{resume_key}"
                            
                            print(f"[{idx+1}/{len(resume_keys)}] Processing: original='{original_key}', normalized='{resume_key}'")
                            
                            try:
                                obj = s3.get_object(Bucket=RESUME_BUCKET, Key=resume_key)
                            except Exception as s3_error:
                                print(f"  - S3 ERROR: Cannot get object '{resume_key}': {str(s3_error)}")
                                results.append({
                                    "resume_id": resume_key,
                                    "resume_name": resume_key.split("/")[-1] if "/" in resume_key else resume_key,
                                    "score": 0.0,
                                    "text_excerpt": f"S3 Error: {str(s3_error)}",
                                    "error": f"S3 Error: {str(s3_error)}"
                                })
                                continue
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
                            
                            print(f"  - File: {file_name}, text length: {len(resume_text)}")
                            
                            if not resume_text or len(resume_text.strip()) < 10:
                                print(f"  - WARNING: Resume {file_name} has no extractable text or text too short (length: {len(resume_text)})")
                                # ยังคง append แต่มี flag ว่าไม่มี text
                                results.append({
                                    "resume_id": resume_key,
                                    "resume_name": file_name,
                                    "score": 0.0,
                                    "text_excerpt": "ไม่สามารถอ่านข้อความจากไฟล์นี้ได้",
                                    "error": "Could not extract text from resume"
                                })
                                print(f"  - Appended empty text result. Current results count: {len(results)}")
                                continue
                            
                            if resume_text:
                                # Generate embedding for resume
                                resume_embed_body = {
                                    "texts": [resume_text[:5000]],
                                    "input_type": "search_document"
                                }
                                resume_emb_res = bedrock_runtime.invoke_model(
                                    modelId=BEDROCK_EMBEDDING_MODEL,
                                    body=json.dumps(resume_embed_body)
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
                                print(f"  - Successfully processed resume {file_name} with score {similarity:.4f}. Current results count: {len(results)}")
                        except Exception as e:
                            print(f"  - ERROR processing resume {resume_key}: {str(e)}")
                            import traceback
                            print(traceback.format_exc())
                            # Append error result instead of skipping
                            results.append({
                                "resume_id": resume_key,
                                "resume_name": resume_key.split("/")[-1] if "/" in resume_key else resume_key,
                                "score": 0.0,
                                "text_excerpt": f"Error: {str(e)}",
                                "error": str(e)
                            })
                            continue
                    
                    # Sort by score descending
                    results.sort(key=lambda x: x["score"], reverse=True)
                    
                    print(f"=== Mode B: Processed {len(results)} resumes successfully ===")
                    print(f"Results summary: {[{'name': r['resume_name'], 'score': r['score']} for r in results]}")
                    
                    if len(results) == 0:
                        return response(200, {
                            "query": {
                                "job_id": job_id,
                                "job_description": job_description[:100] + "..." if len(job_description) > 100 else job_description
                            },
                            "results": [],
                            "total": 0,
                            "message": "ไม่สามารถประมวลผล Resume ได้ (อาจเป็นเพราะไฟล์ไม่ใช่ PDF/TXT หรือมีปัญหาในการอ่านไฟล์)"
                        })
                    
                    # Select Top 3 based on embedding score
                    top_results = results[:3]  # Select Top 3 based on embedding score
                    print(f"Selected Top 3 resumes from {len(results)} total resumes based on embedding score")
                    
                    # Prepare candidates for reranking (only Top 3)
                    candidates = []
                    for result in top_results:
                        candidates.append({
                            "resume_id": result["resume_id"],
                            "resume_name": result["resume_name"],
                            "text_excerpt": result["text_excerpt"],
                            "resume_text": "",  # Will be filled if needed
                            "vector_score": result["score"],
                            "raw_score": result["score"]
                        })
                    
                    # Rerank with Nova Lite v1
                    reranked_results = []
                    try:
                        print(f"Attempting reranking with Nova Lite ({BEDROCK_RERANK_MODEL})...")
                        
                        # Build prompt for reranking
                        job_summary = job_description[:500] + "..." if len(job_description) > 500 else job_description
                        candidates_text = "\n".join([
                            f"{i+1}. {c.get('resume_name', 'N/A')} - {c.get('text_excerpt', '')[:200]}..."
                            for i, c in enumerate(candidates)
                        ])
                        
                        rerank_prompt = f"""คุณเป็น AI ที่เชี่ยวชาญในการจับคู่ Resume กับ Job

**Job Description:**
{job_summary}

**รายการ Resume (Candidates):**
{candidates_text}

**งานของคุณ:**
1. วิเคราะห์และจัดอันดับ Top 3 Resume ที่เหมาะสมที่สุดกับ Job นี้
2. ให้เหตุผลสั้นๆ กระชับ (2-3 ประโยค) ว่าทำไมถึงเหมาะ
3. ระบุจุดเด่น (highlighted_skills) และจุดที่ขาด (gaps) ถ้ามี
4. แนะนำคำถามสำหรับสัมภาษณ์ (recommended_questions_for_interview)

**ข้อกำหนด:**
- ห้ามสร้างข้อมูลที่ไม่มีในรายการ
- ถ้าข้อมูลไม่พอ ให้ระบุว่า "ข้อมูลไม่เพียงพอ"
- ใช้ภาษาไทยในการให้เหตุผล
- คะแนน rerank_score ควรอยู่ระหว่าง 0.0-1.0

**รูปแบบผลลัพธ์ (JSON):**
{{
  "ranked_candidates": [
    {{
      "candidate_index": 0,
      "rerank_score": 0.95,
      "reasons": "เหตุผลสั้นๆ",
      "highlighted_skills": ["skill1", "skill2"],
      "gaps": ["gap1"],
      "recommended_questions_for_interview": ["คำถาม1", "คำถาม2"]
    }}
  ]
}}

กรุณาให้ผลลัพธ์เป็น JSON เท่านั้น:"""
                        
                        # Call Nova Lite for reranking
                        rerank_body = json.dumps({
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "text": rerank_prompt
                                        }
                                    ]
                                }
                            ],
                            "inferenceConfig": {
                                "maxTokens": 2000,
                                "temperature": 0.3,
                                "topP": 0.9
                            }
                        })
                        
                        rerank_response = bedrock_runtime.invoke_model(
                            modelId=BEDROCK_RERANK_MODEL,
                            body=rerank_body
                        )
                        
                        # Parse Nova Lite response
                        rerank_result = json.loads(rerank_response["body"].read())
                        output = rerank_result.get("output", {})
                        message = output.get("message", {})
                        content = message.get("content", [])
                        
                        if content:
                            result_text = content[0].get("text", "{}")
                            # Extract JSON from markdown code blocks if present
                            if "```json" in result_text:
                                result_text = result_text.split("```json")[1].split("```")[0].strip()
                            elif "```" in result_text:
                                result_text = result_text.split("```")[1].split("```")[0].strip()
                            
                            try:
                                ranked_data = json.loads(result_text)
                            except json.JSONDecodeError as e:
                                print(f"Error parsing JSON from Nova Lite: {str(e)}")
                                print(f"Raw response text: {result_text[:500]}")
                                ranked_data = {}
                            
                            ranked_list = ranked_data.get("ranked_candidates", [])
                            print(f"Nova Lite returned {len(ranked_list)} ranked candidates")
                            
                            if ranked_list and len(ranked_list) > 0:
                                # Map reranked results back to candidates
                                for item in ranked_list:
                                    idx = item.get("candidate_index", 0)
                                    print(f"Processing ranked candidate index: {idx}, total candidates: {len(candidates)}")
                                    if 0 <= idx < len(candidates):
                                        candidate = candidates[idx]
                                        reranked_results.append({
                                            "rank": len(reranked_results) + 1,
                                            "resume_id": candidate["resume_id"],
                                            "resume_name": candidate["resume_name"],
                                            "match_score": candidate["vector_score"],
                                            "rerank_score": float(item.get("rerank_score", 0.0)),
                                            "score": candidate["raw_score"],
                                            "reasons": item.get("reasons", "ไม่มีข้อมูล"),
                                            "highlighted_skills": item.get("highlighted_skills", []),
                                            "gaps": item.get("gaps", []),
                                            "recommended_questions_for_interview": item.get("recommended_questions_for_interview", []),
                                            "text_excerpt": candidate.get("text_excerpt", "")
                                        })
                                    else:
                                        print(f"WARNING: candidate_index {idx} is out of range (0-{len(candidates)-1})")
                                
                                print(f"Reranked {len(reranked_results)} candidates using Nova Lite")
                                
                                # ถ้า reranked_results ยังว่าง ให้ใช้ fallback
                                if len(reranked_results) == 0:
                                    print("WARNING: reranked_results is empty after mapping, using fallback")
                                    raise Exception("Reranked results is empty after mapping")
                            else:
                                print("Warning: Nova Lite returned empty ranked list, using original results")
                                # Fallback to original results
                                for i, candidate in enumerate(candidates, 1):
                                    reranked_results.append({
                                        "rank": i,
                                        "resume_id": candidate["resume_id"],
                                        "resume_name": candidate["resume_name"],
                                        "match_score": candidate["vector_score"],
                                        "rerank_score": candidate["vector_score"],
                                        "score": candidate["raw_score"],
                                        "reasons": f"Vector similarity score: {candidate['raw_score']:.4f}",
                                        "highlighted_skills": [],
                                        "gaps": [],
                                        "recommended_questions_for_interview": [],
                                        "text_excerpt": candidate.get("text_excerpt", "")
                                    })
                        else:
                            print("Warning: Nova Lite returned no content, using original results")
                            # Fallback to original results
                            for i, candidate in enumerate(candidates, 1):
                                reranked_results.append({
                                    "rank": i,
                                    "resume_id": candidate["resume_id"],
                                    "resume_name": candidate["resume_name"],
                                    "match_score": candidate["vector_score"],
                                    "rerank_score": candidate["vector_score"],
                                    "score": candidate["raw_score"],
                                    "reasons": f"Vector similarity score: {candidate['raw_score']:.4f}",
                                    "highlighted_skills": [],
                                    "gaps": [],
                                    "recommended_questions_for_interview": [],
                                    "text_excerpt": candidate.get("text_excerpt", "")
                                })
                    except Exception as e:
                        print(f"Warning: Reranking with Nova Lite failed: {str(e)}")
                        import traceback
                        print(traceback.format_exc())
                        print("Falling back to original results without reranking")
                        # Fallback: use original results without reranking
                        for i, candidate in enumerate(candidates, 1):
                            reranked_results.append({
                                "rank": i,
                                "resume_id": candidate["resume_id"],
                                "resume_name": candidate["resume_name"],
                                "match_score": candidate["vector_score"],
                                "rerank_score": candidate["vector_score"],
                                "score": candidate["raw_score"],
                                "reasons": f"Vector similarity score: {candidate['raw_score']:.4f}",
                                "highlighted_skills": [],
                                "gaps": [],
                                "recommended_questions_for_interview": [],
                                "text_excerpt": candidate.get("text_excerpt", "")
                            })
                    
                    print(f"Final reranked_results count: {len(reranked_results)}")
                    if len(reranked_results) > 0:
                        print(f"First result: {reranked_results[0].get('resume_name', 'N/A')}")
                    
                    return response(200, {
                        "query": {
                            "job_id": job_id,
                            "job_description": job_description[:100] + "..." if len(job_description) > 100 else job_description
                        },
                        "results": reranked_results,
                        "total": len(reranked_results)
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
                    auth=opensearch_auth,
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
