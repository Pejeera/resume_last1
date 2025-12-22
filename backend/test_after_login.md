# ทดสอบ OpenSearch หลังจาก Login

## หลังจาก Login และตั้งค่า Permissions แล้ว

### 1. ทดสอบ OpenSearch Sync:
```bash
python backend/test_opensearch_lambda.py
```

### 2. หรือทดสอบผ่าน API โดยตรง:
```bash
python backend/test_api_server.py
```

### 3. ตรวจสอบว่า Sync สำเร็จ:
- ควรได้ Status 200 แทน 500
- ไม่มี error AuthorizationException(403)

## สิ่งที่ควรเห็นหลังจากแก้ไข:

✅ **Jobs List**: ทำงานได้ (200 OK)
✅ **OpenSearch Sync**: ทำงานได้ (200 OK) - ไม่มี error 403
✅ **สามารถสร้าง index และ index documents ได้**

## ถ้ายังมีปัญหา:

1. **ตรวจสอบ Role Mapping:**
   - Security > Role Mappings
   - ตรวจสอบว่า `resume_admin` ถูก map กับ role ที่มี permissions ครบ

2. **ตรวจสอบ Index Permissions:**
   - Security > Roles > [role name] > Index permissions
   - ตรวจสอบว่า index pattern ถูกต้อง (เช่น `*` หรือ `jobs_index`, `resumes_index`)

3. **ตรวจสอบ CloudWatch Logs:**
   - ดู error messages ที่ละเอียดกว่า

