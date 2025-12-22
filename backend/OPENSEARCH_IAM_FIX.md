# แก้ไข OpenSearch ให้ใช้ IAM Authentication

## สิ่งที่แก้ไข

### 1. เปลี่ยน OpenSearch Client ให้ใช้ IAM Authentication
- **เดิม**: ใช้ username/password (`resume_admin`)
- **ใหม่**: ใช้ IAM authentication (AWS SigV4)
- **เหตุผล**: Master user type เป็น IAM ไม่ใช่ Internal user database

### 2. เพิ่ม dependency
- เพิ่ม `requests-aws4auth==1.2.3` ใน `requirements.txt`

### 3. ใช้ Lambda IAM Role
- Lambda จะใช้ IAM role ของตัวเอง (`resumematch-api-ResumeMatchAPIRole-6RhsLEwNCqDV`)
- ไม่ต้องตั้งค่า username/password อีกต่อไป

## ข้อดี

1. **ปลอดภัยกว่า**: ใช้ IAM role แทน hardcoded credentials
2. **ไม่ต้องจัดการ password**: ไม่ต้องอัปเดต password ใน Lambda environment variables
3. **สอดคล้องกับการตั้งค่า**: Master user type เป็น IAM

## หลังจาก Deploy

1. **Deploy Lambda ใหม่:**
   ```powershell
   .\deploy_lambda_clean.ps1
   ```

2. **ตรวจสอบ Lambda IAM Role มีสิทธิ์:**
   - ไปที่ IAM Console
   - ตรวจสอบ role: `resumematch-api-ResumeMatchAPIRole-6RhsLEwNCqDV`
   - ต้องมี policy ที่อนุญาต `es:*` actions

3. **ทดสอบ:**
   ```bash
   python backend/test_opensearch_lambda.py
   ```

## หมายเหตุ

- ไม่ต้องตั้งค่า `OPENSEARCH_USERNAME` และ `OPENSEARCH_PASSWORD` อีกต่อไป
- Lambda จะใช้ IAM role credentials อัตโนมัติ
- ต้องแน่ใจว่า Lambda IAM role มีสิทธิ์เข้าถึง OpenSearch domain

