"""check that the LLM is properly anonymizing personal data from resumes 
was for looking what he will do with the amonymized data
not in the unit testing taken"""

import asyncio
import re
import unittest
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from apps.backend.app.services.resume_service import ResumeService

DATABASE_URL = "sqlite+aiosqlite:///./test.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
RESUMES_DIR = "app/resumes_examples"

# Expected anonymization data
anonymization_data :dict = {
    "firstName": "Fname",
    "lastName": "Lname",
    "email": "EMAIL",
    "phone": "PHONE",
    "linkedin": "https://www.linkedin.com/x",
    "location": {
        "city": "CITY",
    }
}

class TestResumeService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Create a session and ResumeService before each test."""
        self.session = async_session()
        self.resume_service = ResumeService(db=self.session)

    '''async def asyncTearDown(self):
        """Close the session after each test."""
        await self.session.close()
'''
    async def test_all_resumes_anonymization(self):
        """Iterate over all PDF resumes and send it to the LLM and check anonymization."""
        for filename in os.listdir(RESUMES_DIR):
            file_path = os.path.join(RESUMES_DIR, filename)
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            text_content, _ = await self.resume_service.convert_and_store_resume(
                file_bytes=file_bytes,
                file_type="application/pdf",
                filename=filename,
                content_type="md",
                test_mode=True
            )
            print("sending data to LLM for structured extraction...")
            structured_data = await self.resume_service._extract_and_store_structured_resume(
                resume_id=None,
                resume_text=text_content,
                test_mode=True
            )
            #structured_data =  {'personal_data': {'firstName': 'Floran', 'lastName': 'Dens', 'email': 'floran.dens@gmail.com', 'phone': '+32 489 78 91 28', 'linkedin': 'null', 'portfolio': 'null', 'location': {'city': 'Mechelen', 'country': 'Belgium'}}, 'experiences': [{'job_title': 'Orderpicker Magazijn', 'company': 'Colruytgroep', 'location': 'null', 'start_date': '2021-07-01', 'end_date': 'Present', 'description': ['Efficiënte en nauwkeurige orderpicker bij Colruyt Group.', 'Ervaring in een dynamische magazijnomgeving met focus op kwaliteit, punctualiteit en veilig werken binnen logistieke processen'], 'technologies_used': []}, {'job_title': 'Stage software developer', 'company': 'Nokia bell labs', 'location': 'null', 'start_date': '2024-07-29', 'end_date': '2024-09-10', 'description': ['Ik heb tijdens deze stage geleerd om in grotere projecten te programmeren.', 'Een aantal componenten waren reeds geschreven, anderen dienden nog uitgewerkt te worden.', 'Ik heb ervaring opgedaan om in team te werken.'], 'technologies_used': []}, {'job_title': 'ICT-assistent PDSS', 'company': 'PDSS', 'location': 'null', 'start_date': '2021-01-01', 'end_date': '2022-12-31', 'description': ['Tijdens de weekends werkte ik hier als assistent.', 'Ik was verantwoordelijk voor het opzetten van 3CX voor klanten.', 'Ik heb hier ook websites gemaakt.', 'Ik werkte zelfstandig en leerde probleemoplossend te denken.'], 'technologies_used': []}], 'projects': [], 'skills': [{'category': 'Computer Knowledge', 'skill_name': 'Python'}, {'category': 'Computer Knowledge', 'skill_name': 'C'}, {'category': 'Computer Knowledge', 'skill_name': 'Java'}, {'category': 'Computer Knowledge', 'skill_name': 'Office'}, {'category': 'Social Skills', 'skill_name': 'Sociaal vaardig'}, {'category': 'Soft Skills', 'skill_name': 'Analytisch denken'}, {'category': 'Soft Skills', 'skill_name': 'Behulpzaamheid'}, {'category': 'Soft Skills', 'skill_name': 'Doorzettingsvermogen'}], 'research_work': [], 'achievements': [], 'education': [{'institution': 'KU Leuven campus De Nayer', 'degree': 'Industrieel ingenieur', 'field_of_study': 'null', 'start_date': '2021-09-27', 'end_date': 'Present', 'grade': 'null', 'description': 'Industrieel ingenieur'}, {'institution': 'Technische Scholen Mechelen', 'degree': 'Industriële Wetenschappen', 'field_of_study': 'null', 'start_date': '2014-09-01', 'end_date': '2021-06-30', 'grade': 'null', 'description': 'Industriële Wetenschappen'}], 'extracted_keywords': ['electronica-ICT', 'computernetwerken', 'cybersecurty', 'orderpicker', 'software developer', '3CX', 'websites']}
            print(f"Structured data for {filename}: {structured_data}")
            
            self.person_data : dict = structured_data.get("personal_data")
            #test firstname
            await self.assert_text_equal(
                result=self.person_data.get("firstName"),
                expected=anonymization_data.get("firstName")
            )
            #test lastname
            await self.assert_text_equal(
                result=self.person_data.get("lastName"),
                expected=anonymization_data.get("lastName")
            )
            #test email
            await self.assert_text_equal(
                result=self.person_data.get("email"),
                expected=anonymization_data.get("email")
            )
            #test phone
            await self.assert_text_equal(
                result=self.person_data.get("phone"),
                expected=anonymization_data.get("phone")
            )
            
            #test linkedin
            print(self.person_data.get("linkedin"))
            print(anonymization_data.get("linkedin"))  
            await self.assert_text_equal(
                result=self.person_data.get("linkedin"),
                expected=anonymization_data.get("linkedin")
            )
            #test location city
            location_data : dict = self.person_data.get("location")
            await self.assert_text_equal(
                result=location_data.get("city"),
                expected=anonymization_data.get("location").get("city")
            )
    
    async def assert_text_equal(self, result, expected):
        if result == "null" or result is None:
            return #skip test if data is present
        with self.subTest(result=result, expected=expected):
            self.assertEqual(result, expected)

if __name__ == "__main__":
    unittest.main()
