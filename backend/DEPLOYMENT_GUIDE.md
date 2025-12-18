# 🚀 Lambda Deployment Guide - Clean Build

## 📋 สรุปไฟล์ที่ควร zip

เมื่อ deploy Lambda ควรมีเฉพาะไฟล์เหล่านี้ใน zip:

```
lambda-deployment-clean.zip
├── lambda_function.py          # Lambda handler
├── main.py                     # FastAPI app
├── app/                        # Application code
│   ├── __init__.py
│   ├── clients/
│   ├── core/
│   ├── repositories/
│   ├── routers/
│   └── services/
└── python/                     # Dependencies (installed via Docker)
    ├── fastapi/
    ├── mangum/
    ├── pydantic/
    └── ... (other dependencies)
```

## ❌ ไฟล์ที่ห้ามมีใน zip (root level)

- `typing.py` - ชนกับ Python stdlib
- `http.py` - ชนกับ Python stdlib
- `json.py` - ชนกับ Python stdlib
- `asyncio.py` - ชนกับ Python stdlib
- `email.py` - ชนกับ Python stdlib

**หมายเหตุ:** ไฟล์เหล่านี้ใน packages (เช่น `fastapi/security/http.py`, `pydantic/typing.py`) **ไม่เป็นปัญหา** เพราะอยู่ใน subdirectory

## 🔧 การใช้งาน

### วิธีที่ 1: ใช้สคริปต์อัตโนมัติ (แนะนำ)

```powershell
cd backend
.\deploy_lambda_clean.ps1
```

สคริปต์จะ:
1. ✅ ตรวจสอบ source code ก่อน deploy
2. ✅ ลบ build artifacts และ installed packages ทั้งหมด
3. ✅ ติดตั้ง dependencies ใหม่ด้วย Docker (Linux-compatible)
4. ✅ Copy เฉพาะ source code ที่จำเป็น
5. ✅ ตรวจสอบและลบไฟล์ต้องห้าม
6. ✅ สร้าง zip และตรวจสอบอีกครั้ง
7. ✅ Deploy และ test อัตโนมัติ

### วิธีที่ 2: Manual Clean Build

```powershell
# 1. ลบทุกอย่าง
cd backend
Remove-Item -Recurse -Force build, dist, __pycache__, *.zip, lambda-package -ErrorAction SilentlyContinue

# 2. ตรวจสอบไฟล์ต้องห้าม
.\check_forbidden_files.ps1

# 3. Deploy
.\deploy_lambda_clean.ps1
```

## 🔍 ตรวจสอบ Lambda ที่ deploy แล้ว

### ดาวน์โหลด code จาก Lambda

```bash
aws lambda get-function \
  --function-name ResumeMatchAPI \
  --region us-east-1 \
  --query 'Code.Location' \
  --output text
```

เปิดลิงก์ใน browser → ดาวน์โหลด zip

### ตรวจสอบว่า Lambda ยังสกปรกหรือไม่

```bash
# ใช้ tar (Windows 10+ หรือ Git Bash)
tar -tf downloaded.zip | grep -E "^(typing|http)\.py$"

# หรือใช้ PowerShell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead("downloaded.zip")
$zip.Entries | Where-Object { $_.Name -in @("typing.py", "http.py") -and $_.FullName -notmatch '[\\/]' }
$zip.Dispose()
```

**ถ้าเห็น `var/task/typing.py` หรือ `var/task/http.py`** → Lambda ยังสกปรก ต้อง deploy ใหม่

## ✅ ผลลัพธ์ที่ถูกต้อง

หลัง deploy สำเร็จ:

- ✅ ไม่มี `Runtime.ImportModuleError`
- ✅ ไม่มี `typing.py` หรือ `http.py` ใน `/var/task/`
- ✅ Lambda init ผ่าน
- ✅ FastAPI / Mangum import ได้
- ✅ Error (ถ้ามี) จะเป็น logic-level ไม่ใช่ import error

## 🛡️ ป้องกันระยะยาว

### 1. ตั้งชื่อไฟล์ให้ปลอดภัย

❌ **ห้ามใช้:**
- `typing.py`
- `http.py`
- `json.py`
- `asyncio.py`
- `email.py`

✅ **ใช้แทน:**
- `typing_utils.py`
- `http_utils.py` หรือ `http_routes.py`
- `json_utils.py`
- `async_utils.py`
- `email_utils.py`

### 2. ตรวจสอบก่อน commit

```powershell
.\check_forbidden_files.ps1
```

### 3. ใช้ Docker สำหรับ dependencies

สคริปต์จะใช้ Docker อัตโนมัติเพื่อติดตั้ง dependencies แบบ Linux-compatible

## 🐛 Troubleshooting

### ปัญหา: Runtime.ImportModuleError

**สาเหตุ:** มีไฟล์ต้องห้ามใน zip

**แก้ไข:**
1. ตรวจสอบ source code: `.\check_forbidden_files.ps1`
2. ลบ build artifacts: `Remove-Item -Recurse -Force lambda-package, *.zip`
3. Deploy ใหม่: `.\deploy_lambda_clean.ps1`

### ปัญหา: Lambda ยังใช้ code เก่า

**แก้ไข:**
1. ตรวจสอบ code ที่ Lambda ใช้จริง (ดาวน์โหลด zip จาก Lambda)
2. ถ้ายังมีไฟล์ต้องห้าม → deploy ใหม่
3. รอ ~10 วินาที หลัง deploy แล้ว test อีกครั้ง

### ปัญหา: Dependencies ไม่ทำงาน

**สาเหตุ:** ใช้ Windows dependencies แทน Linux

**แก้ไข:**
1. เปิด Docker Desktop
2. รันสคริปต์ใหม่: `.\deploy_lambda_clean.ps1`
3. สคริปต์จะใช้ Docker อัตโนมัติ

## 📝 Checklist ก่อน Deploy

- [ ] Source code ไม่มีไฟล์ต้องห้าม (`.\check_forbidden_files.ps1`)
- [ ] ลบ build artifacts ทั้งหมด
- [ ] Docker พร้อมใช้งาน (สำหรับ dependencies)
- [ ] ตรวจสอบ zip ก่อน deploy (ไม่มี `typing.py` หรือ `http.py` ที่ root)
- [ ] Test Lambda หลัง deploy

---

**สรุป:** ใช้ `.\deploy_lambda_clean.ps1` แล้วสคริปต์จะจัดการทุกอย่างให้อัตโนมัติ! 🎉

