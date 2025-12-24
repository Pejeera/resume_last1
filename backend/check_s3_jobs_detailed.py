"""Check S3 jobs directory with detailed info"""
import boto3
import json

s3 = boto3.client('s3', region_name='ap-southeast-2')
bucket = 'resume-matching-533267343789'
prefix = 'resumes/jobs/'

print(f"Checking S3: s3://{bucket}/{prefix}")
print("=" * 70)

try:
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    
    if 'Contents' in response:
        # Filter out directories (keys ending with /)
        files = [obj for obj in response['Contents'] if not obj['Key'].endswith('/')]
        
        print(f"Found {len(files)} job files:\n")
        
        for i, obj in enumerate(files, 1):
            s3_key = obj['Key']
            file_size = obj['Size']
            last_modified = obj['LastModified']
            
            print(f"{i}. {s3_key}")
            print(f"   Size: {file_size} bytes")
            print(f"   Modified: {last_modified}")
            
            # Try to read and show details
            try:
                file_obj = s3.get_object(Bucket=bucket, Key=s3_key)
                content = file_obj['Body'].read().decode('utf-8')
                data = json.loads(content)
                
                if isinstance(data, dict):
                    print(f"   Title: {data.get('title', 'N/A')}")
                    print(f"   ID: {data.get('_id', data.get('id', data.get('job_id', 'N/A')))}")
                    if 'description' in data:
                        desc = data.get('description', '')[:100]
                        print(f"   Description: {desc}...")
                    if 'metadata' in data and data.get('metadata'):
                        meta = data.get('metadata', {})
                        if 'skills' in meta:
                            print(f"   Skills: {', '.join(meta.get('skills', []))}")
                elif isinstance(data, list):
                    print(f"   Contains {len(data)} jobs")
                    
            except json.JSONDecodeError as e:
                print(f"   Error parsing JSON: {e}")
            except Exception as e:
                print(f"   Error reading: {e}")
            
            print()
        
        print(f"Summary: {len(files)} job files found")
    else:
        print("No files found in resumes/jobs/")
        print("\nYou need to upload job files to S3:")
        print(f"   s3://{bucket}/{prefix}job-001.json")
        print(f"   s3://{bucket}/{prefix}job-002.json")
        print("   etc.")
        
except Exception as e:
    print(f"Error: {e}")

