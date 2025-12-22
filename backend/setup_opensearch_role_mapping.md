# ตั้งค่า OpenSearch Role Mapping สำหรับ Lambda

## ปัญหา
Error 403 (AuthorizationException) เมื่อพยายามสร้าง index แม้ว่า Access Policy จะถูกต้องแล้ว

## สาเหตุ
Fine-Grained Access Control (FGAC) เปิดอยู่ ต้องตั้งค่า Role Mapping เพื่อให้ IAM role มีสิทธิ์เข้าถึง

## วิธีแก้ไข

### ขั้นตอนที่ 1: Login เข้า OpenSearch Dashboards

1. ไปที่:
   ```
   https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com/_dashboards
   ```

2. Login ด้วย master user credentials
   - ถ้า Master user type เป็น IAM ต้องใช้ IAM user/role ที่มีสิทธิ์

### ขั้นตอนที่ 2: สร้าง Role ที่มี Permissions ครบ

1. ไปที่ **Security > Roles**
2. คลิก **Create role**
3. ตั้งชื่อ role: `lambda_opensearch_role`
4. **Cluster permissions:**
   - เพิ่ม: `cluster_composite_ops`
   - เพิ่ม: `cluster_monitor`
5. **Index permissions:**
   - คลิก **Add index permissions**
   - Index pattern: `*` (หรือ `jobs_index`, `resumes_index`)
   - Permissions:
     - ✅ `create_index`
     - ✅ `write`
     - ✅ `read`
     - ✅ `manage`
     - ✅ `delete_index` (ถ้าต้องการ)
6. คลิก **Create**

### ขั้นตอนที่ 3: สร้าง Role Mapping

1. ไปที่ **Security > Role Mappings**
2. คลิก **Create role mapping**
3. **Mapping name:** `lambda_role_mapping`
4. **Backend role:**
   ```
   arn:aws:iam::533267343789:role/resumematch-api-ResumeMatchAPIRole-6RhsLEwNCqDV
   ```
5. **Users:** (เว้นว่างไว้ หรือใส่ `*`)
6. **Hosts:** (เว้นว่างไว้)
7. **Roles:** เลือก role ที่สร้างไว้ (`lambda_opensearch_role`)
8. คลิก **Create**

### ขั้นตอนที่ 4: ทดสอบ

```bash
python backend/test_opensearch_lambda.py
```

## หมายเหตุ

- **Backend role** ต้องเป็น IAM role ARN ที่ Lambda ใช้
- **Roles** ต้องมี permissions ที่จำเป็น (create_index, write, read, manage)
- หลังจากสร้าง role mapping แล้ว อาจต้องรอ ~30 วินาที

## Alternative: ใช้ All Access Role

ถ้าเร่งด่วน สามารถ map กับ `all_access` role:

1. ไปที่ **Security > Role Mappings**
2. สร้าง role mapping ใหม่
3. **Backend role:** `arn:aws:iam::533267343789:role/resumematch-api-ResumeMatchAPIRole-6RhsLEwNCqDV`
4. **Roles:** เลือก `all_access`
5. คลิก **Create**

⚠️ **คำเตือน:** `all_access` ให้สิทธิ์เต็ม ใช้เฉพาะ development/testing

