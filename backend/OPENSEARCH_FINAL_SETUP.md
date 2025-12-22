# สรุปการตั้งค่า OpenSearch ทั้งหมด

## ✅ สิ่งที่ทำแล้ว

1. ✅ แก้ไข OpenSearch client ให้ใช้ IAM authentication
2. ✅ Deploy Lambda ใหม่
3. ✅ ตั้งค่า Access Policy ให้อนุญาต Lambda role
4. ✅ เปลี่ยน Action เป็น `es:*`

## ❌ สิ่งที่ยังต้องทำ

### ตั้งค่า Role Mapping ใน OpenSearch Dashboards

เนื่องจาก Fine-Grained Access Control เปิดอยู่ ต้องตั้งค่า Role Mapping

**URL:** https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com/_dashboards

**ขั้นตอน:**
1. Login ด้วย master user credentials
2. Security > Roles > Create role
   - Role name: `lambda_opensearch_role`
   - Cluster permissions: `cluster_composite_ops`, `cluster_monitor`
   - Index permissions: `create_index`, `write`, `read`, `manage`
3. Security > Role Mappings > Create role mapping
   - Backend role: `arn:aws:iam::533267343789:role/resumematch-api-ResumeMatchAPIRole-6RhsLEwNCqDV`
   - Roles: `lambda_opensearch_role`

## 📋 Checklist

- [ ] Login เข้า OpenSearch Dashboards
- [ ] สร้าง role ที่มี permissions ครบ
- [ ] สร้าง role mapping สำหรับ Lambda IAM role
- [ ] ทดสอบ: `python backend/test_opensearch_lambda.py`

## 🎯 ผลลัพธ์ที่คาดหวัง

หลังจากตั้งค่าเสร็จ:
- ✅ Jobs List: 200 OK
- ✅ OpenSearch Sync: 200 OK (ไม่มี error 403)

## 📝 หมายเหตุ

- Access Policy ถูกต้องแล้ว
- Code ใช้ IAM authentication แล้ว
- แค่ต้องตั้งค่า Role Mapping ใน Dashboards

