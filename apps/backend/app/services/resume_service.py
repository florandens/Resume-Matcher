import os
import uuid
import json
import tempfile
import logging
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import selectinload 
from markitdown import MarkItDown
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import ValidationError
from typing import Dict, Optional, Union 

'''from app.models import Resume, ProcessedResume
from apps.backend.app.agent import AgentManager
from app.prompt import prompt_factory
from app.schemas.json import json_schema_factory
from app.schemas.pydantic import StructuredResumeModel'''

from apps.backend.app.models import Resume, ProcessedResume, Job
from apps.backend.app.agent import AgentManager
from apps.backend.app.prompt import prompt_factory
from apps.backend.app.schemas.json import json_schema_factory
from apps.backend.app.schemas.pydantic import StructuredResumeModel

from .exceptions import ResumeNotFoundError, ResumeValidationError

logger = logging.getLogger(__name__)

class ResumeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.md = MarkItDown(enable_plugins=False)
        self.json_agent_manager = AgentManager()
        
        # Validate dependencies for DOCX processing
        self._validate_docx_dependencies()

    def _validate_docx_dependencies(self):
        """Validate that required dependencies for DOCX processing are available"""
        missing_deps = []
        
        try:
            # Check if markitdown can handle docx files
            from markitdown.converters import DocxConverter
            # Try to instantiate the converter to check if dependencies are available
            DocxConverter()
        except ImportError:
            missing_deps.append("markitdown[all]==0.1.2")
        except Exception as e:
            if "MissingDependencyException" in str(e) or "dependencies needed to read .docx files" in str(e):
                missing_deps.append("markitdown[all]==0.1.2 (current installation missing DOCX extras)")
        
        if missing_deps:
            logger.warning(
                f"Missing dependencies for DOCX processing: {', '.join(missing_deps)}. "
                f"DOCX file processing may fail. Install with: pip install {' '.join(missing_deps)}"
            )

    async def remove_personal_info(self, text: str) -> str: 
        """Removes phone numbers and email addresses from the text."""
        #re to match phone and email
        PHONE_REGEX = re.compile(r"\+?32[\s()-]*\d(?:[\s()-]*\d){7,9}")             #regex for Belgian phone numbers expandable to other countries if needed
        EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}") #regex for email addresses

        text = PHONE_REGEX.sub("PHONE", text)
        text = EMAIL_REGEX.sub("EMAIL", text)
        #find names
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        FNAMEFILE = os.path.join(BASE_DIR, "common-names.txt")
        LNAMEFILE = os.path.join(BASE_DIR, "last-names.txt")
        with open(FNAMEFILE) as f:                                                  #load first names from file
            fnames = [line.strip().lower() for line in f if line.strip()]
        with open(LNAMEFILE) as f:                                                  #load last names from file
            lnames = [line.strip().lower() for line in f if line.strip()]
        fname_pattern = r"\b(" + "|".join(re.escape(n.capitalize()) for n in fnames) + r")\b" #create regex pattern for first names
        lname_pattern = r"\b(" + "|".join(re.escape(n.capitalize()) for n in lnames) + r")\b" #create regex pattern for last names

        # Ensure case-sensitive matching
        text = re.sub(fname_pattern, "FNAME", text) #remove first names
        text = re.sub(lname_pattern, "LNAME", text) #remove last names

        # remove city
        CITYFILE = os.path.join(BASE_DIR, "cities.txt")
        with open(CITYFILE) as f:                           #load city names from file
            cities = [line.strip().lower() for line in f if line.strip()]
        city_pattern = r"\b(" + "|".join(re.escape(n.capitalize()) for n in cities) + r")\b" #create regex pattern for city names
        text = re.sub(city_pattern, "CITY", text) #remove city names

        #remove street names
        STREETFILE = os.path.join(BASE_DIR, "streets.txt")
        with open(STREETFILE) as f:
            streets = [line.strip().lower() for line in f if line.strip()]
        street_pattern = r"\b(" + "|".join(re.escape(n.capitalize()) for n in streets) + r")\b"
        text = re.sub(street_pattern, "STREET", text)

        return text

    async def convert_and_store_resume(
        self, file_bytes: bytes, file_type: str, filename: str, content_type: str = "md", test_mode: bool = False
    ):
        """
        Converts resume file (PDF/DOCX) to text using MarkItDown and stores it in the database.
        if test_mode is True, returns the converted text instead of storing in DB.

        Args:
            file_bytes: Raw bytes of the uploaded file
            file_type: MIME type of the file ("application/pdf" or "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            filename: Original filename
            content_type: Output format ("md" for markdown or "html")

        Returns:
            None
        """


        with tempfile.NamedTemporaryFile(
            delete=False, suffix=self._get_file_extension(file_type)
        ) as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        try:
            try:
                result = self.md.convert(temp_path)
                text_content = result.text_content
            except Exception as e:
                # Handle specific markitdown conversion errors
                error_msg = str(e)
                if "MissingDependencyException" in error_msg or "DocxConverter" in error_msg:
                    raise Exception(
                        "File conversion failed: markitdown is missing DOCX support. "
                        "Please install with: pip install 'markitdown[all]==0.1.2' or contact system administrator."
                    ) from e
                elif "docx" in error_msg.lower():
                    raise Exception(
                        f"DOCX file processing failed: {error_msg}. "
                        "Please ensure the file is a valid DOCX document."
                    ) from e
                else:
                    raise Exception(f"File conversion failed: {error_msg}") from e

            text_content = await self.remove_personal_info(text_content) #anonymize personal data
            
            if test_mode:
                return text_content, content_type
            
            resume_id = await self._store_resume_in_db(text_content, content_type)

            await self._extract_and_store_structured_resume(
                resume_id=resume_id, resume_text=text_content
            )

            return resume_id
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _get_file_extension(self, file_type: str) -> str:
        """Returns the appropriate file extension based on MIME type"""
        if file_type == "application/pdf":
            return ".pdf"
        elif (
            file_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return ".docx"
        return ""

    async def _store_resume_in_db(self, text_content: str, content_type: str):
        """
        Stores the parsed resume content in the database.
        """
        resume_id = str(uuid.uuid4())
        resume = Resume(
            resume_id=resume_id, content=text_content, content_type=content_type
        )
        self.db.add(resume)
        await self.db.flush()
        await self.db.commit()
        return resume_id

    async def _extract_and_store_structured_resume(
        self, resume_id, resume_text: str, test_mode: bool = False
    ) -> Union[None, dict]:
        """
        extract and store structured resume data in the database
        if test_mode is True, returns the structured data instead of storing in DB.
        """
        try:
            structured_resume = await self._extract_structured_json(resume_text, test_mode)
            if not structured_resume:
                logger.error("Structured resume extraction returned None.")
                raise ResumeValidationError(
                    resume_id=resume_id,
                    message="Failed to extract structured data from resume. Please ensure your resume contains all required sections.",
                )
            
            if test_mode:
                return structured_resume
            
            processed_resume = ProcessedResume(
                resume_id=resume_id,
                personal_data=json.dumps(structured_resume.get("personal_data", {}))
                if structured_resume.get("personal_data")
                else None,
                experiences=json.dumps(
                    {"experiences": structured_resume.get("experiences", [])}
                )
                if structured_resume.get("experiences")
                else None,
                projects=json.dumps({"projects": structured_resume.get("projects", [])})
                if structured_resume.get("projects")
                else None,
                skills=json.dumps({"skills": structured_resume.get("skills", [])})
                if structured_resume.get("skills")
                else None,
                research_work=json.dumps(
                    {"research_work": structured_resume.get("research_work", [])}
                )
                if structured_resume.get("research_work")
                else None,
                achievements=json.dumps(
                    {"achievements": structured_resume.get("achievements", [])}
                )
                if structured_resume.get("achievements")
                else None,
                education=json.dumps(
                    {"education": structured_resume.get("education", [])}
                )
                if structured_resume.get("education")
                else None,
                extracted_keywords=json.dumps(
                    {
                        "extracted_keywords": structured_resume.get(
                            "extracted_keywords", []
                        )
                    }
                    if structured_resume.get("extracted_keywords")
                    else None
                ),
            )

            self.db.add(processed_resume)
            await self.db.commit()
        except ResumeValidationError:
            # Re-raise validation errors to propagate to the upload endpoint
            raise
        except Exception as e:
            logger.error(f"Error storing structured resume: {str(e)}")
            raise ResumeValidationError(
                resume_id=resume_id,
                message=f"Failed to store structured resume data: {str(e)}",
            )

    async def _extract_structured_json(
        self, resume_text: str, test_mode: bool = False
    ) -> StructuredResumeModel | None:
        """
        Uses the AgentManager+JSONWrapper to ask the LLM to
        return the data in exact JSON schema we need.
        """
        prompt_template = prompt_factory.get("structured_resume")
        prompt = prompt_template.format(
            json.dumps(json_schema_factory.get("structured_resume"), indent=2),
            resume_text,
        )
        logger.info(f"Structured Resume Prompt: {prompt}")
        
        if test_mode:
            print(prompt) #to vieuw information (log not working in unittest)
        
        raw_output = await self.json_agent_manager.run(prompt=prompt)

        try:
            structured_resume: StructuredResumeModel = (
                StructuredResumeModel.model_validate(raw_output)
            )
        except ValidationError as e:
            logger.info(f"Validation error: {e}")
            error_details = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                error_details.append(f"{field}: {error['msg']}")

            user_friendly_message = "Resume validation failed. " + "; ".join(
                error_details
            )
            raise ResumeValidationError(
                validation_error=user_friendly_message,
                message=f"Resume structure validation failed: {user_friendly_message}",
            )
        return structured_resume.model_dump()

    async def get_resume_with_processed_data(self, resume_id: str) -> Optional[Dict]:
        """
        Fetches both resume and processed resume data from the database and combines them.

        Args:
            resume_id: The ID of the resume to retrieve

        Returns:
            Combined data from both resume and processed_resume models

        Raises:
            ResumeNotFoundError: If the resume is not found
        """
        resume_query = select(Resume).where(Resume.resume_id == resume_id)
        resume_result = await self.db.execute(resume_query)
        resume = resume_result.scalars().first()

        if not resume:
            raise ResumeNotFoundError(resume_id=resume_id)

        processed_query = select(ProcessedResume).where(
            ProcessedResume.resume_id == resume_id
        )
        processed_result = await self.db.execute(processed_query)
        processed_resume = processed_result.scalars().first()

        combined_data = {
            "resume_id": resume.resume_id,
            "raw_resume": {
                "id": resume.id,
                "content": resume.content,
                "content_type": resume.content_type,
                "created_at": resume.created_at.isoformat()
                if resume.created_at
                else None,
            },
            "processed_resume": None,
        }

        if processed_resume:
            combined_data["processed_resume"] = {
                "personal_data": json.loads(processed_resume.personal_data)
                if processed_resume.personal_data
                else None,
                "experiences": json.loads(processed_resume.experiences).get(
                    "experiences", []
                )
                if processed_resume.experiences
                else None,
                "projects": json.loads(processed_resume.projects).get("projects", [])
                if processed_resume.projects
                else [],
                "skills": json.loads(processed_resume.skills).get("skills", [])
                if processed_resume.skills
                else [],
                "research_work": json.loads(processed_resume.research_work).get(
                    "research_work", []
                )
                if processed_resume.research_work
                else [],
                "achievements": json.loads(processed_resume.achievements).get(
                    "achievements", []
                )
                if processed_resume.achievements
                else [],
                "education": json.loads(processed_resume.education).get("education", [])
                if processed_resume.education
                else [],
                "extracted_keywords": json.loads(
                    processed_resume.extracted_keywords
                ).get("extracted_keywords", [])
                if processed_resume.extracted_keywords
                else [],
                "processed_at": processed_resume.processed_at.isoformat()
                if processed_resume.processed_at
                else None,
            }

        return combined_data

    async def delete_old_resumes(self, days_old: int) -> None:
        """
        Deletes resumes and all their processed data older than `days_old` days.
        Uses timezone-aware comparisons, chained eager loading, and explicit deletion
        ordering to resolve ORM cascade AssertionErrors caused by model constraints.
        """
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        stmt = select(Resume).options(
            selectinload(Resume.raw_resume_association)
                .selectinload(ProcessedResume.processed_jobs),

            selectinload(Resume.jobs)
                .selectinload(Job.raw_job_association)
        )
        
        result = await self.db.execute(stmt)
        all_resumes = result.scalars().all()
        
        old_resumes = []
        for r in all_resumes:
            created = r.created_at
            if not created:
                continue
            
            # Normalize naive datetimes to UTC (assume naive timestamps are UTC)
            if created.tzinfo is None:
                created_utc = created.replace(tzinfo=timezone.utc)
            else:
                created_utc = created.astimezone(timezone.utc)
                
            if created_utc < threshold_date:
                old_resumes.append(r)
 
        for resume in old_resumes:
             for job in list(resume.jobs):
                 
                 # Step 1: Delete the ProcessedJob (the child with the conflicting PK/FK)
                 processed_job = job.raw_job_association
                 if processed_job:
                     await self.db.delete(processed_job)
                     
                 # Step 2: Delete the Job (the immediate parent)
                 await self.db.delete(job)
             
             # Step 3: Delete ProcessedResume (which cleans up M2M link)
             processed_resume = resume.raw_resume_association
             
             if processed_resume:
                 await self.db.delete(processed_resume)
 
             # Step 4: Delete the Resume itself.
             await self.db.delete(resume)
 
        await self.db.commit()
        logger.info(f"Deleted resumes older than {days_old} days.")
