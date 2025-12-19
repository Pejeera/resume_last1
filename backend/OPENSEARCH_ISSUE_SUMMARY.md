# สรุปปัญหา OpenSearch Authentication

## 🔴 ปัญหาหลัก
**OpenSearch Authentication Error (401)** - ไม่สามารถเชื่อมต่อ OpenSearch ได้

## 📋 สถานะการตั้งค่าปัจจุบัน

### ✅ สิ่งที่ตั้งค่าถูกต้องแล้ว:
- **USE_MOCK**: `false` (เปิดใช้งาน OpenSearch จริง)
- **OPENSEARCH_ENDPOINT**: ตั้งค่าแล้ว
  - `https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com`
- **OPENSEARCH_USERNAME**: `resume_admin`
- **OPENSEARCH_PASSWORD**: ตั้งค่าแล้ว (แต่ไม่ถูกต้อง)

### ⚠️ ปัญหาที่พบ:

1. **Authentication Failed (401)**
   - การทดสอบเชื่อมต่อโดยตรงได้ 401 Unauthorized
   - Username หรือ Password ไม่ถูกต้อง

2. **Fine-Grained Access Control (FGAC) Enabled**
   - OpenSearch domain มี FGAC เปิดอยู่
   - Internal User Database ถูกปิด (Disabled)
   - อาจต้องใช้ IAM role แทน username/password

3. **API Sync ล้มเหลว**
   - `/api/jobs/sync_from_s3` ได้ error 401
   - ไม่สามารถสร้าง index หรือ index documents ได้

## 🔍 สาเหตุที่เป็นไปได้

### 1. Password ไม่ถูกต้อง
- Password ที่ตั้งค่าใน Lambda อาจไม่ตรงกับ password จริงใน OpenSearch
- ต้องตรวจสอบ password ที่ถูกต้อง

### 2. User ไม่มีในระบบ
- `resume_admin` อาจไม่มีใน OpenSearch (เพราะ Internal User Database ถูกปิด)
- ต้องสร้าง user ใหม่หรือใช้ user ที่มีอยู่

### 3. ต้องใช้ IAM Authentication
- เนื่องจาก Internal User Database ถูกปิด อาจต้องใช้ IAM role แทน
- ต้องเปลี่ยนการ authentication จาก username/password เป็น IAM

### 4. Role Mapping ไม่ถูกต้อง
- User อาจมีอยู่แต่ไม่มีสิทธิ์เข้าถึง domain
- ต้องตรวจสอบ role mapping ใน OpenSearch

## 🛠️ วิธีแก้ไข

### วิธีที่ 1: ตรวจสอบและอัปเดต Password

1. **ตรวจสอบ password ที่ถูกต้อง:**
   - ไปที่ AWS Console > OpenSearch Service
   - ตรวจสอบ master user password
   - หรือ reset password ใหม่

2. **อัปเดต Lambda environment variables:**
   ```powershell
   .\update_opensearch_credentials.ps1 `
     -OpenSearchEndpoint "https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com" `
     -OpenSearchUsername "resume_admin" `
     -OpenSearchPassword "PASSWORD_THAT_IS_CORRECT" `
     -UseMock "false"
   ```

3. **ทดสอบอีกครั้ง:**
   ```bash
   python test_opensearch_lambda.py
   ```

### วิธีที่ 2: ใช้ IAM Authentication (ถ้าจำเป็น)

1. **ตรวจสอบว่า OpenSearch ใช้ IAM หรือไม่:**
   - ไปที่ AWS Console > OpenSearch Service > Domain
   - ดูที่ Fine-grained access control settings
   - ตรวจสอบ Master user type (IAM หรือ Internal user database)

2. **ถ้าใช้ IAM:**
   - ต้องเปลี่ยน OpenSearch client ให้ใช้ IAM authentication
   - ใช้ AWS SigV4 signing แทน username/password

### วิธีที่ 3: สร้าง User ใหม่ใน OpenSearch

1. **เข้าถึง OpenSearch Dashboards:**
   - ไปที่ `https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com/_dashboards`
   - Login ด้วย master user credentials

2. **สร้าง user ใหม่:**
   - Security > Internal users > Create user
   - ตั้ง username: `resume_admin`
   - ตั้ง password ที่ต้องการ
   - Assign roles ที่เหมาะสม

3. **อัปเดต Lambda credentials:**
   ```powershell
   .\update_opensearch_credentials.ps1 `
     -OpenSearchEndpoint "https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com" `
     -OpenSearchUsername "resume_admin" `
     -OpenSearchPassword "NEW_PASSWORD" `
     -UseMock "false"
   ```

## 📊 สรุปสถานะ

| องค์ประกอบ | สถานะ | หมายเหตุ |
|-----------|-------|---------|
| USE_MOCK | ✅ OK | ตั้งเป็น false แล้ว |
| OPENSEARCH_ENDPOINT | ✅ OK | ตั้งค่าถูกต้อง |
| OPENSEARCH_USERNAME | ✅ OK | resume_admin |
| OPENSEARCH_PASSWORD | ❌ ERROR | ไม่ถูกต้องหรือไม่มี user |
| Fine-Grained Access Control | ⚠️ WARNING | เปิดอยู่ - ต้องตรวจสอบ |
| Internal User Database | ❌ DISABLED | ถูกปิด - อาจต้องใช้ IAM |

## 🎯 ขั้นตอนต่อไป

1. **ตรวจสอบ password ที่ถูกต้อง** - ถามผู้ดูแลระบบหรือ reset password
2. **ทดสอบ credentials โดยตรง:**
   ```bash
   curl -u resume_admin:PASSWORD https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com/_cluster/health
   ```
3. **อัปเดต Lambda credentials** ด้วย password ที่ถูกต้อง
4. **ทดสอบอีกครั้ง** ด้วย `python test_opensearch_lambda.py`

## 📝 หมายเหตุ

- Internal User Database ถูกปิด - อาจหมายความว่า domain ใช้ IAM authentication
- ถ้าใช้ IAM ต้องแก้ไข OpenSearch client code ให้ใช้ AWS SigV4
- ตรวจสอบ CloudWatch Logs สำหรับรายละเอียดเพิ่มเติม

