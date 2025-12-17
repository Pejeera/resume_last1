"""
Seed script to create ~100 job positions for testing.

รันไฟล์นี้เพื่อสร้างตำแหน่งงานตัวอย่างลงใน OpenSearch (หรือ MOCK storage ถ้า USE_MOCK=true)
"""

from typing import List, Dict
from datetime import datetime

from app.repositories.job_repository import job_repository
from app.core.config import settings
from app.core.logging import setup_logging, get_logger


logger = setup_logging()
logger = get_logger(__name__)


def build_job_definitions() -> List[Dict]:
    """Build a list of diverse job definitions (~100)."""
    base_jobs = [
        {
            "category": "Backend",
            "title": "Backend Engineer",
            "stack": "Python, FastAPI, PostgreSQL, Redis, Docker, AWS",
        },
        {
            "category": "Backend",
            "title": "Python Backend Developer",
            "stack": "Python, Django/FastAPI, REST API, Celery, AWS Lambda",
        },
        {
            "category": "Frontend",
            "title": "Frontend Engineer",
            "stack": "JavaScript, TypeScript, React, Next.js, Tailwind CSS",
        },
        {
            "category": "Full-Stack",
            "title": "Full-Stack Engineer",
            "stack": "React, Node.js / Python, REST/GraphQL, Docker, CI/CD",
        },
        {
            "category": "Data",
            "title": "Data Engineer",
            "stack": "Python, SQL, ETL, Airflow, Spark, Data Warehouse",
        },
        {
            "category": "Data",
            "title": "Data Scientist",
            "stack": "Python, Pandas, Scikit-learn, ML model deployment",
        },
        {
            "category": "DevOps",
            "title": "DevOps Engineer",
            "stack": "CI/CD, Docker, Kubernetes, Terraform, AWS/GCP",
        },
        {
            "category": "Cloud",
            "title": "Cloud Engineer (AWS)",
            "stack": "AWS, VPC, EC2, Lambda, API Gateway, RDS, OpenSearch",
        },
        {
            "category": "AI/ML",
            "title": "Machine Learning Engineer",
            "stack": "Python, ML models, MLOps, GPU, cloud deployment",
        },
        {
            "category": "AI/LLM",
            "title": "Generative AI Engineer",
            "stack": "LLM, Prompt Engineering, Vector DB, Bedrock / OpenAI",
        },
        {
            "category": "Mobile",
            "title": "Mobile Developer",
            "stack": "Flutter / React Native, REST API, CI/CD",
        },
        {
            "category": "QA",
            "title": "QA Automation Engineer",
            "stack": "Automated testing, Cypress / Playwright, API testing",
        },
        {
            "category": "Product",
            "title": "Product Manager (Tech)",
            "stack": "Agile, Product discovery, Roadmap planning, Analytics",
        },
    ]

    levels = [
        ("Junior", "0-2 ปี", "โฟกัสการเรียนรู้และทำงานร่วมกับทีม"),
        ("Mid", "2-5 ปี", "รับผิดชอบ feature ตั้งแต่ design ถึง deploy"),
        ("Senior", "5+ ปี", "ออกแบบสถาปัตยกรรมและเป็น technical lead บางส่วน"),
        ("Lead", "7+ ปี", "วาง technical vision และโค้ชทีม"),
    ]

    work_modes = [
        ("Onsite", "Bangkok"),
        ("Hybrid", "Bangkok"),
        ("Remote", "Anywhere (ASEAN preferred)"),
    ]

    job_defs: List[Dict] = []

    for base in base_jobs:
        for level_name, exp_text, resp_text in levels:
            for work_mode, location in work_modes:
                title = f"{level_name} {base['title']}"
                description = (
                    f"เรากำลังมองหา {level_name} {base['title']} ทำงานแบบ {work_mode} ที่ {location}.\n\n"
                    f"ประสบการณ์ที่ต้องการ: {exp_text}.\n\n"
                    f"Tech Stack หลัก: {base['stack']}.\n\n"
                    f"ความรับผิดชอบหลัก:\n"
                    f"- {resp_text}\n"
                    f"- ทำงานร่วมกับทีม cross-functional (Product, Design, QA)\n"
                    f"- รักษาคุณภาพโค้ดและมาตรฐานด้าน security/performance\n\n"
                    f"คุณสมบัติที่คาดหวัง:\n"
                    f"- มีพื้นฐานที่ดีด้าน Computer Science หรือประสบการณ์ทำงานจริง\n"
                    f"- สื่อสารและทำงานเป็นทีมได้ดี\n"
                    f"- พร้อมเรียนรู้เทคโนโลยีใหม่ ๆ อย่างต่อเนื่อง\n"
                )

                metadata = {
                    "category": base["category"],
                    "level": level_name,
                    "work_mode": work_mode,
                    "location": location,
                    "created_by": "seed_script",
                    "created_at_human": datetime.utcnow().isoformat(),
                }

                job_defs.append(
                    {
                        "title": title,
                        "description": description,
                        "metadata": metadata,
                    }
                )

    # เราจะใช้เฉพาะ 100 ตัวแรกเพื่อไม่ให้เยอะเกินไป
    return job_defs[:100]


def seed_jobs() -> None:
    """Create ~100 jobs via JobRepository."""
    logger.info("Starting job seeding...")
    logger.info(f"USE_MOCK={settings.USE_MOCK} (ถ้า true จะไม่เรียก AWS จริง)")

    job_defs = build_job_definitions()
    created = 0

    for job in job_defs:
        try:
            result = job_repository.create_job(
                title=job["title"],
                description=job["description"],
                metadata=job["metadata"],
            )
            created += 1
            logger.info(f"[{created:03d}] Created job: {result['job_id']} - {result['title']}")
        except Exception as e:
            logger.error(f"Failed to create job '{job['title']}': {e}")

    logger.info(f"Job seeding completed. Total created: {created}")
    
    # Save to S3 after seeding
    if settings.USE_MOCK:
        from app.clients.opensearch_client import opensearch_client
        from app.clients.s3_client import s3_client
        jobs_data = opensearch_client._mock_data_storage.get("jobs_index", [])
        if jobs_data:
            s3_client.save_jobs_data(jobs_data)
            logger.info(f"Saved {len(jobs_data)} jobs to S3")


if __name__ == "__main__":
    seed_jobs()


