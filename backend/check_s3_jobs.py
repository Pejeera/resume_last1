"""Check S3 jobs directory"""
import boto3
import json

s3 = boto3.client('s3', region_name='ap-southeast-2')
bucket = 'resume-matching-533267343789'
prefix = 'resumes/jobs/'

print(f"Checking S3: s3://{bucket}/{prefix}")
print("=" * 60)

try:
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    
    if 'Contents' in response:
        print(f"Found {len(response['Contents'])} files:")
        for obj in response['Contents']:
            print(f"  - {obj['Key']}")
            # Try to read and show first few chars
            try:
                file_obj = s3.get_object(Bucket=bucket, Key=obj['Key'])
                content = file_obj['Body'].read().decode('utf-8')
                data = json.loads(content)
                if isinstance(data, dict):
                    print(f"    Title: {data.get('title', 'N/A')}")
                elif isinstance(data, list):
                    print(f"    Contains {len(data)} jobs")
            except Exception as e:
                print(f"    Error reading: {e}")
    else:
        print("❌ No files found in resumes/jobs/")
        print("\n💡 You need to upload job files to S3:")
        print(f"   s3://{bucket}/{prefix}job-001.json")
        print(f"   s3://{bucket}/{prefix}job-002.json")
        print("   etc.")
        
except Exception as e:
    print(f"❌ Error: {e}")

