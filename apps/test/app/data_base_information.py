'''take every information from the database and print it to the console for debuging purposes
is only use for debuging and verifying'''

import os
import asyncio
import unittest
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from apps.backend.app.core.config import _DEFAULT_DB_PATH
from apps.backend.app.models import Resume, ProcessedResume, User, ProcessedJob

# Build correct SQLAlchemy async SQLite URL
DB_URL = f"sqlite+aiosqlite:///{_DEFAULT_DB_PATH}"

# Create async engine and session
engine = create_async_engine(DB_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def list_tables():
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table';")
            )
            tables = result.scalars().all()

            print("Tables in the database:")
            for table in tables:
                  print(f"- {table}")

async def read_job_resume_data(db: AsyncSession):
    """
    Reads all data from the job_resume table.

    Args:
        db (AsyncSession): The database session.

    Returns:
        List[JobResume]: A list of JobResume objects.
    """
    result = await db.execute(select(ProcessedJob))
    job_resumes = result.scalars().all()
    for job_resume in job_resumes:
        print(f"ID: {job_resume.id}")
        print(f"Job ID: {job_resume.job_id}")
        print(f"Resume ID: {job_resume.resume_id}")
        print(f"Processed At: {job_resume.processed_at}")
        print("-" * 40)  # Separator for readability

async def read_resumes(db: AsyncSession):
    """
    Reads all data from the resumes table.

    Args:
        db (AsyncSession): The database session.

    Returns:
        List[Resume]: A list of Resume objects.
    """
    result = await db.execute(select(Resume))
    resumes = result.scalars().all()

    for resume in resumes:
        print(f"ID: {resume.id}")
        print(f"Resume ID: {resume.resume_id}")
        print(f"Content Type: {resume.content_type}")
        print(f"Created At: {resume.created_at}")
        print("-" * 40)

async def read_processed_resumes(db: AsyncSession):
    """
    Reads all data from the processed_resumes table.

    Args:
        db (AsyncSession): The database session.
        """
    result = await db.execute(select(ProcessedResume))
    processed_resumes = result.scalars().all()

    for processed_resume in processed_resumes:
        print(f"ID: {processed_resume.id}")
        print(f"Resume ID: {processed_resume.resume_id}")
        print(f"Processed At: {processed_resume.processed_at}")
        print("-" * 40)
if __name__ == "__main__":
    async def main():
        async with async_session() as db:
            await read_job_resume_data(db)
            await read_resumes(db)
            await read_processed_resumes(db)
            await list_tables()

    asyncio.run(main())