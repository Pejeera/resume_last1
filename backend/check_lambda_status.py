"""
ตรวจสอบสถานะ Lambda Function และ CloudWatch Logs
"""
import subprocess
import json
import sys
from datetime import datetime, timedelta

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

LAMBDA_FUNCTION_NAME = "ResumeMatchAPI"
REGION = "us-east-1"

def run_aws_command(command):
    """Run AWS CLI command and return result"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def check_lambda_config():
    """Check Lambda function configuration"""
    print_header("🔧 ตรวจสอบ Lambda Configuration")
    
    # Get function configuration
    command = f'aws lambda get-function-configuration --function-name {LAMBDA_FUNCTION_NAME} --region {REGION}'
    success, output, error = run_aws_command(command)
    
    if not success:
        print(f"❌ ไม่สามารถดึงข้อมูล Lambda function ได้")
        print(f"   Error: {error}")
        print(f"\n💡 ตรวจสอบ:")
        print(f"   1. AWS CLI configured หรือไม่ (aws configure)")
        print(f"   2. Lambda function name ถูกต้อง: {LAMBDA_FUNCTION_NAME}")
        print(f"   3. Region ถูกต้อง: {REGION}")
        print(f"   4. มี permissions ในการเข้าถึง Lambda")
        return False
    
    try:
        config = json.loads(output)
        print(f"✅ พบ Lambda function")
        print(f"\n📋 Configuration:")
        print(f"   Function Name: {config.get('FunctionName', 'N/A')}")
        print(f"   Runtime: {config.get('Runtime', 'N/A')}")
        print(f"   Handler: {config.get('Handler', 'N/A')}")
        print(f"   Memory Size: {config.get('MemorySize', 'N/A')} MB")
        print(f"   Timeout: {config.get('Timeout', 'N/A')} seconds")
        print(f"   Last Modified: {config.get('LastModified', 'N/A')}")
        print(f"   State: {config.get('State', 'N/A')}")
        print(f"   StateReason: {config.get('StateReason', 'N/A')}")
        
        # Check environment variables
        env_vars = config.get('Environment', {}).get('Variables', {})
        if env_vars:
            print(f"\n🔐 Environment Variables:")
            important_vars = ['USE_MOCK', 'S3_BUCKET_NAME', 'OPENSEARCH_ENDPOINT', 'AWS_REGION']
            for var in important_vars:
                value = env_vars.get(var, 'Not set')
                if var in ['OPENSEARCH_PASSWORD', 'AWS_SECRET_ACCESS_KEY']:
                    value = '[HIDDEN]' if value != 'Not set' else 'Not set'
                print(f"   {var}: {value}")
        
        # Check if function is active
        state = config.get('State', '')
        if state != 'Active':
            print(f"\n⚠️  Warning: Lambda function state is '{state}'")
            print(f"   StateReason: {config.get('StateReason', 'N/A')}")
        
        return True
    except json.JSONDecodeError:
        print(f"❌ ไม่สามารถ parse JSON response ได้")
        print(f"   Output: {output}")
        return False

def check_recent_logs():
    """Check recent CloudWatch Logs"""
    print_header("📜 ตรวจสอบ CloudWatch Logs (ล่าสุด)")
    
    log_group = f"/aws/lambda/{LAMBDA_FUNCTION_NAME}"
    
    # Get recent log streams (last 1 hour)
    start_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
    
    command = f'aws logs describe-log-streams --log-group-name "{log_group}" --region {REGION} --order-by LastEventTime --descending --max-items 5'
    success, output, error = run_aws_command(command)
    
    if not success:
        print(f"⚠️  ไม่สามารถดึง log streams ได้")
        print(f"   Error: {error}")
        print(f"\n💡 ตรวจสอบ:")
        print(f"   1. CloudWatch Logs permissions")
        print(f"   2. Log group exists: {log_group}")
        return
    
    try:
        streams_data = json.loads(output)
        streams = streams_data.get('logStreams', [])
        
        if not streams:
            print(f"⚠️  ไม่พบ log streams ล่าสุด")
            print(f"   อาจยังไม่มี invocation หรือ logs ยังไม่ถูกสร้าง")
            return
        
        print(f"✅ พบ {len(streams)} log streams ล่าสุด")
        
        # Get events from the most recent stream
        latest_stream = streams[0]
        stream_name = latest_stream.get('logStreamName', '')
        
        print(f"\n📄 Log Stream: {stream_name}")
        print(f"   Last Event: {datetime.fromtimestamp(latest_stream.get('lastEventTimestamp', 0) / 1000)}")
        
        # Get log events
        command = f'aws logs get-log-events --log-group-name "{log_group}" --log-stream-name "{stream_name}" --region {REGION} --limit 50'
        success, output, error = run_aws_command(command)
        
        if success:
            events_data = json.loads(output)
            events = events_data.get('events', [])
            
            if events:
                print(f"\n📝 Recent Log Events (last {len(events)} events):")
                print("-" * 70)
                
                # Show last 20 events
                for event in events[-20:]:
                    timestamp = datetime.fromtimestamp(event.get('timestamp', 0) / 1000)
                    message = event.get('message', '')
                    
                    # Highlight errors
                    if 'ERROR' in message or 'Exception' in message or 'Traceback' in message:
                        print(f"❌ [{timestamp.strftime('%H:%M:%S')}] {message}")
                    elif 'WARNING' in message or 'WARN' in message:
                        print(f"⚠️  [{timestamp.strftime('%H:%M:%S')}] {message}")
                    else:
                        print(f"   [{timestamp.strftime('%H:%M:%S')}] {message}")
            else:
                print(f"⚠️  ไม่พบ log events ใน stream นี้")
        else:
            print(f"⚠️  ไม่สามารถดึง log events ได้: {error}")
            
    except json.JSONDecodeError:
        print(f"❌ ไม่สามารถ parse JSON response ได้")
        print(f"   Output: {output}")

def check_lambda_invocations():
    """Check recent Lambda invocations"""
    print_header("📊 ตรวจสอบ Lambda Invocations")
    
    # Get metrics for errors
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)
    
    command = f'aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Errors --dimensions Name=FunctionName,Value={LAMBDA_FUNCTION_NAME} --start-time {start_time.isoformat()} --end-time {end_time.isoformat()} --period 300 --statistics Sum --region {REGION}'
    success, output, error = run_aws_command(command)
    
    if success:
        try:
            metrics = json.loads(output)
            datapoints = metrics.get('Datapoints', [])
            if datapoints:
                total_errors = sum(dp.get('Sum', 0) for dp in datapoints)
                print(f"❌ Total Errors (last hour): {int(total_errors)}")
            else:
                print(f"✅ No errors in the last hour")
        except:
            pass
    
    # Get invocations
    command = f'aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Invocations --dimensions Name=FunctionName,Value={LAMBDA_FUNCTION_NAME} --start-time {start_time.isoformat()} --end-time {end_time.isoformat()} --period 300 --statistics Sum --region {REGION}'
    success, output, error = run_aws_command(command)
    
    if success:
        try:
            metrics = json.loads(output)
            datapoints = metrics.get('Datapoints', [])
            if datapoints:
                total_invocations = sum(dp.get('Sum', 0) for dp in datapoints)
                print(f"📞 Total Invocations (last hour): {int(total_invocations)}")
            else:
                print(f"⚠️  No invocations in the last hour")
        except:
            pass

def main():
    print_header("🔍 ตรวจสอบ Lambda Function Status")
    print(f"Function: {LAMBDA_FUNCTION_NAME}")
    print(f"Region: {REGION}")
    print(f"เวลา: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if AWS CLI is configured
    success, output, error = run_aws_command('aws sts get-caller-identity')
    if not success:
        print("\n❌ AWS CLI ไม่ได้ configure หรือไม่มี permissions")
        print("   กรุณา run: aws configure")
        return
    
    # Check Lambda configuration
    if check_lambda_config():
        # Check recent logs
        check_recent_logs()
        
        # Check invocations
        check_lambda_invocations()
    
    print_header("💡 แนะนำการแก้ไข")
    print("ถ้า Lambda มีปัญหา:")
    print("1. ตรวจสอบ CloudWatch Logs สำหรับ error details")
    print("2. ตรวจสอบ Lambda timeout (อาจต้องเพิ่ม)")
    print("3. ตรวจสอบ Lambda memory (อาจต้องเพิ่ม)")
    print("4. ตรวจสอบ Lambda execution role permissions")
    print("5. ตรวจสอบ Lambda environment variables")
    print("6. ตรวจสอบ dependencies ใน Lambda package")
    print("\nสำหรับ 502 errors:")
    print("- Lambda function อาจ timeout")
    print("- Lambda function อาจมี import errors")
    print("- Lambda function อาจมี runtime errors")
    print("- ตรวจสอบ Lambda logs ใน CloudWatch")

if __name__ == "__main__":
    main()

