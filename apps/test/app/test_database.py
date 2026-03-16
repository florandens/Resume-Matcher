import os
import asyncio
import unittest
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


from apps.backend.app.core.config import _DEFAULT_DB_PATH # Use the gloabal value for the database
from apps.backend.app.models import Resume, ProcessedResume, User

# Build correct SQLAlchemy async SQLite URL
DB_URL = f"sqlite+aiosqlite:///{_DEFAULT_DB_PATH}" # Use the same database that is created in the application 

# Create async engine and session
engine = create_async_engine(DB_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

def time_diffrents_with_now(past_time):
    '''take a past time and return the difference in days and hours with now'''
    now = datetime.now()
    delta = now - past_time
    days = delta.days
    hours = delta.seconds // 3600 #dalta.hours is not available
    return days, hours

def older_than(past_time, day_limit=7, hours_limit=0): #default 7 days, 0 hours but you can change it in the systemcall
    '''check if the past time is older than the day and hour limit'''
    days, hours = time_diffrents_with_now(past_time)
    return days > day_limit or (days == day_limit and hours > hours_limit)

class TestDatabaseAges(unittest.IsolatedAsyncioTestCase):
    async def test_time_of_resumes(self):
        '''check that all resumes in the database are not older than 4 days'''
        day_limit = 4
        hours_limit = 0
        async with async_session() as session:
            result = await session.execute(select(Resume))
            resumes = result.scalars().all() #take all resumes

            print("Resumes:")
            for resume in resumes: #go over every resume
                with self.subTest(resume_id=resume.resume_id):
                    days, hours = time_diffrents_with_now(resume.created_at) #get time difference
                    print(f"Processed Resume ID: {resume.resume_id}, Days old: {days}, Hours old: {hours}")
                    #assert that the resume is not older than the limit
                    self.assertFalse(older_than(resume.created_at, day_limit=day_limit, hours_limit=hours_limit), f"Resume {resume.resume_id} the past time is Days old: {days}, Hours old: {hours}")
                
                
    async def test_time_of_processed_resumes(self):
        '''check that all processed resumes in the database are not older than 4 days'''
        day_limit = 4
        hours_limit = 0
        async with async_session() as session:
            result = await session.execute(select(ProcessedResume))
            processed_resumes = result.scalars().all()
            
            print("\nProcessed Resumes:")
            for processed_resume in processed_resumes:
                with self.subTest(resume_id=processed_resume.resume_id):
                    days, hours = time_diffrents_with_now(processed_resume.processed_at)
                    print(f"Processed Resume ID: {processed_resume.resume_id}, Days old: {days}, Hours old: {hours}")
                    self.assertFalse(older_than(processed_resume.processed_at, day_limit=day_limit,hours_limit=hours_limit), f"Processed Resume {processed_resume.resume_id} the past time is Days old: {days}, Hours old: {hours}")  


    
if __name__ == "__main__":
    unittest.main() 