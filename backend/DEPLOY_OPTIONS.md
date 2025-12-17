# 🚀 Lambda Deploy Options

## ปัญหา: Windows binaries ไม่ทำงานใน Lambda (Linux)

Lambda ใช้ Linux แต่ dependencies ที่ติดตั้งใน Windows เป็น `.pyd` (Windows binary) ไม่สามารถใช้ใน Lambda ได้

## วิธีแก้ไข

### Option 1: ใช้ Docker (แนะนำ) ⭐

**ข้อกำหนด:**
- Docker Desktop ต้องรันอยู่
- Start Docker Desktop ก่อนรันสคริปต์

**คำสั่ง:**
```powershell
# 1. Start Docker Desktop
# 2. รอให้ Docker พร้อม (ไอคอน Docker ใน system tray เป็นสีเขียว)

# 3. Deploy
.\deploy_lambda_docker.ps1
```

### Option 2: ใช้ EC2 หรือ Linux Machine

```bash
# SSH เข้า EC2 หรือ Linux machine
cd backend
pip install -r requirements.txt -t .
zip -r lambda-deployment.zip . -x "*.pyc" "__pycache__/*" "test_*.py" "*.md"
aws lambda update-function-code --function-name ResumeMatchAPI --zip-file fileb://lambda-deployment.zip
```

### Option 3: ใช้ Lambda Layer

สร้าง Lambda Layer สำหรับ dependencies ที่ซับซ้อน (pydantic_core, etc.)

### Option 4: ใช้ AWS SAM หรือ Serverless Framework

จัดการ dependencies และ deployment อัตโนมัติ

## สถานะปัจจุบัน

- ✅ Code ถูกต้อง (main.py, lambda_function.py)
- ✅ Handler = `lambda_function.handler`
- ❌ Dependencies เป็น Windows binaries
- ⏳ ต้อง deploy ด้วย Docker หรือ Linux environment

## ขั้นตอนถัดไป

1. **Start Docker Desktop**
2. **รอให้ Docker พร้อม** (ไอคอนเขียว)
3. **รัน:** `.\deploy_lambda_docker.ps1`
4. **ทดสอบ:** `python test_api_routes.py`

