# แก้ไขปัญหา OpenSearch Authorization (403)

## สถานะปัจจุบัน
- ✅ Authentication ผ่านแล้ว (เชื่อมต่อได้)
- ❌ Authorization ล้มเหลว (403) - ไม่มีสิทธิ์สร้าง index

## สาเหตุ
Error: `AuthorizationException(403, '')` เมื่อพยายามสร้าง index

## วิธีแก้ไข

### วิธีที่ 1: ตรวจสอบ Role Mapping ใน OpenSearch

1. **เข้าถึง OpenSearch Dashboards:**
   ```
   https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com/_dashboards
   ```

2. **Login ด้วย master user credentials**

3. **ไปที่ Security > Roles:**
   - ตรวจสอบ role ที่ user `resume_admin` มี
   - ต้องมี role ที่มีสิทธิ์:
     - `create_index`
     - `write` (สำหรับ index documents)
     - `read` (สำหรับ search)

4. **ตรวจสอบ Role Mapping:**
   - Security > Role Mappings
   - ตรวจสอบว่า user `resume_admin` ถูก map กับ role ที่เหมาะสม

### วิธีที่ 2: สร้าง/แก้ไข Role สำหรับ resume_admin

1. **สร้าง Role ใหม่ (ถ้ายังไม่มี):**
   - Security > Roles > Create role
   - Role name: `resume_admin_role`
   - Cluster permissions:
     - `cluster_composite_ops`
     - `cluster_monitor`
   - Index permissions:
     - Index pattern: `*` หรือ `jobs_index`, `resumes_index`
     - Permissions:
       - `create_index`
       - `write`
       - `read`
       - `manage`

2. **Map User กับ Role:**
   - Security > Role Mappings
   - Map user `resume_admin` กับ role `resume_admin_role`

### วิธีที่ 3: ใช้ Master User (ชั่วคราว)

ถ้าเร่งด่วน สามารถใช้ master user แทน `resume_admin`:

```powershell
.\update_opensearch_credentials.ps1 `
  -OpenSearchEndpoint "https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com" `
  -OpenSearchUsername "MASTER_USERNAME" `
  -OpenSearchPassword "MASTER_PASSWORD" `
  -UseMock "false"
```

### วิธีที่ 4: ตรวจสอบ Access Policy

1. **ไปที่ AWS Console > OpenSearch Service**
2. **เลือก domain: `resume-search-dev`**
3. **ตรวจสอบ Access Policy:**
   - ต้องอนุญาตให้ Lambda role เข้าถึงได้
   - หรือใช้ fine-grained access control

## ขั้นตอนแนะนำ

1. **เข้าถึง OpenSearch Dashboards**
2. **ตรวจสอบ role ของ `resume_admin`**
3. **เพิ่ม permissions ที่จำเป็น (create_index, write, read)**
4. **ทดสอบอีกครั้ง:**
   ```bash
   python backend/test_opensearch_lambda.py
   ```

## หมายเหตุ

- 403 Authorization ดีกว่า 401 Authentication (เชื่อมต่อได้แล้ว)
- ปัญหาอยู่ที่ permissions ไม่ใช่ credentials
- ต้องแก้ไขใน OpenSearch Dashboards หรือ AWS Console

