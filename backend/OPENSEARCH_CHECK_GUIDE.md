# OpenSearch Index Check Guide

## วิธีตรวจสอบ OpenSearch Indices

### วิธีที่ 1: ใช้ Python Script

```powershell
cd backend
python check_opensearch_indices.py [resume_id] [--skip-ssl]
```

**ตัวอย่าง:**
```powershell
python check_opensearch_indices.py c3a74273-816f-4dd6-bd50-24e8d8c6d8f7
```

### วิธีที่ 2: ใช้ PowerShell Script

```powershell
cd backend
.\check_opensearch_indices.ps1 -ResumeId "c3a74273-816f-4dd6-bd50-24e8d8c6d8f7" -IndexName "resumes_index"
```

### วิธีที่ 3: ใช้ AWS CLI (แนะนำ)

#### 1. เช็ค indices ที่มีอยู่

```bash
# List all indices
aws es describe-elasticsearch-domain \
  --domain-name resume-search-dev \
  --region ap-southeast-2

# หรือใช้ curl กับ AWS signing
aws es describe-elasticsearch-domain \
  --domain-name resume-search-dev \
  --region ap-southeast-2 \
  --query 'DomainStatus.Endpoint' \
  --output text
```

#### 2. เช็คว่า resume_id อยู่ใน OpenSearch ไหม

**ใช้ AWS CLI + curl:**

```bash
# Get OpenSearch endpoint
ENDPOINT=$(aws es describe-elasticsearch-domain \
  --domain-name resume-search-dev \
  --region ap-southeast-2 \
  --query 'DomainStatus.Endpoint' \
  --output text)

# Search for resume
curl -X POST "https://${ENDPOINT}/resumes_index/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "term": {
        "resume_id.keyword": "c3a74273-816f-4dd6-bd50-24e8d8c6d8f7"
      }
    }
  }' \
  --aws-sigv4 "aws:amz:ap-southeast-2:es"
```

**หรือใช้ match query:**

```bash
curl -X POST "https://${ENDPOINT}/resumes_index/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "match": {
        "resume_id": "c3a74273-816f-4dd6-bd50-24e8d8c6d8f7"
      }
    }
  }' \
  --aws-sigv4 "aws:amz:ap-southeast-2:es"
```

#### 3. เช็ค vector fields

```bash
curl -X POST "https://${ENDPOINT}/resumes_index/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "_source": ["resume_id", "embedding", "embeddings", "vector", "resume_vector", "content"],
    "query": {
      "match_all": {}
    },
    "size": 1
  }' \
  --aws-sigv4 "aws:amz:ap-southeast-2:es"
```

#### 4. เช็ค mapping

```bash
curl -X GET "https://${ENDPOINT}/resumes_index/_mapping" \
  --aws-sigv4 "aws:amz:ap-southeast-2:es"
```

#### 5. ทดสอบ vector search

```bash
# Create dummy vector (1536 dimensions)
DUMMY_VECTOR=$(python -c "print([0.01]*1536)")

curl -X POST "https://${ENDPOINT}/resumes_index/_search" \
  -H "Content-Type: application/json" \
  -d "{
    \"size\": 3,
    \"query\": {
      \"knn\": {
        \"embeddings\": {
          \"vector\": $DUMMY_VECTOR,
          \"k\": 3
        }
      }
    }
  }" \
  --aws-sigv4 "aws:amz:ap-southeast-2:es"
```

### วิธีที่ 4: ใช้ Python requests กับ AWS signing

```python
import requests
from requests_aws4auth import AWS4Auth
import boto3

# Get credentials
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    'ap-southeast-2',
    'es',
    session_token=credentials.token
)

endpoint = "https://search-resume-search-dev-xxx.ap-southeast-2.es.amazonaws.com"

# 1. List indices
response = requests.get(f"{endpoint}/_cat/indices?v", auth=awsauth, verify=False)
print(response.text)

# 2. Search for resume
search_body = {
    "query": {
        "term": {
            "resume_id.keyword": "c3a74273-816f-4dd6-bd50-24e8d8c6d8f7"
        }
    }
}
response = requests.post(
    f"{endpoint}/resumes_index/_search",
    json=search_body,
    auth=awsauth,
    verify=False
)
print(response.json())

# 3. Check mapping
response = requests.get(
    f"{endpoint}/resumes_index/_mapping",
    auth=awsauth,
    verify=False
)
print(response.json())
```

## การแปลผล

### ✅ พร้อม search แล้ว
- `hits.total.value > 0` → resume อยู่ใน OpenSearch
- มี field `embedding` หรือ `embeddings` ใน document
- มี field type `knn_vector` หรือ `dense_vector` ใน mapping

### ❌ ยังไม่ index
- `hits.total.value = 0` → resume ยังไม่ถูก index

### ❌ index ผิด field
- ไม่มี field `embedding` หรือ `embeddings` ใน document

### ❌ mapping vector ผิด
- ไม่มี field type `knn_vector` หรือ `dense_vector` ใน mapping

## แก้ปัญหา SSL Certificate Error

ถ้าเจอ SSL certificate error:

1. **ใช้ `verify=False` ใน requests:**
   ```python
   requests.get(url, auth=awsauth, verify=False)
   ```

2. **หรือใช้ AWS CLI แทน curl**

3. **หรือ configure SSL certificates อย่างถูกต้อง**

## ตัวอย่างผลลัพธ์

### ✅ พบ resume
```json
{
  "hits": {
    "total": {
      "value": 1
    },
    "hits": [
      {
        "_source": {
          "resume_id": "c3a74273-816f-4dd6-bd50-24e8d8c6d8f7",
          "embeddings": [0.01, 0.02, ...],
          "content": "..."
        }
      }
    ]
  }
}
```

### ❌ ไม่พบ resume
```json
{
  "hits": {
    "total": {
      "value": 0
    }
  }
}
```

### ✅ Vector mapping
```json
{
  "resumes_index": {
    "mappings": {
      "properties": {
        "embeddings": {
          "type": "knn_vector",
          "dimension": 1536
        }
      }
    }
  }
}
```

