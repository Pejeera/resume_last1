#!/bin/bash

# Lambda Deployment Script for Linux/macOS/Git Bash
# Run from the backend directory

set -e  # Exit on error

echo "🚀 Starting Lambda deployment..."

# ลบของเก่า
echo "📦 Cleaning old build files..."
rm -rf build package.zip

# สร้างโฟลเดอร์ build
echo "📁 Creating build directory..."
mkdir build

# ติดตั้ง dependency แบบ Lambda-compatibl\6=-
echo "📥 Installing dependencies..."
pip install -r requirements.txt -t build/

# copy lambda code
echo "📋 Copying lambda function..."
cp lambda_function.py build/

# zip
echo "🗜️  Creating deployment package..."
cd build
zip -r ../package.zip .
cd ..

# deploy ขึ้น Lambda
echo "☁️  Deploying to AWS Lambda..."
aws lambda update-function-code \
  --function-name resume-search-api \
  --zip-file fileb://package.zip \
  --region ap-southeast-2

echo ""
echo "✅ Deployment completed successfully!"
echo "📦 Package: package.zip"
echo "🔧 Function: resume-search-api"
echo "🌍 Region: ap-southeast-2"

