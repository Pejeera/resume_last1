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

# Helper function to extract important information from resume for embedding
def extract_important_resume_info(resume_text, max_chars=2048):
    """
    Extract important information from resume text for embedding.
    Prioritizes: Name, Title, Contact, Skills, Experience, Education, Reference
    """
    if not resume_text:
        return ""
    
    # If text is short enough, return all
    if len(resume_text) <= max_chars:
        return resume_text
    
    # Try to extract key sections
    text_lower = resume_text.lower()
    lines = resume_text.split('\n')
    
    # Priority sections (case-insensitive keywords)
    priority_keywords = [
        'contact', 'phone', 'email', 'location', 'address',
        'skills', 'skill', 'technical skills', 'technical',
        'experience', 'work experience', 'employment', 'internship',
        'education', 'university', 'degree', 'gpa',
        'reference', 'profile', 'summary', 'objective'
    ]
    
    important_parts = []
    current_section = []
    in_important_section = False
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # Check if this line is a section header
        is_section_header = any(keyword in line_lower for keyword in priority_keywords) and len(line.strip()) < 100
        
        if is_section_header:
            # Save previous section if it was important
            if in_important_section and current_section:
                important_parts.append('\n'.join(current_section))
            # Start new important section
            current_section = [line]
            in_important_section = True
        elif in_important_section:
            # Continue adding to current important section
            current_section.append(line)
            # Limit section size
            if len('\n'.join(current_section)) > 800:
                important_parts.append('\n'.join(current_section))
                current_section = []
        else:
            # Check if line contains important info (phone, email, location patterns)
            if any(pattern in line_lower for pattern in ['@', 'phone', 'email', 'location', 'address', 'bang', 'bangkok', 'thailand']):
                important_parts.append(line)
    
    # Add remaining section
    if current_section:
        important_parts.append('\n'.join(current_section))
    
    # Combine important parts
    combined = '\n'.join(important_parts)
    
    # If still too long, take first max_chars with smart truncation
    if len(combined) > max_chars:
        # Try to keep complete sections
        truncated = combined[:max_chars]
        # Try to cut at a newline to avoid cutting mid-word
        last_newline = truncated.rfind('\n')
        if last_newline > max_chars * 0.8:  # If we can cut at a reasonable point
            truncated = truncated[:last_newline]
        return truncated
    
    # If we didn't find structured sections, use first max_chars (fallback)
    if len(combined) < 100:
        return resume_text[:max_chars]
    
    return combined

# Helper function to extract important information from job for embedding
def extract_important_job_info(job_title, job_location, job_description, max_chars=2048):
    """
    Extract important information from job for embedding.
    Prioritizes: Title, Location, Description (with skills, requirements)
    """
    parts = []
    
    # Always include title and location first (highest priority)
    if job_title:
        parts.append(job_title)
    if job_location:
        parts.append(f"Location: {job_location}")
    
    # Then add description, prioritizing important sections
    if job_description:
        desc_lower = job_description.lower()
        
        # Try to extract key sections from description
        if 'skills' in desc_lower or 'requirements' in desc_lower or 'responsibilities' in desc_lower:
            # Description already has structure, use it
            parts.append(job_description)
        else:
            # Use full description
            parts.append(job_description)
    
    combined = '\n'.join(parts)
    
    # If too long, prioritize title + location + first part of description
    if len(combined) > max_chars:
        title_location = f"{job_title}\n{job_location if job_location else ''}".strip()
        remaining_chars = max_chars - len(title_location) - 10  # Reserve some space
        if remaining_chars > 0 and job_description:
            desc_part = job_description[:remaining_chars]
            # Try to cut at sentence boundary
            last_period = desc_part.rfind('.')
            if last_period > remaining_chars * 0.7:
                desc_part = desc_part[:last_period + 1]
            return f"{title_location}\n{desc_part}"
        return title_location[:max_chars]
    
    return combined

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
                
                # Format jobs for frontend - ส่งข้อมูลทั้งหมดเพื่อแสดงรายละเอียด
                result = []
                for job in jobs_data:
                    job_id = job.get("_id", job.get("id", job.get("job_id", "")))
                    job_obj = {
                        "id": job_id,
                        "job_id": job_id,  # Backward compatibility
                        "title": job.get("title", "N/A"),
                        "description": job.get("description", job.get("text_excerpt", "")),
                        "text_excerpt": job.get("text_excerpt", job.get("description", "")[:500]),
                        "created_at": job.get("created_at", ""),
                        # Include all metadata fields
                        "location": job.get("location", ""),
                        "department": job.get("department", ""),
                        "employment_type": job.get("employment_type", ""),
                        "experience_years": job.get("experience_years", ""),
                        "skills": job.get("skills", []),
                        "responsibilities": job.get("responsibilities", []),
                        "requirements": job.get("requirements", []),
                        # Include metadata object if exists
                        "metadata": job.get("metadata", {})
                    }
                    # If metadata exists, merge location and other fields from metadata
                    if job.get("metadata") and isinstance(job.get("metadata"), dict):
                        metadata = job.get("metadata")
                        if not job_obj["location"] and metadata.get("location"):
                            job_obj["location"] = metadata.get("location")
                        if not job_obj["department"] and metadata.get("department"):
                            job_obj["department"] = metadata.get("department")
                        if not job_obj["employment_type"] and metadata.get("employment_type"):
                            job_obj["employment_type"] = metadata.get("employment_type")
                        if not job_obj["experience_years"] and metadata.get("experience_years"):
                            job_obj["experience_years"] = metadata.get("experience_years")
                        if not job_obj["skills"] and metadata.get("skills"):
                            job_obj["skills"] = metadata.get("skills")
                        if not job_obj["responsibilities"] and metadata.get("responsibilities"):
                            job_obj["responsibilities"] = metadata.get("responsibilities")
                        if not job_obj["requirements"] and metadata.get("requirements"):
                            job_obj["requirements"] = metadata.get("requirements")
                    result.append(job_obj)
                
                print(f"Loaded {len(result)} jobs from S3: {jobs_prefix}")
                return response(200, {"jobs": result, "total": len(result)})
            except Exception as e:
                print(f"Error fetching jobs from S3: {str(e)}")
                return response(500, {"error": str(e), "jobs": [], "total": 0})

        # ---- get single job by ID from S3 ----
        if path.startswith("/api/jobs/") and path != "/api/jobs/list" and method == "GET":
            try:
                # Extract job_id from path (e.g., /api/jobs/job123)
                job_id = path.split("/api/jobs/")[-1]
                if not job_id:
                    return response(400, {"error": "job_id is required"})
                
                jobs_prefix = f"{RESUME_PREFIX}jobs/"
                # Try to find job file (could be {job_id}.json or in any .json file)
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
                            
                            # Check if this file contains the job we're looking for
                            if isinstance(job_data, dict):
                                job_file_id = job_data.get("_id", job_data.get("id", job_data.get("job_id", "")))
                                if job_file_id == job_id:
                                    # Format job data
                                    job_obj = {
                                        "id": job_file_id,
                                        "job_id": job_file_id,
                                        "title": job_data.get("title", "N/A"),
                                        "description": job_data.get("description", job_data.get("text_excerpt", "")),
                                        "text_excerpt": job_data.get("text_excerpt", job_data.get("description", "")[:500]),
                                        "created_at": job_data.get("created_at", ""),
                                        "location": job_data.get("location", ""),
                                        "department": job_data.get("department", ""),
                                        "employment_type": job_data.get("employment_type", ""),
                                        "experience_years": job_data.get("experience_years", ""),
                                        "skills": job_data.get("skills", []),
                                        "responsibilities": job_data.get("responsibilities", []),
                                        "requirements": job_data.get("requirements", []),
                                        "metadata": job_data.get("metadata", {}),
                                        "s3_key": s3_key  # Include S3 key for update
                                    }
                                    # Merge metadata fields
                                    if job_data.get("metadata") and isinstance(job_data.get("metadata"), dict):
                                        metadata = job_data.get("metadata")
                                        if not job_obj["location"] and metadata.get("location"):
                                            job_obj["location"] = metadata.get("location")
                                        if not job_obj["department"] and metadata.get("department"):
                                            job_obj["department"] = metadata.get("department")
                                        if not job_obj["employment_type"] and metadata.get("employment_type"):
                                            job_obj["employment_type"] = metadata.get("employment_type")
                                        if not job_obj["experience_years"] and metadata.get("experience_years"):
                                            job_obj["experience_years"] = metadata.get("experience_years")
                                        if not job_obj["skills"] and metadata.get("skills"):
                                            job_obj["skills"] = metadata.get("skills")
                                        if not job_obj["responsibilities"] and metadata.get("responsibilities"):
                                            job_obj["responsibilities"] = metadata.get("responsibilities")
                                        if not job_obj["requirements"] and metadata.get("requirements"):
                                            job_obj["requirements"] = metadata.get("requirements")
                                    return response(200, {"job": job_obj})
                            
                            elif isinstance(job_data, list):
                                # Check if list contains the job
                                for job in job_data:
                                    job_file_id = job.get("_id", job.get("id", job.get("job_id", "")))
                                    if job_file_id == job_id:
                                        # Format and return
                                        job_obj = {
                                            "id": job_file_id,
                                            "job_id": job_file_id,
                                            "title": job.get("title", "N/A"),
                                            "description": job.get("description", job.get("text_excerpt", "")),
                                            "text_excerpt": job.get("text_excerpt", job.get("description", "")[:500]),
                                            "created_at": job.get("created_at", ""),
                                            "location": job.get("location", ""),
                                            "department": job.get("department", ""),
                                            "employment_type": job.get("employment_type", ""),
                                            "experience_years": job.get("experience_years", ""),
                                            "skills": job.get("skills", []),
                                            "responsibilities": job.get("responsibilities", []),
                                            "requirements": job.get("requirements", []),
                                            "metadata": job.get("metadata", {}),
                                            "s3_key": s3_key
                                        }
                                        # Merge metadata fields
                                        if job.get("metadata") and isinstance(job.get("metadata"), dict):
                                            metadata = job.get("metadata")
                                            if not job_obj["location"] and metadata.get("location"):
                                                job_obj["location"] = metadata.get("location")
                                            if not job_obj["department"] and metadata.get("department"):
                                                job_obj["department"] = metadata.get("department")
                                            if not job_obj["employment_type"] and metadata.get("employment_type"):
                                                job_obj["employment_type"] = metadata.get("employment_type")
                                            if not job_obj["experience_years"] and metadata.get("experience_years"):
                                                job_obj["experience_years"] = metadata.get("experience_years")
                                            if not job_obj["skills"] and metadata.get("skills"):
                                                job_obj["skills"] = metadata.get("skills")
                                            if not job_obj["responsibilities"] and metadata.get("responsibilities"):
                                                job_obj["responsibilities"] = metadata.get("responsibilities")
                                            if not job_obj["requirements"] and metadata.get("requirements"):
                                                job_obj["requirements"] = metadata.get("requirements")
                                        return response(200, {"job": job_obj})
                        except Exception as e:
                            print(f"Error processing {s3_key}: {e}")
                            continue
                
                return response(404, {"error": f"Job {job_id} not found"})
            except Exception as e:
                print(f"Error fetching job from S3: {str(e)}")
                import traceback
                traceback.print_exc()
                return response(500, {"error": str(e)})

        # ---- update job in S3 (will trigger S3 event → auto update embedding in OpenSearch) ----
        if path.startswith("/api/jobs/") and path != "/api/jobs/list" and method in ["PUT", "POST"]:
            try:
                # Extract job_id from path (e.g., /api/jobs/job123)
                job_id = path.split("/api/jobs/")[-1]
                if not job_id:
                    return response(400, {"error": "job_id is required"})
                
                body = json.loads(event.get("body", "{}"))
                updated_job = body.get("job") or body
                
                if not updated_job:
                    return response(400, {"error": "job data is required"})
                
                # Ensure job_id matches
                updated_job["id"] = job_id
                updated_job["_id"] = job_id
                updated_job["job_id"] = job_id
                
                # Find existing job file in S3
                jobs_prefix = f"{RESUME_PREFIX}jobs/"
                found_s3_key = None
                existing_job_data = None
                
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
                            
                            # Check if this file contains the job we're looking for
                            if isinstance(job_data, dict):
                                job_file_id = job_data.get("_id", job_data.get("id", job_data.get("job_id", "")))
                                if job_file_id == job_id:
                                    found_s3_key = s3_key
                                    existing_job_data = job_data
                                    break
                            elif isinstance(job_data, list):
                                for job in job_data:
                                    job_file_id = job.get("_id", job.get("id", job.get("job_id", "")))
                                    if job_file_id == job_id:
                                        found_s3_key = s3_key
                                        existing_job_data = job_data
                                        break
                        except Exception as e:
                            print(f"Error processing {s3_key}: {e}")
                            continue
                    
                    if found_s3_key:
                        break
                
                if not found_s3_key:
                    # Create new file if not found
                    found_s3_key = f"{jobs_prefix}{job_id}.json"
                    existing_job_data = None
                
                # Prepare job data for S3 (preserve structure)
                # If existing file contains a list, keep it as list; otherwise use dict
                if existing_job_data is None:
                    # New file - use dict
                    job_to_save = updated_job
                elif isinstance(existing_job_data, list):
                    # Update job in list
                    job_to_save = existing_job_data.copy()
                    job_index = -1
                    for i, job in enumerate(job_to_save):
                        job_file_id = job.get("_id", job.get("id", job.get("job_id", "")))
                        if job_file_id == job_id:
                            job_index = i
                            break
                    if job_index >= 0:
                        job_to_save[job_index] = updated_job
                    else:
                        job_to_save.append(updated_job)
                else:
                    # Single job dict - replace it
                    job_to_save = updated_job
                
                # Save to S3
                s3.put_object(
                    Bucket=RESUME_BUCKET,
                    Key=found_s3_key,
                    Body=json.dumps(job_to_save, ensure_ascii=False, indent=2).encode('utf-8'),
                    ContentType='application/json'
                )
                
                print(f"Updated job {job_id} in S3: {found_s3_key}")
                print(f"S3 event will trigger Lambda to update embedding in OpenSearch automatically")
                
                return response(200, {
                    "message": f"Job {job_id} updated successfully in S3",
                    "job_id": job_id,
                    "s3_key": found_s3_key,
                    "note": "S3 event will trigger automatic embedding update in OpenSearch"
                })
                
            except Exception as e:
                print(f"Error updating job in S3: {str(e)}")
                import traceback
                traceback.print_exc()
                return response(500, {"error": str(e)})

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
                        
                        # Generate embedding if not present (include location in embedding)
                        if "embeddings" not in document or not document.get("embeddings"):
                            try:
                                # Include title, location, and description in embedding
                                job_title = document.get('title', '')
                                job_location = document.get('metadata', {}).get('location', '') if isinstance(document.get('metadata'), dict) else ''
                                job_description = document.get('description', '')
                                
                                # Use helper function to extract important info (prioritizes title, location, key parts of description)
                                full_text = extract_important_job_info(job_title, job_location, job_description, max_chars=2048)
                                
                                embedding_body = {
                                    "texts": [full_text],  # Already optimized by extract_important_job_info
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
                        
                        # Generate embedding using important information
                        try:
                            # Extract important information from resume (prioritizes contact, skills, experience, education)
                            important_text = extract_important_resume_info(resume_text, max_chars=2048)
                            
                            embedding_body = {
                                "texts": [important_text],  # Already optimized by extract_important_resume_info
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
                    # Extract important information from resume for embedding
                    important_text = extract_important_resume_info(resume_text, max_chars=2048)
                    
                    embedding_body = {
                        "texts": [important_text],  # Already optimized by extract_important_resume_info
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
                # Normalize scores based on actual score range
                all_scores = [hit.get("_score", 0.0) for hit in hits]
                max_score = max(all_scores) if all_scores else 1.0
                min_score = min(all_scores) if all_scores else 0.0
                score_range = max_score - min_score if max_score > min_score else 1.0
                
                for hit in hits:
                    source = hit.get("_source", {})
                    raw_score = hit.get("_score", 0.0)
                    # Normalize to 0-1 range based on actual min/max
                    if score_range > 0:
                        normalized_score = (raw_score - min_score) / score_range
                    else:
                        normalized_score = 1.0 if raw_score > 0 else 0.0
                    # Map to 30-90% range for more realistic scores (100% should be rare)
                    # This ensures scores are meaningful and not inflated
                    normalized_score = 0.3 + (normalized_score * 0.6)  # 30% to 90% range
                    # Cap at 95% to reserve 100% for truly perfect matches
                    normalized_score = min(0.95, normalized_score)
                    # Convert to percentage (30-95%)
                    vector_score_percent = normalized_score * 100.0
                    
                    all_candidates.append({
                        "job_id": hit.get("_id", ""),
                        "title": source.get("title", "N/A"),
                        "description": source.get("description", ""),
                        "text_excerpt": source.get("text_excerpt", ""),
                        "metadata": source.get("metadata", {}),
                        "vector_score": vector_score_percent,
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
                        f"{i+1}. **ตำแหน่งงาน:** {c.get('title', 'N/A')}\n   **สถานที่:** {c.get('metadata', {}).get('location', 'ไม่ระบุ')}\n   **รายละเอียด:** {c.get('text_excerpt', '')[:200]}..."
                        for i, c in enumerate(candidates)
                    ])
                    
                    rerank_prompt = f"""คุณเป็น AI ที่เชี่ยวชาญในการจับคู่ Resume กับ Job

**Resume Summary:**
{resume_summary}

**รายการตำแหน่งงาน (Jobs):**
{candidates_text}

**งานของคุณ:**
1. **สำคัญมาก:** วิเคราะห์และจัดอันดับ Top 3 ตำแหน่งงานที่เหมาะสมที่สุดกับ Resume นี้ โดยต้องพิจารณา:
   - **ตำแหน่งงาน (Job Title)**: ตำแหน่งงานนั้นเหมาะสมกับ Resume นี้หรือไม่
   - **สถานที่ (Location)**: ความเหมาะสมกับสถานที่ (ถ้า Resume มีข้อมูลสถานที่)
   - **Job Description**: ทักษะและประสบการณ์ที่ตรงกับ Job Description
2. ให้เหตุผลที่ละเอียดและยาว (4-6 ประโยค) ว่าทำไมถึงเหมาะหรือไม่เหมาะ โดย**ต้องระบุอย่างชัดเจน**:
   - **ตำแหน่งงาน (Job Title)**: Resume นี้เหมาะสมกับตำแหน่งงานนั้นหรือไม่ อย่างไร - **ต้องระบุชื่อตำแหน่งงานที่ชัดเจน**
   - **สถานที่ (Location)**: ความเหมาะสมกับสถานที่ - **ต้องระบุสถานที่ที่ชัดเจน** (ถ้ามีข้อมูลใน Resume หรือ Job)
   - ทักษะและประสบการณ์ที่ตรงกับ Job Description
   - ทักษะและประสบการณ์ที่ขาดหายไป
   - จุดแข็งและจุดอ่อน
   - ความเหมาะสมโดยรวม
3. ระบุจุดเด่น (highlighted_skills) และจุดที่ขาด (gaps) ถ้ามี
4. แนะนำคำถามสำหรับสัมภาษณ์ (recommended_questions_for_interview)
5. **สำคัญมาก:** ต้องจัดอันดับตำแหน่งงานทั้งหมดที่ให้มา ({len(candidates)} jobs) ไม่ใช่แค่บางอัน - ต้องมี candidate_index ครบทุก Job: 0, 1, 2, ... ถึง {len(candidates)-1}

**ข้อกำหนด:**
- **สำคัญมาก:** ต้องพิจารณา **ตำแหน่งงาน (Job Title)** และ **สถานที่ (Location)** เป็นปัจจัยหลักในการจัดอันดับ
  * ตำแหน่งงานที่เหมาะสมกับ Resume ควรได้คะแนนสูง
  * ตำแหน่งงานที่มีสถานที่ใกล้เคียงหรือเหมาะสมควรได้คะแนนเพิ่ม
- ห้ามสร้างข้อมูลที่ไม่มีในรายการ
- ถ้าข้อมูลไม่พอ ให้ระบุว่า "ข้อมูลไม่เพียงพอ"
- ใช้ภาษาไทยในการให้เหตุผล
- **สำคัญมาก:** rerank_score ต้องสอดคล้องกับ reasons ที่ให้มา
  * ถ้า reasons บอกว่า "เหมาะมาก" หรือ "มีประสบการณ์ตรง" หรือ "เหมาะสมกับตำแหน่งงาน" → rerank_score ควรสูง (0.8-1.0)
  * ถ้า reasons บอกว่า "เหมาะปานกลาง" หรือ "มีบางส่วน" → rerank_score ควรปานกลาง (0.5-0.8)
  * ถ้า reasons บอกว่า "ไม่เหมาะ" หรือ "ไม่มีประสบการณ์" หรือ "ไม่เหมาะสมกับตำแหน่งงาน" → rerank_score ควรต่ำ (0.0-0.5)
- คะแนน rerank_score ควรอยู่ระหว่าง 0.0-1.0
- **สำคัญมาก:** ต้องมี candidate_index ครบทุก Job: 0, 1, 2, ... ถึง {len(candidates)-1} - ห้ามขาด candidate_index ใดๆ

**รูปแบบผลลัพธ์ (JSON):**
{{
  "ranked_candidates": [
    {{
      "candidate_index": 0,
      "rerank_score": 0.95,
      "reasons": "เหตุผลที่ละเอียดและยาว (4-6 ประโยค) ระบุทักษะที่ตรงกับ Job, ทักษะที่ขาด, จุดแข็ง, จุดอ่อน, และความเหมาะสมโดยรวม",
      "highlighted_skills": ["skill1", "skill2"],
      "gaps": ["gap1"],
      "recommended_questions_for_interview": ["คำถาม1", "คำถาม2"]
    }},
    {{
      "candidate_index": 1,
      "rerank_score": 0.85,
      "reasons": "เหตุผลที่ละเอียดและยาว (4-6 ประโยค) ระบุทักษะที่ตรงกับ Job, ทักษะที่ขาด, จุดแข็ง, จุดอ่อน, และความเหมาะสมโดยรวม",
      "highlighted_skills": ["skill1"],
      "gaps": ["gap1"],
      "recommended_questions_for_interview": ["คำถาม1"]
    }},
    {{
      "candidate_index": 2,
      "rerank_score": 0.75,
      "reasons": "เหตุผลที่ละเอียดและยาว (4-6 ประโยค) ระบุทักษะที่ตรงกับ Job, ทักษะที่ขาด, จุดแข็ง, จุดอ่อน, และความเหมาะสมโดยรวม",
      "highlighted_skills": [],
      "gaps": [],
      "recommended_questions_for_interview": []
    }}
  ]
}}

**สำคัญมาก:** 
- candidate_index ต้องเป็น 0, 1, 2, ... ตามลำดับ (0 ถึง {len(candidates)-1})
- ต้องมี ranked_candidates ครบทุก Job ที่ให้มา ({len(candidates)} jobs)
- ห้ามขาด candidate_index ใดๆ

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
                        print(f"Nova Lite returned {len(ranked_list)} ranked candidates (expected {len(candidates)})")
                        
                        if ranked_list and len(ranked_list) > 0:
                            # CRITICAL: Check if Nova Lite returned all candidates
                            if len(ranked_list) < len(candidates):
                                print(f"WARNING (Mode A): Nova Lite returned only {len(ranked_list)} candidates but {len(candidates)} were expected. Adding missing candidates.")
                            
                            # Map reranked results back to candidates
                            processed_indices = set()
                            for item in ranked_list:
                                idx = item.get("candidate_index", 0)
                                if 0 <= idx < len(candidates) and idx not in processed_indices:
                                    candidate = candidates[idx]
                                    reasons = item.get("reasons", "ไม่มีข้อมูล")
                                    raw_rerank_score = float(item.get("rerank_score", 0.0))
                                    
                                    # Validate and adjust rerank_score to match reasons AND match_score (Mode A)
                                    # Get match_score as baseline (0-100% range, convert to 0-1)
                                    match_score_normalized = candidate["vector_score"] / 100.0  # Convert 0-100% to 0-1
                                    
                                    # Analyze reasons text
                                    reasons_lower = reasons.lower()
                                    
                                    # Check for strong negative indicators (should lower score)
                                    strong_negative = any(keyword in reasons_lower for keyword in [
                                        "ไม่เหมาะ", "ไม่มีประสบการณ์", "ไม่ตรง", "ไม่เกี่ยวข้อง", 
                                        "ไม่สามารถ", "ไม่พบ", "ไม่เหมาะสม", "ขาดประสบการณ์"
                                    ])
                                    
                                    # Check for strong positive indicators (should raise score)
                                    strong_positive = any(keyword in reasons_lower for keyword in [
                                        "เหมาะมาก", "มีประสบการณ์ตรง", "ตรงกับ", "เหมาะสมมาก", 
                                        "เชี่ยวชาญ", "ประสบการณ์เต็ม", "เหมาะอย่างมาก", "มีทักษะครบ"
                                    ])
                                    
                                    # Check for moderate positive indicators
                                    moderate_positive = any(keyword in reasons_lower for keyword in [
                                        "เหมาะสม", "มีทักษะ", "เหมาะ", "มีประสบการณ์", "ตรงกับบางส่วน"
                                    ])
                                    
                                    # Check for gaps mentioned (should slightly lower score)
                                    has_gaps = "ขาด" in reasons_lower or "จุดอ่อน" in reasons_lower or "ไม่พบ" in reasons_lower
                                    
                                    # Calculate adjusted score based on reasons AND match_score
                                    if strong_negative:
                                        # Force to low range (0.2-0.4), but consider match_score
                                        adjusted_rerank_score = min(0.4, max(0.2, match_score_normalized * 0.5))
                                        print(f"INFO (Mode A): Strong negative reasons detected. Adjusting rerank_score from {raw_rerank_score:.2f} to {adjusted_rerank_score:.2f} (based on match_score {candidate['vector_score']:.2f}%)")
                                    elif strong_positive:
                                        # Force to high range (0.7-1.0), but consider match_score
                                        adjusted_rerank_score = max(0.7, min(1.0, match_score_normalized * 1.2))
                                        print(f"INFO (Mode A): Strong positive reasons detected. Adjusting rerank_score from {raw_rerank_score:.2f} to {adjusted_rerank_score:.2f} (based on match_score {candidate['vector_score']:.2f}%)")
                                    elif moderate_positive:
                                        # Use match_score as base, but adjust slightly based on Nova Lite's score
                                        base_score = match_score_normalized
                                        # Blend Nova Lite's score (30%) with match_score (70%)
                                        adjusted_rerank_score = (base_score * 0.7) + (raw_rerank_score * 0.3)
                                        # If has gaps, reduce slightly
                                        if has_gaps:
                                            adjusted_rerank_score = adjusted_rerank_score * 0.9
                                        adjusted_rerank_score = max(0.3, min(0.9, adjusted_rerank_score))
                                        print(f"INFO (Mode A): Moderate positive reasons detected. Adjusting rerank_score from {raw_rerank_score:.2f} to {adjusted_rerank_score:.2f} (blended with match_score {candidate['vector_score']:.2f}%)")
                                    else:
                                        # Use match_score as primary, but blend with Nova Lite's score
                                        base_score = match_score_normalized
                                        adjusted_rerank_score = (base_score * 0.8) + (raw_rerank_score * 0.2)
                                        # If has gaps, reduce
                                        if has_gaps:
                                            adjusted_rerank_score = adjusted_rerank_score * 0.85
                                        adjusted_rerank_score = max(0.2, min(0.95, adjusted_rerank_score))
                                        print(f"INFO (Mode A): Neutral reasons. Adjusting rerank_score from {raw_rerank_score:.2f} to {adjusted_rerank_score:.2f} (based on match_score {candidate['vector_score']:.2f}%)")
                                    
                                    # Final validation: ensure rerank_score is reasonable
                                    adjusted_rerank_score = max(0.0, min(1.0, adjusted_rerank_score))
                                    
                                    results.append({
                                        "rank": len(results) + 1,
                                        "job_id": candidate["job_id"],
                                        "job_title": candidate["title"],
                                        "title": candidate["title"],
                                        "description": candidate["description"],
                                        "text_excerpt": candidate["text_excerpt"],
                                        "metadata": candidate["metadata"],
                                        "match_score": candidate["vector_score"],
                                        "rerank_score": adjusted_rerank_score,
                                        "score": candidate["raw_score"],
                                        "reasons": reasons,
                                        "highlighted_skills": item.get("highlighted_skills", []),
                                        "gaps": item.get("gaps", []),
                                        "recommended_questions_for_interview": item.get("recommended_questions_for_interview", []),
                                        "match_reason": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}"
                                    })
                                    processed_indices.add(idx)
                                else:
                                    if idx in processed_indices:
                                        print(f"WARNING (Mode A): candidate_index {idx} already processed, skipping duplicate")
                                    else:
                                        print(f"WARNING (Mode A): candidate_index {idx} is out of range (0-{len(candidates)-1})")
                            
                            # CRITICAL: If Nova Lite didn't return all candidates, add missing ones
                            if len(results) < len(candidates):
                                print(f"WARNING (Mode A): After mapping, only {len(results)} candidates mapped but {len(candidates)} were expected. Adding missing candidates.")
                                for i, candidate in enumerate(candidates):
                                    if i not in processed_indices:
                                        results.append({
                                            "rank": len(results) + 1,
                                            "job_id": candidate["job_id"],
                                            "job_title": candidate["title"],
                                            "title": candidate["title"],
                                            "description": candidate["description"],
                                            "text_excerpt": candidate["text_excerpt"],
                                            "metadata": candidate["metadata"],
                                            "match_score": candidate["vector_score"],
                                            "rerank_score": candidate["vector_score"] / 100.0,  # Convert to 0-1 range
                                            "score": candidate["raw_score"],
                                            "reasons": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}%",
                                            "highlighted_skills": [],
                                            "gaps": [],
                                            "recommended_questions_for_interview": [],
                                            "match_reason": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}"
                                        })
                            
                            # CRITICAL: Final check - ensure we have all candidates
                            if len(results) < len(candidates):
                                print(f"CRITICAL (Mode A): Still missing candidates after all processing. Expected {len(candidates)}, got {len(results)}. Adding missing candidates.")
                                processed_job_ids = {r.get('job_id') for r in results}
                                for candidate in candidates:
                                    if candidate.get('job_id') not in processed_job_ids:
                                        results.append({
                                            "rank": len(results) + 1,
                                            "job_id": candidate["job_id"],
                                            "job_title": candidate["title"],
                                            "title": candidate["title"],
                                            "description": candidate["description"],
                                            "text_excerpt": candidate["text_excerpt"],
                                            "metadata": candidate["metadata"],
                                            "match_score": candidate["vector_score"],
                                            "rerank_score": candidate["vector_score"] / 100.0,
                                            "score": candidate["raw_score"],
                                            "reasons": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}%",
                                            "highlighted_skills": [],
                                            "gaps": [],
                                            "recommended_questions_for_interview": [],
                                            "match_reason": f"{'Vector similarity' if use_vector_search else 'Text match'} score: {candidate['raw_score']:.4f}"
                                        })
                            
                            # CRITICAL: Sort results by rerank_score descending to ensure proper ranking
                            results.sort(key=lambda x: float(x.get("rerank_score", 0.0)), reverse=True)
                            # Update rank numbers after sorting
                            for idx, result in enumerate(results, 1):
                                result["rank"] = idx
                            
                            print(f"Reranked {len(results)} candidates using Nova Lite (sorted by rerank_score, expected {len(candidates)})")
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
                job_title = job_data.get("title", "")
                job_description = job_data.get("description", job_data.get("text_excerpt", ""))
                job_location = job_data.get("metadata", {}).get("location", "")
                # Get scoring_weights from job (could be in root or metadata)
                scoring_weights = job_data.get("scoring_weights") or job_data.get("metadata", {}).get("scoring_weights", {})
                
                if not job_description:
                    return response(400, {"error": "Job has no description"})
                
                # 2. Generate embedding for job (include title and location)
                job_embedding = None
                try:
                    # Use helper function to extract important info (prioritizes title, location, key parts of description)
                    embedding_text = extract_important_job_info(job_title, job_location, job_description, max_chars=5000)
                    
                    embedding_body = {
                        "texts": [embedding_text],  # Already optimized by extract_important_job_info
                        "input_type": "search_query"
                    }
                    embedding_response = bedrock_runtime.invoke_model(
                        modelId=BEDROCK_EMBEDDING_MODEL,
                        body=json.dumps(embedding_body)
                    )
                    embedding_result = json.loads(embedding_response["body"].read())
                    job_embedding = embedding_result.get("embeddings", [])[0]
                    print(f"Generated job embedding successfully (dimension: {len(job_embedding)})")
                except Exception as e:
                    print(f"Error generating embedding: {str(e)}")
                    return response(500, {"error": f"Failed to generate embedding: {str(e)}"})
                
                # 3. Vector search in resumes_index (use stored embeddings)
                search_url = f"https://{OPENSEARCH_HOST}/resumes_index/_search"
                search_res = None
                use_vector_search = False
                
                # Try vector search if embedding is available
                if job_embedding:
                    print(f"Job embedding available, attempting vector search...")
                    try:
                        # Build KNN search query
                        # OpenSearch KNN: use 'filter' inside 'knn' for filtering, not 'query'
                        search_query = {
                            "size": 100,  # Get top 100 resumes
                            "knn": {
                                "embeddings": {
                                    "vector": job_embedding,
                                    "k": 100  # Get top 100 for reranking
                                }
                            }
                        }
                        
                        # If resume_keys provided, filter to only those resumes
                        if resume_keys:
                            # Extract resume IDs from keys (remove path and extension)
                            resume_ids = []
                            resume_filenames = []
                            for key in resume_keys:
                                # Normalize key
                                if not key.startswith(RESUME_PREFIX):
                                    if key.startswith("Candidate/"):
                                        key = f"{RESUME_PREFIX}{key}"
                                    else:
                                        key = f"{RESUME_PREFIX}Candidate/{key}"
                                # Extract ID (filename without extension) - this is the _id in OpenSearch
                                resume_id = key.split("/")[-1].replace(".pdf", "").replace(".docx", "").replace(".txt", "")
                                resume_filename = key.split("/")[-1]
                                if resume_id:
                                    resume_ids.append(resume_id)
                                if resume_filename:
                                    resume_filenames.append(resume_filename)
                            
                            if resume_ids or resume_filenames:
                                # Add filter to KNN query (use 'filter' inside 'knn', not 'query')
                                filter_clauses = []
                                if resume_ids:
                                    # Filter by _id (document ID in OpenSearch)
                                    filter_clauses.append({
                                        "terms": {
                                            "_id": resume_ids
                                        }
                                    })
                                if resume_filenames:
                                    # Also filter by filename field
                                    filter_clauses.append({
                                        "terms": {
                                            "filename": resume_filenames
                                        }
                                    })
                                
                                if filter_clauses:
                                    # Use 'filter' inside 'knn' for OpenSearch KNN filtering
                                    if len(filter_clauses) == 1:
                                        search_query["knn"]["embeddings"]["filter"] = filter_clauses[0]
                                    else:
                                        search_query["knn"]["embeddings"]["filter"] = {
                                            "bool": {
                                                "should": filter_clauses,
                                                "minimum_should_match": 1
                                            }
                                        }
                                print(f"Filtering to {len(resume_ids)} specified resumes: IDs={resume_ids}, Filenames={resume_filenames}")
                        else:
                            print("No resume_keys provided, searching all resumes in index")
                        
                        search_res = requests.post(
                            search_url,
                            auth=opensearch_auth,
                            headers={"Content-Type": "application/json"},
                            json=search_query,
                            timeout=10
                        )
                        
                        if search_res.status_code == 200:
                            use_vector_search = True
                            print("Using vector search in resumes_index")
                        else:
                            try:
                                error_detail = search_res.text if hasattr(search_res, 'text') else (search_res.content.decode('utf-8') if search_res.content else 'No error detail')
                            except:
                                error_detail = str(search_res.content) if search_res.content else 'No error detail'
                            print(f"Vector search failed ({search_res.status_code}): {error_detail[:1000]}, trying fallback...")
                            print(f"Search query was: {json.dumps(search_query, indent=2)[:1000]}")
                    except Exception as e:
                        print(f"Vector search error: {str(e)}, trying fallback...")
                
                # 4. Process results from vector search or fallback
                results = []
                if use_vector_search:
                    # Use results from OpenSearch KNN search
                    hits = search_res.json().get("hits", {}).get("hits", [])
                    print(f"Found {len(hits)} resumes from vector search")
                    
                    # Check if we got enough results - if filtering and got less than requested, fallback to S3 processing
                    if resume_keys and len(hits) < len(resume_keys):
                        print(f"WARNING: Vector search returned only {len(hits)} resumes but {len(resume_keys)} were requested. Falling back to S3 processing for all resumes.")
                        use_vector_search = False  # Force fallback to process all resumes
                        results = []  # Clear results so fallback will process all resumes
                    else:
                        # Normalize scores based on actual score range
                        all_scores = [hit.get("_score", 0.0) for hit in hits]
                        max_score = max(all_scores) if all_scores else 1.0
                        min_score = min(all_scores) if all_scores else 0.0
                        score_range = max_score - min_score if max_score > min_score else 1.0
                        
                        for hit in hits:
                            source = hit.get("_source", {})
                            raw_score = hit.get("_score", 0.0)
                            # Normalize to 0-1 range based on actual min/max
                            if score_range > 0:
                                normalized_score = (raw_score - min_score) / score_range
                            else:
                                normalized_score = 1.0 if raw_score > 0 else 0.0
                            # Map to 30-90% range for more realistic scores (100% should be rare)
                            # This ensures scores are meaningful and not inflated
                            normalized_score = 0.3 + (normalized_score * 0.6)  # 30% to 90% range
                            # Cap at 95% to reserve 100% for truly perfect matches
                            normalized_score = min(0.95, normalized_score)
                            # Convert to percentage (30-95%)
                            vector_score_percent = normalized_score * 100.0
                            
                            resume_id = hit.get("_id", "")
                            # Get full text from source if available for reranking
                            resume_text = source.get("full_text", source.get("text_excerpt", ""))
                            results.append({
                                "resume_id": resume_id,
                                "resume_name": source.get("filename", resume_id),
                                "score": vector_score_percent,
                                "text_excerpt": source.get("text_excerpt", "")[:200] + "..." if len(source.get("text_excerpt", "")) > 200 else source.get("text_excerpt", ""),
                                "resume_text": resume_text  # Store full text for reranking
                            })
                        
                        print(f"Processed {len(results)} resumes from OpenSearch vector search")
                
                # If vector search didn't work or didn't return enough results, use fallback
                if not use_vector_search or (resume_keys and len(results) < len(resume_keys)):
                    # Fallback: if vector search failed or no embedding, process resumes from S3
                    if resume_keys:
                        # Process each resume and calculate similarity (process ALL resumes first)
                        print(f"Processing {len(resume_keys)} resumes from S3 (fallback mode)...")
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
                                    # Generate embedding for resume using important information
                                    # Extract important information (prioritizes contact, skills, experience, education)
                                    important_text = extract_important_resume_info(resume_text, max_chars=2048)
                                    
                                    resume_embed_body = {
                                        "texts": [important_text],  # Already optimized by extract_important_resume_info
                                        "input_type": "search_document"
                                    }
                                    print(f"  - Using important text: {len(important_text)} chars (original: {len(resume_text)} chars)")
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
                                    
                                    # Store raw similarity for later normalization
                                    results.append({
                                        "resume_id": resume_key,
                                        "resume_name": file_name,
                                        "raw_similarity": float(similarity),  # Store raw similarity
                                        "score": float(similarity) * 100.0,  # Temporary: will be normalized later
                                        "text_excerpt": resume_text[:200] + "..." if len(resume_text) > 200 else resume_text,
                                        "resume_text": resume_text  # Store full text for reranking
                                    })
                                    print(f"  - Successfully processed resume {file_name} with raw similarity {similarity:.6f}. Current results count: {len(results)}")
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
                    else:
                        return response(400, {"error": "resume_keys is required when vector search is not available"})
                
                # Normalize scores for fallback mode (if using cosine similarity)
                if not use_vector_search and results:
                    # Get all raw similarities
                    raw_similarities = [r.get("raw_similarity", r.get("score", 0.0) / 100.0) for r in results]
                    max_sim = max(raw_similarities) if raw_similarities else 1.0
                    min_sim = min(raw_similarities) if raw_similarities else 0.0
                    sim_range = max_sim - min_sim if max_sim > min_sim else 1.0
                    
                    # Normalize each result
                    for r in results:
                        raw_sim = r.get("raw_similarity", r.get("score", 0.0) / 100.0)
                        if sim_range > 0:
                            normalized = (raw_sim - min_sim) / sim_range
                        else:
                            normalized = 1.0 if raw_sim > 0 else 0.0
                        # Map to 30-90% range for more realistic scores (100% should be rare)
                        # This ensures scores are meaningful and not inflated
                        normalized = 0.3 + (normalized * 0.6)  # 30% to 90% range
                        # Cap at 95% to reserve 100% for truly perfect matches
                        normalized = min(0.95, normalized)
                        r["score"] = normalized * 100.0
                        # Remove raw_similarity from final result
                        r.pop("raw_similarity", None)
                
                # Sort by score descending (for both vector search and fallback)
                results.sort(key=lambda x: x["score"], reverse=True)
                
                print(f"=== Mode B: Processed {len(results)} resumes successfully ===")
                results_summary = [{'name': r['resume_name'], 'score': round(r['score'], 2)} for r in results]
                print(f"Results summary: {results_summary}")
                print(f"DEBUG: User selected {len(resume_keys)} resumes, processed {len(results)} results")
                
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
                
                # CRITICAL: If user selected specific resumes, ensure we have processed all of them
                # If we have fewer results than selected resumes, something went wrong
                if resume_keys and len(results) < len(resume_keys):
                    print(f"WARNING: Only processed {len(results)} resumes but user selected {len(resume_keys)} resumes!")
                    print(f"  Selected: {resume_keys}")
                    print(f"  Processed: {[r['resume_name'] for r in results]}")
                    # Continue anyway - use what we have
                
                # Select Top 3 based on embedding score (or all if less than 3)
                # IMPORTANT: Always select Top 3 from all processed results for reranking
                if len(results) >= 3:
                    top_results = results[:3]
                    print(f"Selected Top 3 resumes from {len(results)} total resumes based on embedding score")
                elif len(results) > 0:
                    # If we have less than 3, use all available
                    top_results = results
                    print(f"Selected all {len(top_results)} resumes from {len(results)} total resumes (less than 3 available)")
                else:
                    top_results = []
                    print(f"WARNING: No results to select for reranking")
                
                print(f"DEBUG: top_results count: {len(top_results)}, candidates will be: {len(top_results)}")
                
                # Prepare candidates for reranking (only Top 3)
                # Use full resume text for reranking (not just excerpt)
                candidates = []
                print(f"DEBUG: Preparing {len(top_results)} candidates for reranking")
                for idx, result in enumerate(top_results):
                    # Get full resume text if available, otherwise use excerpt
                    resume_full_text = result.get("resume_text", result.get("text_excerpt", ""))
                    candidates.append({
                        "resume_id": result["resume_id"],
                        "resume_name": result["resume_name"],
                        "text_excerpt": result.get("text_excerpt", ""),
                        "resume_text": resume_full_text[:3000] if resume_full_text else "",  # Limit to 3000 chars for rerank prompt
                        "vector_score": result["score"],
                        "raw_score": result["score"]
                    })
                    print(f"DEBUG: Added candidate {idx}: {result.get('resume_name', 'N/A')} (score: {result.get('score', 0):.2f})")
                
                print(f"DEBUG: Total candidates prepared: {len(candidates)}")
                
                # Rerank with Nova Lite v1
                reranked_results = []
                try:
                    print(f"Attempting reranking with Nova Lite ({BEDROCK_RERANK_MODEL})...")
                    
                    # Build prompt for reranking with full resume text
                    # Include job title and location in prompt
                    job_title_display = job_title if job_title else "ไม่ระบุ"
                    job_location_display = job_location if job_location else "ไม่ระบุ"
                    job_summary = job_description[:1000] + "..." if len(job_description) > 1000 else job_description
                    candidates_text = "\n\n".join([
                        f"=== Resume {i+1}: {c.get('resume_name', 'N/A')} ===\n{c.get('resume_text', c.get('text_excerpt', 'N/A'))}"
                        for i, c in enumerate(candidates)
                    ])
                    
                    # Build scoring weights section for prompt (if available)
                    scoring_weights_section = ""
                    if scoring_weights and isinstance(scoring_weights, dict) and len(scoring_weights) > 0:
                        weights_list = []
                        for category, weight in scoring_weights.items():
                            weights_list.append(f"  - **{category}**: {weight}%")
                        scoring_weights_section = f"""
**น้ำหนักการให้คะแนน (Scoring Weights) - ต้องใช้ตามนี้:**
{chr(10).join(weights_list)}

**สำคัญมาก:** ในการจัดอันดับและให้คะแนน rerank_score คุณต้องพิจารณาตามน้ำหนักที่กำหนดไว้ข้างต้น:
  - หมวดหมู่ที่มีน้ำหนักสูง (เช่น {max(scoring_weights.items(), key=lambda x: x[1])[0]} {max(scoring_weights.values())}%) ต้องให้ความสำคัญมากกว่า
  - หมวดหมู่ที่มีน้ำหนักต่ำ (เช่น {min(scoring_weights.items(), key=lambda x: x[1])[0]} {min(scoring_weights.values())}%) ให้ความสำคัญน้อยกว่า
  - คะแนน rerank_score ต้องสะท้อนถึงน้ำหนักที่กำหนดไว้
"""
                    
                    rerank_prompt = f"""คุณเป็น AI ที่เชี่ยวชาญในการจับคู่ Resume กับ Job

**ตำแหน่งงาน:** {job_title_display}
**สถานที่:** {job_location_display}
**Job Description:**
{job_summary}
{scoring_weights_section}
**รายการ Resume (Candidates):**
{candidates_text}

**งานของคุณ:**
1. **สำคัญมาก:** วิเคราะห์และจัดอันดับ Resume ทั้งหมดที่ให้มา ({len(candidates)} resumes) ตามความเหมาะสมกับ Job นี้ โดยต้องพิจารณา:
   - **ตำแหน่งงาน (Job Title)**: Resume ต้องเหมาะสมกับตำแหน่งงาน "{job_title_display}" นี้
   - **สถานที่ (Location)**: พิจารณาความเหมาะสมกับสถานที่ "{job_location_display}" (ถ้า Resume มีข้อมูลสถานที่)
   - **Job Description**: ทักษะและประสบการณ์ที่ตรงกับ Job Description
   {f"- **น้ำหนักการให้คะแนน**: ใช้ตามน้ำหนักที่กำหนดไว้ข้างต้น - หมวดหมู่ที่มีน้ำหนักสูงต้องให้ความสำคัญมากกว่า" if scoring_weights_section else ""}
2. ให้เหตุผลที่ละเอียดและยาว (4-6 ประโยค) ว่าทำไมถึงเหมาะหรือไม่เหมาะกับตำแหน่งงานนี้ โดย**ต้องระบุอย่างชัดเจน**:
   - **ตำแหน่งงาน (Job Title)**: Resume นี้เหมาะสมกับตำแหน่ง "{job_title_display}" หรือไม่ อย่างไร - **ต้องระบุชื่อตำแหน่งงาน "{job_title_display}" ในเหตุผล**
   - **สถานที่ (Location)**: ความเหมาะสมกับสถานที่ "{job_location_display}" - **ต้องระบุสถานที่ "{job_location_display}" ในเหตุผล** (ถ้ามีข้อมูลใน Resume หรือ Job)
   - ทักษะและประสบการณ์ที่ตรงกับ Job Description
   - ทักษะและประสบการณ์ที่ขาดหายไป
   - จุดแข็งและจุดอ่อนของ Resume นี้
   - ความเหมาะสมโดยรวมกับตำแหน่งงาน
3. ระบุจุดเด่น (highlighted_skills) และจุดที่ขาด (gaps) ถ้ามี
4. แนะนำคำถามสำหรับสัมภาษณ์ (recommended_questions_for_interview)
5. **สำคัญมาก:** ต้องจัดอันดับ Resume ทั้งหมดที่ให้มา ({len(candidates)} resumes) ไม่ใช่แค่บางอัน - ต้องมี candidate_index ครบทุก Resume: 0, 1, 2, ... ถึง {len(candidates)-1}

**ข้อกำหนด:**
- **สำคัญมาก:** ต้องพิจารณา **ตำแหน่งงาน (Job Title)** และ **สถานที่ (Location)** เป็นปัจจัยหลักในการจัดอันดับ
  * Resume ที่เหมาะสมกับตำแหน่งงาน "{job_title_display}" ควรได้คะแนนสูง
  * Resume ที่มีสถานที่ใกล้เคียงหรือเหมาะสมกับ "{job_location_display}" ควรได้คะแนนเพิ่ม
- ห้ามสร้างข้อมูลที่ไม่มีในรายการ
- ถ้าข้อมูลไม่พอ ให้ระบุว่า "ข้อมูลไม่เพียงพอ"
- ใช้ภาษาไทยในการให้เหตุผล
- **สำคัญมาก:** rerank_score ต้องสอดคล้องกับ reasons ที่ให้มา
  * ถ้า reasons บอกว่า "เหมาะมาก" หรือ "มีประสบการณ์ตรง" หรือ "เหมาะสมกับตำแหน่งงาน" → rerank_score ควรสูง (0.8-1.0)
  * ถ้า reasons บอกว่า "เหมาะปานกลาง" หรือ "มีบางส่วน" → rerank_score ควรปานกลาง (0.5-0.8)
  * ถ้า reasons บอกว่า "ไม่เหมาะ" หรือ "ไม่มีประสบการณ์" หรือ "ไม่เหมาะสมกับตำแหน่งงาน" → rerank_score ควรต่ำ (0.0-0.5)
- คะแนน rerank_score ควรอยู่ระหว่าง 0.0-1.0
- **สำคัญมาก:** ต้องมี candidate_index ครบทุก Resume: 0, 1, 2, ... ถึง {len(candidates)-1} - ห้ามขาด candidate_index ใดๆ

**รูปแบบผลลัพธ์ (JSON):**
{{
  "ranked_candidates": [
    {{
      "candidate_index": 0,
      "rerank_score": 0.95,
      "reasons": "เหตุผลที่ละเอียดและยาว (4-6 ประโยค) ระบุทักษะที่ตรงกับ Job, ทักษะที่ขาด, จุดแข็ง, จุดอ่อน, และความเหมาะสมโดยรวม",
      "highlighted_skills": ["skill1", "skill2"],
      "gaps": ["gap1"],
      "recommended_questions_for_interview": ["คำถาม1", "คำถาม2"]
    }},
    {{
      "candidate_index": 1,
      "rerank_score": 0.85,
      "reasons": "เหตุผลที่ละเอียดและยาว (4-6 ประโยค) ระบุทักษะที่ตรงกับ Job, ทักษะที่ขาด, จุดแข็ง, จุดอ่อน, และความเหมาะสมโดยรวม",
      "highlighted_skills": ["skill1"],
      "gaps": ["gap1"],
      "recommended_questions_for_interview": ["คำถาม1"]
    }},
    {{
      "candidate_index": 2,
      "rerank_score": 0.75,
      "reasons": "เหตุผลที่ละเอียดและยาว (4-6 ประโยค) ระบุทักษะที่ตรงกับ Job, ทักษะที่ขาด, จุดแข็ง, จุดอ่อน, และความเหมาะสมโดยรวม",
      "highlighted_skills": [],
      "gaps": [],
      "recommended_questions_for_interview": []
    }}
  ]
}}

**สำคัญมาก:** 
- candidate_index ต้องเป็น 0, 1, 2, ... ตามลำดับ (0 ถึง {len(candidates)-1})
- ต้องมี ranked_candidates ครบทุก Resume ที่ให้มา ({len(candidates)} candidates)
- ห้ามขาด candidate_index ใดๆ

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
                            "maxTokens": 5000,
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
                        print(f"Nova Lite returned {len(ranked_list)} ranked candidates (expected {len(candidates)})")
                        
                        if ranked_list and len(ranked_list) > 0:
                            # CRITICAL: Check if Nova Lite returned all candidates
                            if len(ranked_list) < len(candidates):
                                print(f"WARNING: Nova Lite returned only {len(ranked_list)} candidates but {len(candidates)} were expected. Using fallback to show all candidates.")
                                # Use fallback: show all candidates with vector scores
                                for i, candidate in enumerate(candidates, 1):
                                    reranked_results.append({
                                        "rank": i,
                                        "resume_id": candidate["resume_id"],
                                        "resume_name": candidate["resume_name"],
                                        "match_score": candidate["vector_score"],
                                        "rerank_score": candidate["vector_score"] / 100.0,  # Convert to 0-1 range
                                        "score": candidate["raw_score"],
                                        "reasons": f"Vector similarity score: {candidate['raw_score']:.4f}%",
                                        "highlighted_skills": [],
                                        "gaps": [],
                                        "recommended_questions_for_interview": [],
                                        "text_excerpt": candidate.get("text_excerpt", "")
                                    })
                                print(f"Using fallback: Added all {len(candidates)} candidates to results")
                            else:
                                # Nova Lite returned all candidates - map them properly
                                # Sort ranked_list by rerank_score descending to get proper ranking
                                ranked_list.sort(key=lambda x: float(x.get("rerank_score", 0.0)), reverse=True)
                                
                                # Map reranked results back to candidates
                                processed_indices = set()
                                for item in ranked_list:
                                    idx = item.get("candidate_index", 0)
                                    print(f"Processing ranked candidate index: {idx}, total candidates: {len(candidates)}")
                                    if 0 <= idx < len(candidates) and idx not in processed_indices:
                                        candidate = candidates[idx]
                                        reasons = item.get("reasons", "ไม่มีข้อมูล")
                                        raw_rerank_score = float(item.get("rerank_score", 0.0))
                                        
                                        # Validate and adjust rerank_score to match reasons AND match_score
                                        # Get match_score as baseline (0-100% range, convert to 0-1)
                                        match_score_normalized = candidate["vector_score"] / 100.0  # Convert 0-100% to 0-1
                                        
                                        # Analyze reasons text
                                        reasons_lower = reasons.lower()
                                        
                                        # Check for strong negative indicators (should lower score)
                                        strong_negative = any(keyword in reasons_lower for keyword in [
                                            "ไม่เหมาะ", "ไม่มีประสบการณ์", "ไม่ตรง", "ไม่เกี่ยวข้อง", 
                                            "ไม่สามารถ", "ไม่พบ", "ไม่เหมาะสม", "ขาดประสบการณ์"
                                        ])
                                        
                                        # Check for strong positive indicators (should raise score)
                                        strong_positive = any(keyword in reasons_lower for keyword in [
                                            "เหมาะมาก", "มีประสบการณ์ตรง", "ตรงกับ", "เหมาะสมมาก", 
                                            "เชี่ยวชาญ", "ประสบการณ์เต็ม", "เหมาะอย่างมาก", "มีทักษะครบ"
                                        ])
                                        
                                        # Check for moderate positive indicators
                                        moderate_positive = any(keyword in reasons_lower for keyword in [
                                            "เหมาะสม", "มีทักษะ", "เหมาะ", "มีประสบการณ์", "ตรงกับบางส่วน"
                                        ])
                                        
                                        # Check for gaps mentioned (should slightly lower score)
                                        has_gaps = "ขาด" in reasons_lower or "จุดอ่อน" in reasons_lower or "ไม่พบ" in reasons_lower
                                        
                                        # Calculate adjusted score based on reasons AND match_score
                                        # Start with Nova Lite's rerank_score, but adjust based on consistency
                                        
                                        # If reasons are strongly negative, score should be low
                                        if strong_negative:
                                            # Force to low range (0.2-0.4), but consider match_score
                                            adjusted_rerank_score = min(0.4, max(0.2, match_score_normalized * 0.5))
                                            print(f"INFO: Strong negative reasons detected. Adjusting rerank_score from {raw_rerank_score:.2f} to {adjusted_rerank_score:.2f} (based on match_score {candidate['vector_score']:.2f}%)")
                                        # If reasons are strongly positive, score should be high
                                        elif strong_positive:
                                            # Force to high range (0.7-1.0), but consider match_score
                                            adjusted_rerank_score = max(0.7, min(1.0, match_score_normalized * 1.2))
                                            print(f"INFO: Strong positive reasons detected. Adjusting rerank_score from {raw_rerank_score:.2f} to {adjusted_rerank_score:.2f} (based on match_score {candidate['vector_score']:.2f}%)")
                                        # If reasons are moderately positive
                                        elif moderate_positive:
                                            # Use match_score as base, but adjust slightly based on Nova Lite's score
                                            base_score = match_score_normalized
                                            # Blend Nova Lite's score (30%) with match_score (70%)
                                            adjusted_rerank_score = (base_score * 0.7) + (raw_rerank_score * 0.3)
                                            # If has gaps, reduce slightly
                                            if has_gaps:
                                                adjusted_rerank_score = adjusted_rerank_score * 0.9
                                            adjusted_rerank_score = max(0.3, min(0.9, adjusted_rerank_score))
                                            print(f"INFO: Moderate positive reasons detected. Adjusting rerank_score from {raw_rerank_score:.2f} to {adjusted_rerank_score:.2f} (blended with match_score {candidate['vector_score']:.2f}%)")
                                        # If reasons are neutral or unclear, use match_score as primary indicator
                                        else:
                                            # Use match_score as primary, but blend with Nova Lite's score
                                            base_score = match_score_normalized
                                            adjusted_rerank_score = (base_score * 0.8) + (raw_rerank_score * 0.2)
                                            # If has gaps, reduce
                                            if has_gaps:
                                                adjusted_rerank_score = adjusted_rerank_score * 0.85
                                            adjusted_rerank_score = max(0.2, min(0.95, adjusted_rerank_score))
                                            print(f"INFO: Neutral reasons. Adjusting rerank_score from {raw_rerank_score:.2f} to {adjusted_rerank_score:.2f} (based on match_score {candidate['vector_score']:.2f}%)")
                                        
                                        # Final validation: ensure rerank_score is reasonable
                                        adjusted_rerank_score = max(0.0, min(1.0, adjusted_rerank_score))
                                        
                                        reranked_results.append({
                                            "rank": len(reranked_results) + 1,
                                            "resume_id": candidate["resume_id"],
                                            "resume_name": candidate["resume_name"],
                                            "match_score": candidate["vector_score"],
                                            "rerank_score": adjusted_rerank_score,
                                            "score": candidate["raw_score"],
                                            "reasons": reasons,
                                            "highlighted_skills": item.get("highlighted_skills", []),
                                            "gaps": item.get("gaps", []),
                                            "recommended_questions_for_interview": item.get("recommended_questions_for_interview", []),
                                            "text_excerpt": candidate.get("text_excerpt", "")
                                        })
                                        processed_indices.add(idx)
                                    else:
                                        if idx in processed_indices:
                                            print(f"WARNING: candidate_index {idx} already processed, skipping duplicate")
                                        else:
                                            print(f"WARNING: candidate_index {idx} is out of range (0-{len(candidates)-1})")
                                
                                # CRITICAL: If Nova Lite didn't return all candidates, add missing ones
                                if len(reranked_results) < len(candidates):
                                    print(f"WARNING: After mapping, only {len(reranked_results)} candidates mapped but {len(candidates)} were expected. Adding missing candidates.")
                                    for i, candidate in enumerate(candidates):
                                        if i not in processed_indices:
                                            reranked_results.append({
                                                "rank": len(reranked_results) + 1,
                                                "resume_id": candidate["resume_id"],
                                                "resume_name": candidate["resume_name"],
                                                "match_score": candidate["vector_score"],
                                                "rerank_score": candidate["vector_score"] / 100.0,  # Convert to 0-1 range
                                                "score": candidate["raw_score"],
                                                "reasons": f"Vector similarity score: {candidate['raw_score']:.4f}%",
                                                "highlighted_skills": [],
                                                "gaps": [],
                                                "recommended_questions_for_interview": [],
                                                "text_excerpt": candidate.get("text_excerpt", "")
                                            })
                                
                                print(f"Reranked {len(reranked_results)} candidates using Nova Lite (expected {len(candidates)})")
                            
                            # CRITICAL: Final check - ensure we have all candidates
                            # Only add missing candidates if we actually have fewer than expected
                            if len(reranked_results) < len(candidates):
                                print(f"CRITICAL: Still missing candidates after all processing. Expected {len(candidates)}, got {len(reranked_results)}. Checking for missing candidates...")
                                processed_names = {r.get('resume_name') for r in reranked_results}
                                missing_count = 0
                                for i, candidate in enumerate(candidates):
                                    if candidate.get('resume_name') not in processed_names:
                                        missing_count += 1
                                        reranked_results.append({
                                            "rank": len(reranked_results) + 1,
                                            "resume_id": candidate["resume_id"],
                                            "resume_name": candidate["resume_name"],
                                            "match_score": candidate["vector_score"],
                                            "rerank_score": candidate["vector_score"] / 100.0,
                                            "score": candidate["raw_score"],
                                            "reasons": f"Vector similarity score: {candidate['raw_score']:.4f}%",
                                            "highlighted_skills": [],
                                            "gaps": [],
                                            "recommended_questions_for_interview": [],
                                            "text_excerpt": candidate.get("text_excerpt", "")
                                        })
                                if missing_count > 0:
                                    print(f"Added {missing_count} missing candidates via fallback")
                                else:
                                    print(f"WARNING: len(reranked_results) < len(candidates) but no missing candidates found! This is a bug.")
                            else:
                                print(f"SUCCESS: reranked_results ({len(reranked_results)}) >= candidates ({len(candidates)}). All candidates present.")
                            
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
                    print(f"All results: {[r.get('resume_name', 'N/A') for r in reranked_results]}")
                
                # CRITICAL: Ensure we return all reranked results (should be at least as many as candidates)
                # Only add missing candidates if we actually have fewer than expected AND they are truly missing
                if len(reranked_results) < len(candidates):
                    print(f"CRITICAL ERROR: reranked_results ({len(reranked_results)}) < candidates ({len(candidates)}). Checking for missing candidates...")
                    # Force add missing candidates (only if truly missing)
                    processed_names = {r.get('resume_name') for r in reranked_results}
                    missing_count = 0
                    for candidate in candidates:
                        if candidate.get('resume_name') not in processed_names:
                            missing_count += 1
                            reranked_results.append({
                                "rank": len(reranked_results) + 1,
                                "resume_id": candidate["resume_id"],
                                "resume_name": candidate["resume_name"],
                                "match_score": candidate["vector_score"],
                                "rerank_score": candidate["vector_score"] / 100.0,
                                "score": candidate["raw_score"],
                                "reasons": f"Vector similarity score: {candidate['raw_score']:.4f}",
                                "highlighted_skills": [],
                                "gaps": [],
                                "recommended_questions_for_interview": [],
                                "text_excerpt": candidate.get("text_excerpt", "")
                            })
                    if missing_count > 0:
                        print(f"Added {missing_count} missing candidates via fallback")
                    else:
                        print(f"WARNING: len(reranked_results) < len(candidates) but no missing candidates found! This is a bug. Skipping fallback.")
                else:
                    print(f"SUCCESS: reranked_results ({len(reranked_results)}) >= candidates ({len(candidates)}). No fallback needed.")
                
                # Remove duplicates if any (should not happen, but just in case)
                # BUT: Only remove duplicates if we have MORE than expected candidates
                # If we have exactly len(candidates), don't remove duplicates (they might be needed)
                seen_names = set()
                unique_results = []
                for r in reranked_results:
                    name = r.get('resume_name')
                    if name not in seen_names:
                        seen_names.add(name)
                        unique_results.append(r)
                    else:
                        print(f"WARNING: Duplicate resume found: {name}, skipping")
                
                # Only use unique_results if we have MORE than expected candidates
                # If we have exactly len(candidates) or less, keep all results (even if duplicates)
                if len(unique_results) < len(reranked_results) and len(reranked_results) > len(candidates):
                    print(f"WARNING: Removed {len(reranked_results) - len(unique_results)} duplicate resumes")
                    reranked_results = unique_results
                elif len(unique_results) == len(candidates):
                    # If unique results equals candidates, use unique (this is good)
                    reranked_results = unique_results
                    print(f"Using unique results: {len(unique_results)} candidates")
                
                # CRITICAL: Final check - ensure we have at least len(candidates) results
                # If we have fewer, add missing candidates from the original candidates list
                if len(reranked_results) < len(candidates):
                    print(f"CRITICAL: After duplicate removal, only {len(reranked_results)} results but {len(candidates)} expected. Adding missing candidates.")
                    existing_names = {r.get('resume_name') for r in reranked_results}
                    for candidate in candidates:
                        if candidate.get('resume_name') not in existing_names:
                            reranked_results.append({
                                "rank": len(reranked_results) + 1,
                                "resume_id": candidate["resume_id"],
                                "resume_name": candidate["resume_name"],
                                "match_score": candidate["vector_score"],
                                "rerank_score": candidate["vector_score"] / 100.0,
                                "score": candidate["raw_score"],
                                "reasons": f"Vector similarity score: {candidate['raw_score']:.4f}%",
                                "highlighted_skills": [],
                                "gaps": [],
                                "recommended_questions_for_interview": [],
                                "text_excerpt": candidate.get("text_excerpt", "")
                            })
                            print(f"Added missing candidate: {candidate.get('resume_name', 'N/A')}")
                
                # CRITICAL: Sort reranked_results by rerank_score descending to ensure proper ranking
                reranked_results.sort(key=lambda x: float(x.get("rerank_score", 0.0)), reverse=True)
                # Update rank numbers after sorting
                for idx, result in enumerate(reranked_results, 1):
                    result["rank"] = idx
                
                # FINAL VERIFICATION: Ensure we return exactly len(candidates) results (or all if less than 3)
                # Limit to top len(candidates) if we have more
                if len(reranked_results) > len(candidates):
                    print(f"WARNING: Have {len(reranked_results)} results but only need {len(candidates)}. Limiting to top {len(candidates)}.")
                    reranked_results = reranked_results[:len(candidates)]
                    # Update ranks again
                    for idx, result in enumerate(reranked_results, 1):
                        result["rank"] = idx
                
                print(f"Final reranked_results count: {len(reranked_results)} (expected: {len(candidates)})")
                print(f"Final reranked_results sorted by rerank_score: {[(r.get('resume_name', 'N/A'), r.get('rerank_score', 0.0)) for r in reranked_results]}")
                
                # ABSOLUTE FINAL CHECK: If still not enough, force add from candidates
                if len(reranked_results) < len(candidates):
                    print(f"ABSOLUTE FINAL CHECK: Only {len(reranked_results)} results, forcing to add all {len(candidates)} candidates")
                    final_names = {r.get('resume_name') for r in reranked_results}
                    for candidate in candidates:
                        if candidate.get('resume_name') not in final_names:
                            reranked_results.append({
                                "rank": len(reranked_results) + 1,
                                "resume_id": candidate["resume_id"],
                                "resume_name": candidate["resume_name"],
                                "match_score": candidate["vector_score"],
                                "rerank_score": candidate["vector_score"] / 100.0,
                                "score": candidate["raw_score"],
                                "reasons": f"Vector similarity score: {candidate['raw_score']:.4f}%",
                                "highlighted_skills": [],
                                "gaps": [],
                                "recommended_questions_for_interview": [],
                                "text_excerpt": candidate.get("text_excerpt", "")
                            })
                    # Re-sort and re-rank
                    reranked_results.sort(key=lambda x: float(x.get("rerank_score", 0.0)), reverse=True)
                    for idx, result in enumerate(reranked_results, 1):
                        result["rank"] = idx
                
                return response(200, {
                    "query": {
                        "job_id": job_id,
                        "job_description": job_description[:100] + "..." if len(job_description) > 100 else job_description
                    },
                    "results": reranked_results,
                    "total": len(reranked_results)
                })
            except Exception as e:
                print(f"Error in search_by_job: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return response(500, {"error": str(e)})

        return response(404, {"error": "Not found"})

    # =====================================================
    # 2) S3 EVENT → index jobs/resumes with embeddings (AUTO)
    # =====================================================
    if "Records" in event:
        jobs_processed = 0
        resumes_processed = 0
        
        for record in event["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

            print(f"Processing S3 event: bucket={bucket}, key={key}")

            # Check if it's a job file (JSON in jobs/ folder)
            if key.startswith(f"{RESUME_PREFIX}jobs/") and key.endswith('.json'):
                try:
                    obj = s3.get_object(Bucket=bucket, Key=key)
                    jobs_data = json.loads(obj["Body"].read().decode("utf-8"))
                    
                    if isinstance(jobs_data, dict):
                        jobs_data = [jobs_data]
                    elif not isinstance(jobs_data, list):
                        print(f"Skipping {key}: Invalid format")
                        continue

                    for job_data in jobs_data:
                        job_id = job_data.get("_id") or job_data.get("job_id") or job_data.get("id")
                        
                        if not job_id:
                            print(f"Skipping job: no ID found")
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
                            for meta_key in ["department", "location", "employment_type", "experience_years", "skills", "responsibilities", "requirements"]:
                                if meta_key in document:
                                    metadata[meta_key] = document[meta_key]
                            document["metadata"] = metadata

                        # ALWAYS generate embedding (auto-update when file changes)
                        try:
                            job_title = document.get('title', '')
                            job_location = document.get('metadata', {}).get('location', '') if isinstance(document.get('metadata'), dict) else ''
                            job_description = document.get('description', '')
                            
                            # Use helper function to extract important info
                            full_text = extract_important_job_info(job_title, job_location, job_description, max_chars=2048)
                            
                            embedding_body = {
                                "texts": [full_text],
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

                        # Index to OpenSearch (jobs_index)
                        index_doc_url = f"https://{OPENSEARCH_HOST}/jobs_index/_doc/{job_id}"
                        index_res = requests.put(
                            index_doc_url,
                            auth=opensearch_auth,
                            headers={"Content-Type": "application/json"},
                            json=document,
                            timeout=10
                        )

                        if index_res.status_code in [200, 201]:
                            jobs_processed += 1
                            print(f"Indexed job {job_id} with embedding")
                        else:
                            print(f"Failed to index job {job_id}: {index_res.status_code} - {index_res.text}")

                except Exception as e:
                    print(f"Error processing job file {key}: {e}")
                    import traceback
                    traceback.print_exc()

            # Check if it's a resume file (PDF/TXT in Candidate/ folder)
            elif key.startswith(f"{RESUME_PREFIX}Candidate/") and (key.endswith('.pdf') or key.endswith('.txt')):
                try:
                    # Extract resume_id from key
                    resume_id = key.split("/")[-1].replace(".pdf", "").replace(".docx", "").replace(".txt", "")
                    if not resume_id:
                        resume_id = key.replace("/", "_").replace(".", "_")

                    print(f"Processing resume: {key} (ID: {resume_id})")

                    # Get file from S3
                    file_obj = s3.get_object(Bucket=bucket, Key=key)
                    file_content = file_obj["Body"].read()
                    file_name = key.split("/")[-1]

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
                        continue

                    # Prepare document
                    document = {
                        "id": resume_id,
                        "filename": file_name,
                        "full_text": resume_text,
                        "text_excerpt": resume_text[:500],
                        "metadata": {
                            "s3_key": key,
                            "file_size": len(file_content)
                        }
                    }

                    # ALWAYS generate embedding (auto-update when file changes)
                    try:
                        # Extract important information from resume
                        important_text = extract_important_resume_info(resume_text, max_chars=2048)
                        
                        embedding_body = {
                            "texts": [important_text],
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

                    # Index to OpenSearch (resumes_index)
                    index_doc_url = f"https://{OPENSEARCH_HOST}/resumes_index/_doc/{resume_id}"
                    index_res = requests.put(
                        index_doc_url,
                        auth=opensearch_auth,
                        headers={"Content-Type": "application/json"},
                        json=document,
                        timeout=10
                    )

                    if index_res.status_code in [200, 201]:
                        resumes_processed += 1
                        print(f"Indexed resume {resume_id} with embedding")
                    else:
                        print(f"Failed to index resume {resume_id}: {index_res.status_code} - {index_res.text}")

                except Exception as e:
                    print(f"Error processing resume file {key}: {e}")
                    import traceback
                    traceback.print_exc()

        return response(200, {
            "message": f"Processed S3 events successfully",
            "jobs_processed": jobs_processed,
            "resumes_processed": resumes_processed
        })

    # =====================================================
    return response(400, {"error": "Unknown event"})
