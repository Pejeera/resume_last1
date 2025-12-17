# 🔍 API Gateway → Lambda → FastAPI (Mangum) Event Format Analysis

## 📋 Checklist การตรวจสอบ

### ✅ 1. Lambda Handler Configuration

**สถานะ: ✅ ถูกต้อง**

```python
# lambda_function.py
handler = Mangum(app, lifespan="off")
```

- Handler name: `lambda_function.handler` ✅
- Mangum version: รองรับทั้ง REST API v1 และ HTTP API v2 ✅
- Lifespan: ปิดแล้ว (เหมาะกับ Lambda) ✅

---

### ✅ 2. FastAPI Routes Configuration

**สถานะ: ✅ ถูกต้อง**

| Route | Method | FastAPI Definition | Status |
|-------|--------|-------------------|--------|
| `/api/health` | GET | `@router.get("/health")` + prefix `/api` | ✅ |
| `/api/jobs/list` | GET | `@router.get("/list")` + prefix `/api/jobs` | ✅ |
| `/api/jobs/create` | POST | `@router.post("/create")` + prefix `/api/jobs` | ✅ |

**FastAPI App Setup:**
```python
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
```

---

### ⚠️ 3. API Gateway Type Detection

**สถานะ: ⚠️ ต้องตรวจสอบ**

**สาเหตุที่เป็นไปได้ของ 405:**

#### A. **REST API (v1) - Lambda Proxy Integration**
- Event format: `httpMethod`, `path`, `resource`
- Mangum รองรับ ✅
- **ต้องตั้งค่า**: `Integration type = Lambda Proxy`

#### B. **HTTP API (v2) - Lambda Integration**
- Event format: `version: "2.0"`, `routeKey`, `rawPath`
- Mangum รองรับ ✅
- **ต้องตั้งค่า**: `Integration type = Lambda`

---

### 🔴 4. ปัญหาที่พบ: HTTP 405 Method Not Allowed

**สาเหตุที่เป็นไปได้ (เรียงตามความน่าจะเป็น):**

#### 🎯 **สาเหตุ #1: CORS Preflight (OPTIONS) ไม่ได้ Handle**
**ความน่าจะเป็น: 80%**

**อาการ:**
- Frontend เรียก API แล้วได้ 405
- Browser ส่ง OPTIONS request ก่อน (CORS preflight)
- FastAPI ไม่มี route สำหรับ OPTIONS

**วิธีแก้:**
```python
# main.py - มี CORS middleware แล้ว ✅
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],  # ✅ รองรับ OPTIONS
    allow_headers=["*"],
)
```

**แต่ Mangum อาจต้อง handle OPTIONS เอง:**
- Mangum ควร handle OPTIONS อัตโนมัติ
- ถ้ายังไม่ได้ อาจต้องเพิ่ม route เอง

---

#### 🎯 **สาเหตุ #2: API Gateway Route Configuration ไม่ถูกต้อง**
**ความน่าจะเป็น: 70%**

**ปัญหาที่เป็นไปได้:**

1. **Resource Path ไม่ตรง**
   - API Gateway: `/health`
   - FastAPI: `/api/health`
   - **ต้องตั้งค่า**: API Gateway path = `/{proxy+}` หรือ `/api/{proxy+}`

2. **Method ไม่ตรง**
   - API Gateway: ตั้งค่าแค่ GET
   - FastAPI: ต้องการ POST
   - **ต้องตั้งค่า**: API Gateway ต้องรองรับทุก method

3. **Integration Type ไม่ใช่ Lambda Proxy**
   - ถ้าใช้ Lambda Integration (ไม่ใช่ Proxy)
   - Event format จะไม่ถูกต้อง
   - **ต้องตั้งค่า**: Integration type = **Lambda Proxy**

---

#### 🎯 **สาเหตุ #3: Event Format ไม่ตรงกับ Mangum**
**ความน่าจะเป็น: 50%**

**Mangum รองรับ 2 formats:**

##### Format A: REST API v1 (Lambda Proxy)
```json
{
  "resource": "/api/health",
  "path": "/api/health",
  "httpMethod": "GET",
  "headers": {
    "Accept": "application/json"
  },
  "queryStringParameters": null,
  "pathParameters": null,
  "requestContext": {
    "resourceId": "abc123",
    "resourcePath": "/api/health",
    "httpMethod": "GET",
    "requestId": "test-request-id",
    "path": "/api/health",
    "accountId": "123456789012",
    "protocol": "HTTP/1.1",
    "stage": "prod",
    "identity": {
      "sourceIp": "127.0.0.1"
    },
    "apiId": "test-api-id"
  },
  "body": null,
  "isBase64Encoded": false
}
```

##### Format B: HTTP API v2
```json
{
  "version": "2.0",
  "routeKey": "GET /api/health",
  "rawPath": "/api/health",
  "rawQueryString": "",
  "headers": {
    "accept": "application/json",
    "host": "api.example.com"
  },
  "requestContext": {
    "accountId": "123456789012",
    "apiId": "test-api-id",
    "domainName": "api.example.com",
    "domainPrefix": "api",
    "http": {
      "method": "GET",
      "path": "/api/health",
      "protocol": "HTTP/1.1",
      "sourceIp": "127.0.0.1",
      "userAgent": "test-agent"
    },
    "requestId": "test-request-id",
    "routeKey": "GET /api/health",
    "stage": "$default",
    "time": "01/Jan/2024:00:00:00 +0000",
    "timeEpoch": 1704067200
  },
  "body": null,
  "isBase64Encoded": false
}
```

---

### 🔧 5. แนวทางแก้ไข

#### **Step 1: ตรวจสอบ API Gateway Configuration**

**สำหรับ REST API:**
1. ไปที่ API Gateway Console
2. ตรวจสอบว่า:
   - ✅ Integration type = **Lambda Proxy Integration**
   - ✅ Resource path = `/{proxy+}` หรือ `/api/{proxy+}`
   - ✅ Methods = `ANY` หรือ `GET, POST, OPTIONS, PUT, DELETE`

**สำหรับ HTTP API:**
1. ไปที่ API Gateway Console
2. ตรวจสอบว่า:
   - ✅ Integration type = **Lambda**
   - ✅ Route = `$default` หรือ `/api/{proxy+}`
   - ✅ Methods = `ANY` หรือ `GET, POST, OPTIONS`

---

#### **Step 2: ตรวจสอบ CloudWatch Logs**

```bash
# ดู Lambda logs
aws logs tail /aws/lambda/ResumeMatchAPI --follow
```

**สิ่งที่ต้องดู:**
- Event ที่ Lambda รับจริง
- Error message จาก Mangum
- Path และ Method ที่ได้รับ

---

#### **Step 3: ทดสอบด้วย Event ที่ถูกต้อง**

**ตัวอย่าง Event สำหรับ REST API v1 (Lambda Proxy):**

```json
{
  "resource": "/{proxy+}",
  "path": "/api/health",
  "httpMethod": "GET",
  "headers": {
    "Accept": "application/json",
    "Content-Type": "application/json"
  },
  "multiValueHeaders": {},
  "queryStringParameters": null,
  "multiValueQueryStringParameters": null,
  "pathParameters": {
    "proxy": "api/health"
  },
  "stageVariables": null,
  "requestContext": {
    "resourceId": "abc123",
    "resourcePath": "/{proxy+}",
    "httpMethod": "GET",
    "extendedRequestId": "test-request-id",
    "requestId": "test-request-id",
    "path": "/prod/api/health",
    "accountId": "123456789012",
    "protocol": "HTTP/1.1",
    "stage": "prod",
    "domainPrefix": "api",
    "requestTime": "01/Jan/2024:00:00:00 +0000",
    "requestTimeEpoch": 1704067200,
    "identity": {
      "sourceIp": "127.0.0.1",
      "userAgent": "test-agent"
    },
    "apiId": "test-api-id"
  },
  "body": null,
  "isBase64Encoded": false
}
```

**สำคัญ:** ถ้าใช้ `/{proxy+}`, path จะเป็น `/api/health` แต่ `pathParameters.proxy` จะเป็น `api/health`

---

#### **Step 4: เพิ่ม OPTIONS Handler (ถ้าจำเป็น)**

ถ้า CORS preflight ยังไม่ได้ ให้เพิ่ม:

```python
# main.py
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle CORS preflight requests"""
    return {"status": "ok"}
```

---

### 📊 6. สรุป Checklist

| Item | Status | Notes |
|------|--------|-------|
| Lambda Handler | ✅ | `lambda_function.handler` ถูกต้อง |
| Mangum Setup | ✅ | `Mangum(app, lifespan="off")` ถูกต้อง |
| FastAPI Routes | ✅ | Routes ถูกต้อง |
| CORS Middleware | ✅ | ตั้งค่าแล้ว |
| API Gateway Type | ⚠️ | **ต้องตรวจสอบ** REST API หรือ HTTP API |
| Integration Type | ⚠️ | **ต้องตรวจสอบ** Lambda Proxy หรือไม่ |
| Resource Path | ⚠️ | **ต้องตรวจสอบ** `/{proxy+}` หรือ `/api/{proxy+}` |
| Methods | ⚠️ | **ต้องตรวจสอบ** รองรับ OPTIONS หรือไม่ |
| Event Format | ⚠️ | **ต้องตรวจสอบ** v1 หรือ v2 |

---

### 🎯 สาเหตุที่เป็นไปได้มากที่สุด

**ลำดับความน่าจะเป็น:**

1. **🥇 API Gateway Resource Path ไม่ตรง** (90%)
   - API Gateway: `/health`
   - FastAPI: `/api/health`
   - **แก้ไข**: ตั้งค่า Resource = `/{proxy+}` และ Path = `/api/health`

2. **🥈 CORS Preflight (OPTIONS) ไม่ได้ Handle** (80%)
   - Browser ส่ง OPTIONS ก่อน
   - Mangum อาจไม่ handle
   - **แก้ไข**: ตรวจสอบ CORS middleware และเพิ่ม OPTIONS handler

3. **🥉 Integration Type ไม่ใช่ Lambda Proxy** (70%)
   - ใช้ Lambda Integration แทน Lambda Proxy
   - Event format ไม่ถูกต้อง
   - **แก้ไข**: เปลี่ยนเป็น Lambda Proxy Integration

---

### 📝 ตัวอย่าง Event ที่ "ถูกต้อง"

#### สำหรับ REST API v1 (Lambda Proxy) - ใช้ `/{proxy+}`:

```json
{
  "resource": "/{proxy+}",
  "path": "/api/health",
  "httpMethod": "GET",
  "headers": {
    "Accept": "application/json"
  },
  "queryStringParameters": null,
  "pathParameters": {
    "proxy": "api/health"
  },
  "requestContext": {
    "resourcePath": "/{proxy+}",
    "httpMethod": "GET",
    "path": "/prod/api/health",
    "accountId": "123456789012",
    "protocol": "HTTP/1.1",
    "stage": "prod",
    "requestId": "test-request-id",
    "requestTime": "01/Jan/2024:00:00:00 +0000",
    "requestTimeEpoch": 1704067200,
    "identity": {
      "sourceIp": "127.0.0.1"
    },
    "apiId": "test-api-id"
  },
  "body": null,
  "isBase64Encoded": false
}
```

#### สำหรับ HTTP API v2:

```json
{
  "version": "2.0",
  "routeKey": "GET /api/health",
  "rawPath": "/api/health",
  "rawQueryString": "",
  "headers": {
    "accept": "application/json"
  },
  "requestContext": {
    "http": {
      "method": "GET",
      "path": "/api/health",
      "protocol": "HTTP/1.1",
      "sourceIp": "127.0.0.1"
    },
    "requestId": "test-request-id",
    "routeKey": "GET /api/health",
    "stage": "$default",
    "timeEpoch": 1704067200
  },
  "body": null,
  "isBase64Encoded": false
}
```

---

### 🚀 ขั้นตอนการแก้ไข (Recommended)

1. **ตรวจสอบ API Gateway Console:**
   - ดูว่าเป็น REST API หรือ HTTP API
   - ดู Integration type
   - ดู Resource path และ Methods

2. **ตรวจสอบ CloudWatch Logs:**
   - ดู event ที่ Lambda รับจริง
   - ดู error message

3. **ทดสอบด้วย Lambda Test Event:**
   - ใช้ event format ที่ถูกต้องตาม API Gateway type
   - ทดสอบทีละ endpoint

4. **แก้ไข API Gateway Configuration:**
   - ตั้งค่า Resource = `/{proxy+}`
   - ตั้งค่า Integration = Lambda Proxy
   - ตั้งค่า Methods = `ANY` หรือ `GET, POST, OPTIONS`

5. **ทดสอบอีกครั้ง:**
   - เรียกผ่าน API Gateway endpoint
   - ตรวจสอบ response

---

## 📞 ข้อมูลเพิ่มเติม

- **Mangum Documentation**: https://mangum.io/
- **API Gateway Event Formats**: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html
- **FastAPI CORS**: https://fastapi.tiangolo.com/tutorial/cors/

