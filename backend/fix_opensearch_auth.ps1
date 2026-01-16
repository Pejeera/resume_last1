# Fix OpenSearch Authentication Issue
# This script provides instructions to fix the OpenSearch 403 error

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "OpenSearch Authentication Fix Guide" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[PROBLEM]" -ForegroundColor Red
Write-Host "Error: AuthorizationException(403, 'The security token included in the request is invalid.')" -ForegroundColor Yellow
Write-Host ""

Write-Host "[ROOT CAUSE]" -ForegroundColor Cyan
Write-Host "Lambda function's IAM role doesn't have permission to access OpenSearch" -ForegroundColor White
Write-Host "OR OpenSearch access policy doesn't allow the Lambda role" -ForegroundColor White
Write-Host ""

Write-Host "[SOLUTION]" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 1: Check Lambda IAM Role" -ForegroundColor Yellow
Write-Host "  1. Go to AWS Lambda Console" -ForegroundColor Gray
Write-Host "  2. Select your Lambda function" -ForegroundColor Gray
Write-Host "  3. Go to 'Configuration' -> 'Permissions'" -ForegroundColor Gray
Write-Host "  4. Click on the IAM role name" -ForegroundColor Gray
Write-Host "  5. Note the Role ARN (you'll need this)" -ForegroundColor Gray
Write-Host ""

Write-Host "Step 2: Add OpenSearch Permissions to Lambda Role" -ForegroundColor Yellow
Write-Host "  1. In IAM Console, select the Lambda role" -ForegroundColor Gray
Write-Host "  2. Click 'Add permissions' -> 'Create inline policy'" -ForegroundColor Gray
Write-Host "  3. Use JSON policy editor and add:" -ForegroundColor Gray
Write-Host ""
Write-Host '  {' -ForegroundColor White
Write-Host '    "Version": "2012-10-17",' -ForegroundColor White
Write-Host '    "Statement": [' -ForegroundColor White
Write-Host '      {' -ForegroundColor White
Write-Host '        "Effect": "Allow",' -ForegroundColor White
Write-Host '        "Action": [' -ForegroundColor White
Write-Host '          "es:ESHttpGet",' -ForegroundColor White
Write-Host '          "es:ESHttpPost",' -ForegroundColor White
Write-Host '          "es:ESHttpPut",' -ForegroundColor White
Write-Host '          "es:DescribeElasticsearchDomain",' -ForegroundColor White
Write-Host '          "es:DescribeDomain",' -ForegroundColor White
Write-Host '          "aoss:APIAccessAll"' -ForegroundColor White
Write-Host '        ],' -ForegroundColor White
Write-Host '        "Resource": "arn:aws:es:ap-southeast-2:*:domain/*/*"' -ForegroundColor White
Write-Host '      }' -ForegroundColor White
Write-Host '    ]' -ForegroundColor White
Write-Host '  }' -ForegroundColor White
Write-Host ""
Write-Host "  4. Replace 'ap-southeast-2' with your region if different" -ForegroundColor Gray
Write-Host "  5. For OpenSearch Serverless, use 'aoss:APIAccessAll' instead" -ForegroundColor Gray
Write-Host ""

Write-Host "Step 3: Update OpenSearch Access Policy" -ForegroundColor Yellow
Write-Host ""

Write-Host "  For OpenSearch Service (Managed):" -ForegroundColor Cyan
Write-Host "  1. Go to OpenSearch Service Console" -ForegroundColor Gray
Write-Host "  2. Select your domain" -ForegroundColor Gray
Write-Host "  3. Go to 'Access policy' tab" -ForegroundColor Gray
Write-Host "  4. Add policy to allow Lambda role:" -ForegroundColor Gray
Write-Host ""
Write-Host '  {' -ForegroundColor White
Write-Host '    "Effect": "Allow",' -ForegroundColor White
Write-Host '    "Principal": {' -ForegroundColor White
Write-Host '      "AWS": "arn:aws:iam::ACCOUNT_ID:role/LAMBDA_ROLE_NAME"' -ForegroundColor White
Write-Host '    },' -ForegroundColor White
Write-Host '    "Action": "es:*",' -ForegroundColor White
Write-Host '    "Resource": "arn:aws:es:REGION:ACCOUNT_ID:domain/DOMAIN_NAME/*"' -ForegroundColor White
Write-Host '  }' -ForegroundColor White
Write-Host ""
Write-Host "  5. Replace:" -ForegroundColor Gray
Write-Host "     - ACCOUNT_ID: Your AWS account ID" -ForegroundColor Gray
Write-Host "     - LAMBDA_ROLE_NAME: Your Lambda IAM role name" -ForegroundColor Gray
Write-Host "     - REGION: Your region (e.g., ap-southeast-2)" -ForegroundColor Gray
Write-Host "     - DOMAIN_NAME: Your OpenSearch domain name" -ForegroundColor Gray
Write-Host ""

Write-Host "  For OpenSearch Serverless:" -ForegroundColor Cyan
Write-Host "  1. Go to OpenSearch Serverless Console" -ForegroundColor Gray
Write-Host "  2. Select your collection" -ForegroundColor Gray
Write-Host "  3. Go to 'Access policies' tab" -ForegroundColor Gray
Write-Host "  4. Add policy:" -ForegroundColor Gray
Write-Host ""
Write-Host '  [' -ForegroundColor White
Write-Host '    {' -ForegroundColor White
Write-Host '      "Rules": [' -ForegroundColor White
Write-Host '        {' -ForegroundColor White
Write-Host '          "ResourceType": "collection",' -ForegroundColor White
Write-Host '          "Resource": ["collection/COLLECTION_NAME"],' -ForegroundColor White
Write-Host '          "Permission": [' -ForegroundColor White
Write-Host '            "aoss:CreateCollectionItems",' -ForegroundColor White
Write-Host '            "aoss:UpdateCollectionItems",' -ForegroundColor White
Write-Host '            "aoss:DescribeCollectionItems",' -ForegroundColor White
Write-Host '            "aoss:DeleteCollectionItems"' -ForegroundColor White
Write-Host '          ]' -ForegroundColor White
Write-Host '        }' -ForegroundColor White
Write-Host '      ],' -ForegroundColor White
Write-Host '      "Principal": ["arn:aws:iam::ACCOUNT_ID:role/LAMBDA_ROLE_NAME"],' -ForegroundColor White
Write-Host '      "Description": "Allow Lambda to access OpenSearch Serverless"' -ForegroundColor White
Write-Host '    }' -ForegroundColor White
Write-Host '  ]' -ForegroundColor White
Write-Host ""

Write-Host "Step 4: Verify OpenSearch Endpoint" -ForegroundColor Yellow
Write-Host "  1. Check Lambda environment variables:" -ForegroundColor Gray
Write-Host "     - OPENSEARCH_ENDPOINT: Should be your OpenSearch domain endpoint" -ForegroundColor Gray
Write-Host "     - AWS_REGION: Should match OpenSearch region" -ForegroundColor Gray
Write-Host "  2. Format: https://search-DOMAIN-NAME-REGION.es.amazonaws.com" -ForegroundColor Gray
Write-Host "  3. For Serverless: https://COLLECTION-ID.REGION.aoss.amazonaws.com" -ForegroundColor Gray
Write-Host ""

Write-Host "Step 5: Test After Fix" -ForegroundColor Yellow
Write-Host "  1. Try uploading resume again" -ForegroundColor Gray
Write-Host "  2. Check CloudWatch Logs for Lambda function" -ForegroundColor Gray
Write-Host "  3. Look for OpenSearch connection errors" -ForegroundColor Gray
Write-Host ""

Write-Host "[QUICK CHECK]" -ForegroundColor Cyan
Write-Host "Run this AWS CLI command to check Lambda role:" -ForegroundColor White
Write-Host '  aws lambda get-function-configuration --function-name YOUR_FUNCTION_NAME --query "Role"' -ForegroundColor Yellow
Write-Host ""
Write-Host "Then check the role permissions:" -ForegroundColor White
Write-Host '  aws iam list-attached-role-policies --role-name ROLE_NAME' -ForegroundColor Yellow
Write-Host '  aws iam list-role-policies --role-name ROLE_NAME' -ForegroundColor Yellow
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan

