#!/bin/bash
# Bash script to deploy Lambda function
# Usage: ./deploy_lambda.sh

FUNCTION_NAME="ResumeMatchAPI"
REGION="ap-southeast-1"
ZIP_FILE="lambda-deployment.zip"

echo "=========================================="
echo "Deploying Lambda Function"
echo "=========================================="
echo "Function: $FUNCTION_NAME"
echo "Region: $REGION"
echo ""

# Step 1: Install dependencies
echo "[1/4] Installing dependencies..."
pip install -r requirements.txt -t . --quiet
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

# Step 2: Create ZIP file
echo "[2/4] Creating deployment package..."
rm -f $ZIP_FILE

zip -r $ZIP_FILE . \
    -x "*.pyc" \
    -x "__pycache__/*" \
    -x "*.git/*" \
    -x "test_*.py" \
    -x "*.md" \
    -x ".env" \
    -x "*.log" \
    -x "*.ps1" \
    -x "*.sh" \
    > /dev/null

echo "Created: $ZIP_FILE ($(du -h $ZIP_FILE | cut -f1))"

# Step 3: Upload to Lambda
echo "[3/4] Uploading to Lambda..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file "fileb://$ZIP_FILE" \
    --region $REGION

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to upload to Lambda"
    exit 1
fi

echo "[4/4] Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Verify handler: lambda_function.handler"
echo "2. Test endpoint: /api/health"
echo "3. Check CloudWatch Logs if needed"

