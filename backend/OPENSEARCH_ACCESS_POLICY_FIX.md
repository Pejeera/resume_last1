# แก้ไข OpenSearch Access Policy

## ปัญหา
Access Policy ใช้ `es:ESHttp*` ซึ่งอาจไม่ครอบคลุมทุก action ที่จำเป็น

## วิธีแก้ไข

### เปลี่ยน Action จาก `es:ESHttp*` เป็น `es:*`

1. **ไปที่ AWS Console:**
   - OpenSearch Service > Domains > resume-search-dev
   - Security configuration > Edit access policy

2. **แก้ไข Policy:**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "arn:aws:iam::533267343789:role/resumematch-api-ResumeMatchAPIRole-6RhsLEwNCqDV"
         },
         "Action": "es:*",
         "Resource": "arn:aws:es:ap-southeast-2:533267343789:domain/resume-search-dev/*"
       }
     ]
   }
   ```

3. **ความแตกต่าง:**
   - `es:ESHttp*` - ครอบคลุมเฉพาะ HTTP actions (GET, POST, PUT, DELETE)
   - `es:*` - ครอบคลุมทุก action รวมถึงการจัดการ cluster และ index

4. **Save changes** และรอ ~1-2 นาที

5. **ทดสอบอีกครั้ง:**
   ```bash
   python backend/test_opensearch_lambda.py
   ```

## หมายเหตุ
- Principal ถูกต้องแล้ว (Lambda role ARN)
- Resource ถูกต้องแล้ว
- แค่ต้องเปลี่ยน Action เป็น `es:*` เพื่อให้ครอบคลุมทุก action

