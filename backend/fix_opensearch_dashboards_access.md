# แก้ไข Access Policy เพื่อเข้าถึง OpenSearch Dashboards

## ปัญหา
Error: "User: anonymous is not authorized to perform: es:ESHttpGet" เมื่อพยายามเข้าถึง Dashboards

## สาเหตุ
Access Policy ปัจจุบันอนุญาตเฉพาะ Lambda role แต่ไม่อนุญาตการเข้าถึง Dashboards จาก browser

## วิธีแก้ไข

### วิธีที่ 1: เพิ่ม Principal สำหรับ Browser Access (แนะนำ)

แก้ไข Access Policy ใน AWS Console:

1. ไปที่ **AWS Console > OpenSearch Service > Domains > resume-search-dev**
2. **Security configuration > Edit access policy**
3. แก้ไข Policy เป็น:

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
    },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "*"
      },
      "Action": [
        "es:ESHttpGet",
        "es:ESHttpPost",
        "es:ESHttpPut",
        "es:ESHttpDelete"
      ],
      "Resource": "arn:aws:es:ap-southeast-2:533267343789:domain/resume-search-dev/_dashboards/*"
    }
  ]
}
```

**หมายเหตุ:** Statement ที่ 2 อนุญาตทุกคนเข้าถึง Dashboards (ใช้เฉพาะ development/testing)

### วิธีที่ 2: ใช้ IAM User/Role สำหรับ Browser Access (ปลอดภัยกว่า)

1. สร้าง IAM user หรือใช้ IAM role ที่มีอยู่
2. แก้ไข Access Policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::533267343789:role/resumematch-api-ResumeMatchAPIRole-6RhsLEwNCqDV",
          "arn:aws:iam::533267343789:user/YOUR_IAM_USER"
        ]
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:ap-southeast-2:533267343789:domain/resume-search-dev/*"
    }
  ]
}
```

3. ใช้ AWS CLI credentials หรือ browser extension เพื่อ authenticate

### วิธีที่ 3: ใช้ Cognito Authentication (แนะนำสำหรับ Production)

ตั้งค่า Cognito authentication สำหรับ Dashboards:
1. Security configuration > Authentication for OpenSearch Dashboards/Kibana
2. Enable Cognito
3. สร้าง Cognito user pool และ identity pool

## หลังจากแก้ไข

1. **Save changes** และรอ ~1-2 นาที
2. **Refresh browser** และลองเข้าถึง Dashboards อีกครั้ง
3. **Login** ด้วย master user credentials หรือ IAM credentials

## หมายเหตุ

- Statement แรก: สำหรับ Lambda function (es:*)
- Statement ที่สอง: สำหรับ browser access (es:ESHttpGet)
- สำหรับ production ควรใช้ Cognito หรือ IAM authentication แทน anonymous access

