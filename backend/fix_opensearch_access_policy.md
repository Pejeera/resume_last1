# แก้ไขปัญหา OpenSearch Access Policy

## ปัญหา
Error: `User: anonymous is not authorized to perform: es:ESHttpGet`

## สาเหตุ
OpenSearch domain ไม่ได้ตั้งค่า Access Policy ให้อนุญาตการเข้าถึงจาก browser

## วิธีแก้ไข

### วิธีที่ 1: แก้ไข Access Policy ใน AWS Console (แนะนำ)

1. **ไปที่ AWS Console:**
   - https://console.aws.amazon.com/esv3/home?region=ap-southeast-2
   - หรือค้นหา "OpenSearch Service"

2. **เลือก Domain:**
   - คลิกที่ domain: `resume-search-dev`

3. **แก้ไข Access Policy:**
   - ไปที่แท็บ "Security configuration"
   - คลิก "Edit" ที่ Access policy
   - แก้ไข policy ให้อนุญาตการเข้าถึง

4. **ตัวอย่าง Access Policy (อนุญาตจาก IP ของคุณ):**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "*"
         },
         "Action": "es:*",
         "Resource": "arn:aws:es:ap-southeast-2:533267343789:domain/resume-search-dev/*"
       }
     ]
   }
   ```

   **⚠️ หมายเหตุ:** Policy นี้อนุญาตทุกคน - ใช้เฉพาะสำหรับ development/testing

5. **ตัวอย่าง Access Policy (อนุญาตเฉพาะ IAM users/roles):**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": [
             "arn:aws:iam::533267343789:role/resumematch-api-ResumeMatchAPIRole-6RhsLEwNCqDV",
             "arn:aws:iam::533267343789:root"
           ]
         },
         "Action": "es:*",
         "Resource": "arn:aws:es:ap-southeast-2:533267343789:domain/resume-search-dev/*"
         "Condition": {
           "IpAddress": {
             "aws:SourceIp": ["YOUR_IP_ADDRESS/32"]
           }
         }
       }
     ]
   }
   ```

6. **Save changes** และรอ ~5 นาทีให้ policy อัปเดต

### วิธีที่ 2: ใช้ AWS CLI

```powershell
# ดึง current policy
aws opensearch describe-domain --domain-name resume-search-dev --region ap-southeast-2 --query 'DomainStatus.AccessPolicies' --output text

# อัปเดต policy (ใช้ JSON file)
aws opensearch update-domain-config `
  --domain-name resume-search-dev `
  --region ap-southeast-2 `
  --access-policies file://access-policy.json
```

### วิธีที่ 3: ใช้ Fine-Grained Access Control (FGAC)

ถ้า domain ใช้ FGAC:
1. ต้อง login ด้วย master user credentials
2. หรือใช้ IAM authentication
3. ตั้งค่า role mapping ให้ถูกต้อง

## ตรวจสอบการตั้งค่า

### ตรวจสอบ Network Configuration:
- Public access: ต้องเปิดอยู่
- VPC: ถ้าอยู่ใน VPC ต้องมี VPC endpoint หรือ NAT gateway

### ตรวจสอบ Security:
- Fine-grained access control: เปิดอยู่
- Master user: ตั้งค่าแล้ว
- Internal user database: ปิดอยู่ (ใช้ IAM)

## หลังจากแก้ไข

1. **รอ ~5 นาที** ให้ policy อัปเดต
2. **ลองเข้าถึง Dashboards อีกครั้ง:**
   ```
   https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com/_dashboards
   ```
3. **Login ด้วย master user credentials**

## หมายเหตุ

- Access Policy ใช้สำหรับควบคุมการเข้าถึง domain จากภายนอก
- Fine-Grained Access Control ใช้สำหรับควบคุม permissions ภายใน domain
- ต้องตั้งค่าทั้งสองอย่างให้ถูกต้อง

