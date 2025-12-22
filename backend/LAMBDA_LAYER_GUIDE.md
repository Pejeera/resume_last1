# 🧱 คู่มือการใช้ Lambda Layer แก้ปัญหา "No module named 'requests'"

## ❌ ปัญหา

```
Runtime.ImportModuleError: No module named 'requests'
```

**สาเหตุ:**
- Lambda function ไม่มี library `requests` และ `requests-aws4auth` ใน environment
- ZIP ที่อัปโหลดไม่มี dependencies หรือถูก inline code ทับ

## ✅ วิธีแก้: ใช้ Lambda Layer

Lambda Layer เป็นวิธีที่ AWS แนะนำสำหรับจัดการ dependencies ที่ใช้ร่วมกันหลาย functions

### ข้อดี:
- ✅ ไม่ต้อง zip dependencies ทุกครั้ง
- ✅ แชร์ dependencies ระหว่าง functions ได้
- ✅ แยก code กับ dependencies ชัดเจน
- ✅ ไม่โดน inline code ทับ

---

## 📦 ขั้นตอนที่ 1: สร้าง Lambda Layer

### วิธีที่ 1: ใช้สคริปต์ (แนะนำ)

```powershell
cd backend
.\create_lambda_layer.ps1
```

สคริปต์จะ:
1. สร้างโฟลเดอร์ `lambda-layer/python/`
2. ติดตั้ง `requests` และ `requests-aws4auth`
3. สร้าง ZIP file `requests-layer.zip`
4. ตรวจสอบโครงสร้าง

### วิธีที่ 2: ทำเอง

```powershell
# สร้างโฟลเดอร์
mkdir lambda-layer
cd lambda-layer
mkdir python

# ติดตั้ง dependencies
pip install requests requests-aws4auth -t python

# สร้าง ZIP (ต้องอยู่ภายใน lambda-layer/)
cd ..
Compress-Archive -Path lambda-layer/python -DestinationPath requests-layer.zip
```

**⚠️ สำคัญ:** โครงสร้างใน ZIP ต้องเป็น:
```
requests-layer.zip
 └─ python/
     ├─ requests/
     ├─ requests_aws4auth/
     ├─ urllib3/
     ├─ certifi/
     └─ ...
```

---

## 🚀 ขั้นตอนที่ 2: Deploy Lambda พร้อม Layer

### วิธีที่ 1: ใช้สคริปต์ (แนะนำ)

```powershell
cd backend
.\deploy_lambda_with_layer.ps1
```

สคริปต์จะ:
1. สร้าง Lambda function package (เฉพาะ code)
2. สร้าง/อัปเดต Lambda Layer
3. อัปโหลด Lambda function code
4. ผูก Layer เข้ากับ Lambda function
5. ทดสอบ function

### วิธีที่ 2: ทำเองผ่าน AWS Console

#### 2.1 สร้าง Layer

1. ไปที่ **AWS Console → Lambda → Layers**
2. คลิก **Create layer**
3. ตั้งค่า:
   - **Name:** `requests-layer`
   - **Upload:** เลือกไฟล์ `requests-layer.zip`
   - **Compatible runtimes:** `Python 3.10` (หรือตาม Lambda function)
4. คลิก **Create**

#### 2.2 ผูก Layer เข้ากับ Lambda

1. ไปที่ **Lambda → Functions → resume-search-api**
2. Scroll ลงไปที่ **Layers**
3. คลิก **Add a layer**
4. เลือก **Custom layers**
5. เลือก `requests-layer` และ version ล่าสุด
6. คลิก **Add**

#### 2.3 อัปโหลด Lambda Code

1. ในหน้า **Code** ของ Lambda function
2. คลิก **Upload from** → **.zip file**
3. เลือกไฟล์ `lambda-function-only.zip` (หรือ zip ที่มีเฉพาะ `lambda_function.py`)
4. คลิก **Save**

---

## 📝 ขั้นตอนที่ 3: ตรวจสอบ Lambda Function Code

**โค้ดที่ถูกต้อง (ใช้ Layer):**

```python
import json
import boto3
import urllib.parse
import requests
from requests_aws4auth import AWS4Auth
import os

# ไม่ต้องมี sys.path manipulation
# ไม่ต้องมี python/ directory
```

**โค้ดที่ผิด (ไม่ใช้ Layer):**

```python
import sys
import os

# ❌ ห้ามทำแบบนี้ถ้าใช้ Layer
python_path = os.path.join(os.path.dirname(__file__), 'python')
if python_path not in sys.path:
    sys.path.insert(0, python_path)

import requests
```

---

## 🧪 ขั้นตอนที่ 4: ทดสอบ

### ทดสอบแบบเร็ว (ใน Console)

1. ไปที่ Lambda function → **Test**
2. สร้าง test event:
   ```json
   {}
   ```
3. คลิก **Test**

**✅ ถ้าผ่าน:**
- ไม่เห็น error `No module named 'requests'`
- อาจ error เรื่อง event format (ไม่เป็นไร)

**❌ ถ้ายัง error:**
- ตรวจสอบว่า Layer ถูกผูกแล้วหรือยัง
- ตรวจสอบ Runtime ของ Layer ตรงกับ Lambda หรือไม่
- ตรวจสอบโครงสร้างใน Layer ZIP

### ทดสอบจริง (S3 Trigger)

1. อัปโหลดไฟล์ไปที่ S3:
   ```
   s3://resume-matching-533267343789/resumes/jobs_data.json
   ```

2. ตรวจสอบ CloudWatch Logs:
   ```
   /aws/lambda/resume-search-api
   ```

**✅ ต้องเห็น:**
```
Reading file s3://...
Indexed job job-001
Indexed job job-002
```

---

## 🚫 สิ่งที่ห้ามทำ

### ❌ ห้ามแก้โค้ดใน Console Editor แบบ inline

ถ้าคุณ:
1. Upload ZIP file
2. แล้วไปแก้โค้ดใน Console Editor → Save

**ผลลัพธ์:** Lambda จะใช้ inline code แทน ZIP → Layer จะไม่ทำงาน

### ✅ วิธีแก้โค้ดที่ถูกต้อง

1. แก้โค้ดใน local (`lambda_function.py`)
2. สร้าง ZIP ใหม่ (เฉพาะ code)
3. Upload ZIP ใหม่
4. **อย่าแก้ใน Console Editor**

---

## 🔍 ตรวจสอบปัญหา

### 1. ตรวจสอบว่า Layer ถูกผูกแล้ว

```powershell
aws lambda get-function --function-name resume-search-api --region ap-southeast-2
```

ดูที่ `Configuration.Layers` ต้องมี Layer ARN

### 2. ตรวจสอบโครงสร้าง Layer

```powershell
# Extract ZIP
Expand-Archive -Path requests-layer.zip -DestinationPath temp-check

# ตรวจสอบ
Test-Path temp-check/python/requests
Test-Path temp-check/python/requests_aws4auth
```

### 3. ตรวจสอบ CloudWatch Logs

```powershell
aws logs tail /aws/lambda/resume-search-api --since 5m --region ap-southeast-2
```

---

## 📋 Checklist

- [ ] สร้าง Lambda Layer (`requests-layer.zip`)
- [ ] อัปโหลด Layer ไปที่ AWS
- [ ] ผูก Layer เข้ากับ Lambda function
- [ ] อัปโหลด Lambda code (เฉพาะ `lambda_function.py`)
- [ ] ตรวจสอบว่าไม่มี `sys.path` manipulation ใน code
- [ ] ทดสอบ Lambda function
- [ ] ตรวจสอบ CloudWatch Logs
- [ ] ทดสอบ S3 trigger จริง

---

## 🆘 ถ้ายังมีปัญหา

### Error: "No module named 'requests'"

**ตรวจสอบ:**
1. Layer ถูกผูกกับ Lambda function แล้วหรือยัง?
   - Lambda → Layers section → ต้องมี `requests-layer`
2. Runtime ของ Layer ตรงกับ Lambda หรือไม่?
   - Layer: Python 3.10
   - Lambda: Python 3.10
3. โครงสร้างใน Layer ZIP ถูกต้องหรือไม่?
   - ต้องมี `python/requests/` ภายใน ZIP
4. Lambda code ใช้ inline code หรือ ZIP?
   - ตรวจสอบหน้า Code → ต้องเป็น "Upload a .zip file"

### Error: Layer ไม่พบ

**แก้ไข:**
1. ตรวจสอบ Layer name ถูกต้องหรือไม่
2. ตรวจสอบ Region ตรงกันหรือไม่
3. สร้าง Layer ใหม่

---

## 📚 อ้างอิง

- [AWS Lambda Layers Documentation](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
- [Lambda Layer Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html#configuration-layers-best-practices)

