# คู่มือตั้งค่า Role Mapping ใน OpenSearch Dashboards

## ขั้นตอนที่ 1: Login เข้า Dashboards

1. **URL:** 
   ```
   https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com/_dashboards
   ```

2. **Login ด้วย Master User:**
   - ถ้า Master user type เป็น **IAM**: ต้องใช้ IAM user/role ที่มีสิทธิ์
   - ถ้า Master user type เป็น **Internal user database**: ใช้ username/password ที่ตั้งค่าไว้

3. **ถ้าไม่ทราบ Master User:**
   - ไปที่ AWS Console > OpenSearch Service > Domain: resume-search-dev
   - Security configuration > ดูที่ "Master user type" และ "Master user"

## ขั้นตอนที่ 2: สร้าง Role (ถ้ายังไม่มี)

1. **ไปที่ Security > Roles** (เมนูซ้าย)

2. **ตรวจสอบว่ามี role `all_access` หรือไม่:**
   - ถ้ามี → ใช้ role นี้ได้เลย (ข้ามไปขั้นตอนที่ 3)
   - ถ้าไม่มี → สร้าง role ใหม่

3. **สร้าง Role ใหม่ (ถ้าต้องการ):**
   - คลิก **"Create role"**
   - **Role name:** `lambda_opensearch_role`
   - **Cluster permissions:**
     - คลิก **"Add permissions"**
     - เลือก: `cluster_composite_ops`, `cluster_monitor`
   - **Index permissions:**
     - คลิก **"Add index permissions"**
     - **Index pattern:** `*` (หรือ `jobs_index`, `resumes_index`)
     - **Permissions:** เลือกทั้งหมด:
       - ✅ `create_index`
       - ✅ `write`
       - ✅ `read`
       - ✅ `manage`
       - ✅ `delete_index` (optional)
   - คลิก **"Create"**

## ขั้นตอนที่ 3: สร้าง Role Mapping

1. **ไปที่ Security > Role Mappings** (เมนูซ้าย)

2. **คลิก "Create role mapping"**

3. **กรอกข้อมูล:**
   - **Mapping name:** `lambda_role_mapping` (หรือชื่ออะไรก็ได้)
   - **Backend role:** 
     ```
     arn:aws:iam::533267343789:role/resumematch-api-ResumeMatchAPIRole-6RhsLEwNCqDV
     ```
   - **Users:** (เว้นว่างไว้ หรือใส่ `*` สำหรับทุก user)
   - **Hosts:** (เว้นว่างไว้)

4. **เลือก Roles:**
   - คลิก **"Add role"**
   - เลือก `all_access` (ง่ายที่สุด) หรือ `lambda_opensearch_role` (ถ้าสร้างไว้)
   - คลิก **"Create"**

## ขั้นตอนที่ 4: ทดสอบ

1. **รอ ~30 วินาที** ให้การตั้งค่า propagate

2. **ทดสอบ Lambda:**
   ```bash
   python backend/test_opensearch_lambda.py
   ```

3. **ผลลัพธ์ที่คาดหวัง:**
   - ✅ Jobs List: 200 OK
   - ✅ OpenSearch Sync: 200 OK (ไม่มี error 403)

## หมายเหตุ

- **Backend role** ต้องเป็น IAM role ARN ที่ Lambda ใช้
- **Roles** ต้องมี permissions ที่จำเป็น (create_index, write, read, manage)
- ถ้าใช้ `all_access` role จะให้สิทธิ์เต็ม (ใช้เฉพาะ development/testing)

## ถ้ายังไม่ได้

1. ตรวจสอบว่า Backend role ARN ถูกต้อง
2. ตรวจสอบว่า Role ที่เลือกมี permissions ครบ
3. รออีกสักครู่ (อาจต้องรอ 1-2 นาที)
4. ตรวจสอบ CloudWatch Logs สำหรับ error messages ที่ละเอียดกว่า

