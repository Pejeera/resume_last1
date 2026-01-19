"""
Script to delete all resumes from both S3 and OpenSearch
Use this script to clean up all resume data for testing
"""
import sys
import os
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.clients.s3_client import s3_client
from app.clients.opensearch_client import opensearch_client
from app.core.logging import get_logger
import boto3
from botocore.exceptions import ClientError

logger = get_logger(__name__)


def delete_all_resumes_from_s3():
    """Delete all resumes from S3"""
    print("\n" + "="*60)
    print("กำลังลบ Resume จาก S3...")
    print("="*60)
    
    if settings.USE_MOCK:
        print("⚠️  MOCK MODE: ไม่มีการลบจาก S3 จริง")
        return {"deleted_count": 0, "errors": []}
    
    deleted_count = 0
    errors = []
    
    try:
        # Get S3 client
        if hasattr(s3_client, 'client') and s3_client.client:
            s3_client_boto = s3_client.client
        else:
            s3_client_boto = boto3.client('s3', region_name=settings.AWS_REGION)
        
        # List all files in resumes/Candidate/ prefix
        candidate_prefix = f"{settings.S3_PREFIX}Candidate/"
        print(f"กำลังค้นหาไฟล์ใน S3: bucket={settings.S3_BUCKET_NAME}, prefix={candidate_prefix}")
        
        paginator = s3_client_boto.get_paginator('list_objects_v2')
        all_keys = []
        
        for page in paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=candidate_prefix):
            if 'Contents' in page:
                for obj in page['Contents']:
                    all_keys.append(obj['Key'])
        
        print(f"พบไฟล์ทั้งหมด {len(all_keys)} ไฟล์")
        
        if len(all_keys) == 0:
            print("✅ ไม่มีไฟล์ใน S3 ที่ต้องลบ")
            return {"deleted_count": 0, "errors": []}
        
        # Delete all files
        print(f"กำลังลบ {len(all_keys)} ไฟล์...")
        for i, key in enumerate(all_keys, 1):
            try:
                s3_client_boto.delete_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=key
                )
                deleted_count += 1
                if i % 10 == 0 or i == len(all_keys):
                    print(f"  ลบแล้ว {i}/{len(all_keys)} ไฟล์...")
            except ClientError as e:
                error_msg = f"Error deleting {key}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        print(f"✅ ลบจาก S3 เสร็จสิ้น: {deleted_count}/{len(all_keys)} ไฟล์")
        if errors:
            print(f"⚠️  มีข้อผิดพลาด {len(errors)} รายการ")
        
        return {"deleted_count": deleted_count, "errors": errors}
        
    except Exception as e:
        error_msg = f"Error deleting from S3: {str(e)}"
        logger.error(error_msg)
        print(f"❌ {error_msg}")
        return {"deleted_count": deleted_count, "errors": [error_msg]}


def delete_all_resumes_from_opensearch():
    """Delete all resumes from OpenSearch"""
    print("\n" + "="*60)
    print("กำลังลบ Resume จาก OpenSearch...")
    print("="*60)
    
    deleted_count = 0
    errors = []
    index_name = "resumes_index"
    
    try:
        if settings.USE_MOCK:
            # Mock mode - clear mock storage
            if index_name in opensearch_client._mock_data_storage:
                count = len(opensearch_client._mock_data_storage[index_name])
                opensearch_client._mock_data_storage[index_name] = []
                deleted_count = count
                print(f"✅ ลบจาก Mock Storage: {deleted_count} documents")
            else:
                print("✅ ไม่มีข้อมูลใน Mock Storage")
            return {"deleted_count": deleted_count, "errors": []}
        
        # Real OpenSearch - use delete_by_query for efficiency
        print(f"กำลังลบ documents ทั้งหมดจาก index: {index_name}")
        
        # First, count total documents
        try:
            count_response = opensearch_client.client.count(index=index_name)
            total_count = count_response['count']
            print(f"พบ documents ทั้งหมด {total_count} รายการ")
            
            if total_count == 0:
                print("✅ ไม่มี documents ใน OpenSearch ที่ต้องลบ")
                return {"deleted_count": 0, "errors": []}
        except Exception as count_error:
            logger.warning(f"Could not count documents: {count_error}")
            total_count = 0
        
        # Use delete_by_query to delete all documents
        print(f"กำลังลบ {total_count} documents...")
        try:
            delete_query = {
                "query": {
                    "match_all": {}
                }
            }
            
            # Use delete_by_query API (more efficient than deleting one by one)
            response = opensearch_client.client.delete_by_query(
                index=index_name,
                body=delete_query,
                wait_for_completion=True,
                refresh=True
            )
            
            deleted_count = response.get('deleted', 0)
            print(f"✅ ลบจาก OpenSearch เสร็จสิ้น: {deleted_count} documents")
            
        except Exception as delete_error:
            # Fallback: try deleting one by one if delete_by_query fails
            error_msg = f"delete_by_query failed: {str(delete_error)}, trying individual deletion..."
            logger.warning(error_msg)
            print(f"⚠️  {error_msg}")
            
            # Fallback to individual deletion
            try:
                search_query = {
                    "query": {"match_all": {}},
                    "size": 1000,
                    "_source": False
                }
                
                response = opensearch_client.client.search(
                    index=index_name,
                    body=search_query,
                    scroll='2m'
                )
                
                scroll_id = response.get('_scroll_id')
                hits = response['hits']['hits']
                all_doc_ids = [hit['_id'] for hit in hits]
                
                while len(hits) > 0 and scroll_id:
                    response = opensearch_client.client.scroll(
                        scroll_id=scroll_id,
                        scroll='2m'
                    )
                    scroll_id = response.get('_scroll_id')
                    hits = response['hits']['hits']
                    all_doc_ids.extend([hit['_id'] for hit in hits])
                
                print(f"กำลังลบ {len(all_doc_ids)} documents ทีละรายการ...")
                for i, doc_id in enumerate(all_doc_ids, 1):
                    try:
                        if opensearch_client.delete_document(index_name=index_name, doc_id=doc_id):
                            deleted_count += 1
                        if i % 10 == 0 or i == len(all_doc_ids):
                            print(f"  ลบแล้ว {i}/{len(all_doc_ids)} documents...")
                    except Exception as e:
                        errors.append(f"Error deleting {doc_id}: {str(e)}")
                
                print(f"✅ ลบจาก OpenSearch เสร็จสิ้น: {deleted_count}/{len(all_doc_ids)} documents")
            except Exception as fallback_error:
                error_msg = f"Fallback deletion also failed: {str(fallback_error)}"
                errors.append(error_msg)
                logger.error(error_msg)
        if errors:
            print(f"⚠️  มีข้อผิดพลาด {len(errors)} รายการ")
        
        return {"deleted_count": deleted_count, "errors": errors}
        
    except Exception as e:
        error_msg = f"Error deleting from OpenSearch: {str(e)}"
        logger.error(error_msg)
        print(f"❌ {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        return {"deleted_count": deleted_count, "errors": [error_msg]}


def main():
    """Main function to delete all resumes"""
    print("\n" + "="*60)
    print("สคริปต์ลบ Resume ทั้งหมดจาก S3 และ OpenSearch")
    print("="*60)
    print(f"S3 Bucket: {settings.S3_BUCKET_NAME}")
    print(f"S3 Prefix: {settings.S3_PREFIX}")
    print(f"OpenSearch Endpoint: {settings.OPENSEARCH_ENDPOINT}")
    print(f"OpenSearch Index: resumes_index")
    print(f"Mock Mode: {settings.USE_MOCK}")
    
    # Confirm before deletion
    print("\n⚠️  คำเตือน: การดำเนินการนี้จะลบ Resume ทั้งหมดจาก S3 และ OpenSearch")
    
    # Check for --yes flag or auto-confirm in non-interactive mode
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    
    if not auto_confirm:
        # Check if running in interactive mode
        if sys.stdin.isatty():
            # Interactive mode - ask for confirmation
            try:
                response = input("ต้องการดำเนินการต่อหรือไม่? (yes/no): ")
                if response.lower() not in ['yes', 'y', 'ใช่']:
                    print("❌ ยกเลิกการดำเนินการ")
                    return
            except (EOFError, KeyboardInterrupt):
                print("\n❌ ยกเลิกการดำเนินการ")
                return
        else:
            # Non-interactive mode - auto-confirm
            print("⚠️  Non-interactive mode: Auto-confirming deletion...")
    else:
        print("⚠️  Auto-confirm mode: Proceeding with deletion...")
    
    # Delete from S3
    s3_result = delete_all_resumes_from_s3()
    
    # Delete from OpenSearch
    opensearch_result = delete_all_resumes_from_opensearch()
    
    # Summary
    print("\n" + "="*60)
    print("สรุปผลการลบ")
    print("="*60)
    print(f"S3: ลบแล้ว {s3_result['deleted_count']} ไฟล์")
    if s3_result['errors']:
        print(f"  ⚠️  ข้อผิดพลาด: {len(s3_result['errors'])} รายการ")
    
    print(f"OpenSearch: ลบแล้ว {opensearch_result['deleted_count']} documents")
    if opensearch_result['errors']:
        print(f"  ⚠️  ข้อผิดพลาด: {len(opensearch_result['errors'])} รายการ")
    
    total_deleted = s3_result['deleted_count'] + opensearch_result['deleted_count']
    print(f"\n✅ ลบทั้งหมด: {total_deleted} รายการ")
    print("="*60)


if __name__ == "__main__":
    main()
