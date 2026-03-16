import asyncio
import re
import unittest
import os
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from apps.backend.app.services.resume_service import ResumeService

DATABASE_URL = "sqlite+aiosqlite:///./test.db"  # for using the existing code you need to declare a database URL
engine = create_async_engine(DATABASE_URL, echo=False) 
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) # create session factory

# Regex patterns for phone and email
PHONE_REGEX = re.compile(r"\+?32[\s()-]*\d(?:[\s()-]*\d){7,9}")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
RESUMES_DIR = "app/resumes_examples" # Directory containing resumes and JSON data


class TestResumeService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Create a session and ResumeService before each test"""
        self.session = async_session()
        self.resume_service = ResumeService(db=self.session)

    async def asyncTearDown(self):
        """Close the session after each test."""
        await self.session.close()

    async def test_all_resumes_anonymization(self):
        """Iterate over all PDF resumes and check anonymization."""
        for filename in os.listdir(RESUMES_DIR):
            if not filename.lower().endswith(".pdf"): # Skip non-PDF files (json files is copled with pdf)
                continue
            print(f"Testing anonymization for {filename}...")  
            file_path_pdf = os.path.join(RESUMES_DIR, filename)
            with open(file_path_pdf, "rb") as f:
                file_bytes = f.read() # Read PDF file 
            file_path_json = file_path_pdf.replace(".pdf", ".json") # Corresponding JSON file -> have samen name as pdf only different file type
            with open(file_path_json, "r") as f:
                person_data = json.load(f)            

            text_content, _ = await self.resume_service.convert_and_store_resume(
                file_bytes=file_bytes,
                file_type="application/pdf",
                filename=filename,
                content_type="md",
                test_mode=True # Fix that the data is not sending to LLM (in function is creating en sending to LLM)
            ) # call the function in the applicaiton that responsible is for the resume convertion
            for key, value in person_data.items():
                '''It go over every personal data in the json file and check that this data is not in the converted text content'''
                print(f"Checking {key} is anonymized...")
                self.not_in_context(text_content, str(value)) # Check that each personal data is not in the converted text content

    def not_in_context(self, context, value):
        self.assertNotIn(value, context, f"{value} unexpectedly found in markdown context") 

if __name__ == "__main__":
    unittest.main()
