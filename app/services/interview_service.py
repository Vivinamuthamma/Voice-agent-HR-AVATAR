import asyncio
import logging
import os
import json
import re
from typing import List, Dict, Any
from livekit.plugins import openai
from livekit.agents import ChatContext
from pathlib import Path
from app.core.http_client import get_http_client

logger = logging.getLogger(__name__)

class InterviewService:
    """Service for interview-related operations like analysis and question generation."""

    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.llm = None
        if not self.openai_key:
            logger.warning("OpenAI API key not found - using fallback methods")
        else:
            try:
                self.llm = openai.LLM(model="gpt-4o-mini", api_key=self.openai_key)
                logger.info("LiveKit OpenAI LLM plugin initialized successfully")
            except Exception as e:
                logger.error(f"LLM plugin initialization failed: {e}")
                self.llm = None

    async def analyze_documents(self, jd_text: str, resume_text: str) -> Dict[str, Any]:
        """Analyze documents with AI"""
        try:
            # Basic analysis if OpenAI not available
            if not self.llm:
                return self._basic_analysis(jd_text, resume_text)

            prompt = f"""
Analyze the following job description and resume to determine how well the candidate matches the position.

Job Description:
{jd_text[:2000]}

Resume:
{resume_text[:2000]}

Please provide:
1. A match score from 1-10 (10 being perfect match)
2. Key skills that match between JD and resume
3. Any gaps or areas of concern
4. Overall assessment

Format as JSON with keys: match_score, key_skills (array), gaps (array), assessment (string)
"""

            # Use LiveKit LLM plugin
            chat_ctx = ChatContext()
            chat_ctx.add_message(role="user", content=prompt)

            analysis_text = ""
            async with self.llm.chat(chat_ctx=chat_ctx) as stream:
                async for chunk in stream:
                    if chunk.delta and hasattr(chunk.delta, 'content'):
                        analysis_text += chunk.delta.content or ""
            return self._parse_analysis_response(analysis_text)

        except Exception as e:
            logger.error(f"Document analysis error: {e}")
            return self._basic_analysis(jd_text, resume_text)

    def _basic_analysis(self, jd_text: str, resume_text: str) -> Dict[str, Any]:
        """Basic fallback analysis"""
        return {
            "match_score": 7,
            "key_skills": ["Communication", "Problem Solving"],
            "gaps": ["Specific technical skills may need verification"],
            "assessment": "Basic analysis completed - detailed AI analysis not available"
        }

    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse OpenAI analysis response"""

        # Strip markdown code blocks if present
        if "```json" in response_text:
            # Extract content between ```json and ```
            match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if match:
                response_text = match.group(1).strip()

        try:
            # Try to parse as JSON
            parsed = json.loads(response_text)
            # Ensure required keys are present
            result = {
                "match_score": parsed.get("match_score", 7),
                "key_skills": parsed.get("key_skills", []),
                "gaps": parsed.get("gaps", []),
                "assessment": parsed.get("assessment", response_text)
            }
            return result
        except json.JSONDecodeError:
            # If not JSON, treat as plain text assessment
            logger.warning("LLM response is not valid JSON, using fallback parsing")
            return {
                "match_score": 7,
                "key_skills": ["Communication", "Problem Solving"],
                "gaps": ["Unable to parse detailed analysis"],
                "assessment": response_text
            }
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return self._basic_analysis("", "")

    async def generate_interview_questions(self, jd_text: str, resume_text: str, num_questions: int) -> List[Dict[str, Any]]:
        """Generate interview questions using LLM based on resume and job description"""
        try:
            if not self.llm:
                logger.warning("LLM not available, using fallback questions")
                return self._generate_fallback_questions(num_questions)

            # Create prompt for LLM
            system_prompt = """You are an expert technical interviewer with years of experience conducting interviews for software development and technical roles. Your task is to generate highly relevant, specific interview questions based on the candidate's resume and the job description provided."""
            user_prompt = f"""
Analyze the following job description and candidate resume carefully, then generate {num_questions} targeted interview questions.

JOB DESCRIPTION:
{jd_text[:4000]}

CANDIDATE RESUME:
{resume_text[:4000]}

INSTRUCTIONS:
Generate {num_questions} thoughtful, specific interview questions that directly relate to:
1. Skills and technologies mentioned in both the job description and resume
2. Experience levels required by the JD and demonstrated in the resume
3. Specific projects or achievements from the resume that align with JD requirements
4. Gaps between JD requirements and resume experience (if any)
5. Problem-solving approaches relevant to the role
6. Technical concepts and methodologies from the JD that the candidate should know

REQUIREMENTS:
- Questions must reference specific skills, tools, or experiences from the resume/JD
- Make questions conversational and natural for a professional interview
- Include follow-up potential in questions
- Avoid generic questions; be specific to this candidate and role
- Balance technical and behavioral questions
- Ensure questions assess real job requirements, not just resume keywords
- ALL QUESTIONS MUST BE IN ENGLISH ONLY

FORMAT: Return ONLY a numbered list:
1. Question one?
2. Question two?
3. Continue exactly like this...

No introductions, explanations, or extra text.
"""

            # Generate questions using LiveKit LLM plugin
            logger.info(f"Calling LLM API for {num_questions} questions")
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            chat_ctx = ChatContext()
            chat_ctx.add_message(role="user", content=full_prompt)

            questions_text = ""
            try:
                async with self.llm.chat(chat_ctx=chat_ctx) as stream:
                    async for chunk in stream:
                        if chunk.delta and hasattr(chunk.delta, 'content'):
                            questions_text += chunk.delta.content or ""
                logger.info(f"LLM response received, length: {len(questions_text)} characters")
            except (RuntimeError, asyncio.CancelledError, Exception) as e:
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ["event loop is closed", "cancelled", "connection", "timeout"]):
                    logger.warning(f"LLM request interrupted ({type(e).__name__}: {e}), will retry question generation")
                    # Wait a moment and retry once
                    await asyncio.sleep(1.0)
                    try:
                        # Retry the LLM call with the same prompt
                        chat_ctx = ChatContext()
                        chat_ctx.add_message(role="user", content=full_prompt)

                        questions_text = ""
                        async with self.llm.chat(chat_ctx=chat_ctx) as stream:
                            async for chunk in stream:
                                if chunk.delta and hasattr(chunk.delta, 'content'):
                                    questions_text += chunk.delta.content or ""

                        # Parse questions from retry response
                        questions = []
                        lines = questions_text.split('\n')

                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue

                            question = None
                            if line[0].isdigit() and len(line) > 2:
                                parts = line.split('.', 1)
                                if len(parts) > 1:
                                    question = parts[1].strip()
                                else:
                                    question = line

                            if question:
                                question = question.strip(' -"')
                                question = question.lstrip('0123456789.-•* ')
                                question = question.strip()

                                if (question and len(question) > 10 and
                                    '?' in question and
                                    not question.lower().startswith(('here', 'below', 'above', 'note'))):
                                    questions.append(question)

                        if questions:
                            # Format questions with proper structure
                            return [{"id": i+1, "question": question} for i, question in enumerate(questions[:num_questions])]

                        raise Exception("Retry parsing failed to extract valid questions")

                    except Exception as retry_e:
                        logger.error(f"Retry also failed: {retry_e}, cannot generate questions without LLM")
                        raise RuntimeError("Cannot generate interview questions due to persistent LLM connection issues. Please check your OpenAI API key and network connection.")
                else:
                    logger.error(f"Unexpected error during LLM call: {e}")
                    raise  # Re-raise unexpected errors

            # Extract questions from the response with improved parsing
            questions = []
            lines = questions_text.split('\n')

            for line in lines:
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Handle various numbering formats
                question = None

                # Check for numbered lists (1., 2., etc.)
                if line[0].isdigit() and len(line) > 2:
                    parts = line.split('.', 1)
                    if len(parts) > 1:
                        question = parts[1].strip()
                    else:
                        question = line

                # Check for bullet points
                elif line.startswith(('- ', '• ', '* ')):
                    question = line[2:].strip() if len(line) > 2 else line[1:].strip()

                # Check for other common formats
                elif line.startswith(('Q:', 'Question:')):
                    question = line.split(':', 1)[1].strip() if ':' in line else line

                # If no specific format detected, treat as question if it's long enough
                elif len(line) > 15 and '?' in line:
                    question = line

                # Clean up the question
                if question:
                    question = question.strip(' -"')
                    # Remove any remaining numbering or bullets
                    question = question.lstrip('0123456789.-•* ')
                    question = question.strip()

                    # Filter out very short questions and non-questions
                    if (question and len(question) > 10 and
                        '?' in question and
                        not question.lower().startswith(('here', 'below', 'above', 'note'))):
                        questions.append(question)

            # Log parsing results
            logger.info(f"Successfully parsed {len(questions)} questions from LLM response")

            # Ensure we have the requested number of questions - if not enough, raise error
            if len(questions) < num_questions:
                logger.error(f"LLM generated only {len(questions)} questions, but {num_questions} were requested. Cannot proceed without sufficient AI-generated questions.")
                raise RuntimeError(f"LLM could not generate enough questions ({len(questions)}/{num_questions}). Please check your OpenAI API key and try again.")

            # Format questions with proper structure
            return [{"id": i+1, "question": question} for i, question in enumerate(questions[:num_questions])]

        except Exception as e:
            logger.error(f"Error generating questions with LLM: {e}")
            return self._generate_fallback_questions(num_questions)

    def _generate_fallback_questions(self, num_questions: int) -> List[Dict[str, Any]]:
        """Generate generic fallback questions when LLM is not available"""
        fallback_questions = [
            "Can you walk me through your professional background and key experiences?",
            "What motivated you to apply for this position?",
            "Can you describe a challenging project you've worked on and how you handled it?",
            "How do you approach problem-solving in your work?",
            "What are your greatest professional strengths?",
            "Can you tell me about a time when you had to learn something new quickly?",
            "How do you handle working under pressure or meeting tight deadlines?",
            "Describe your experience working in a team environment.",
            "What tools and technologies are you most proficient with?",
            "How do you stay current with industry trends and best practices?",
            "Can you discuss a situation where you received constructive feedback and how you responded?",
            "What are your career goals and how does this position align with them?",
            "How do you prioritize tasks when working on multiple projects?",
            "Can you describe your experience with project management or coordination?",
            "What do you consider to be your most significant professional achievement?",
            "How do you handle conflicts or disagreements in a professional setting?",
            "What experience do you have with quality assurance or testing processes?",
            "How do you approach documentation and knowledge sharing?",
            "Can you discuss your experience with stakeholder communication?",
            "What strategies do you use for continuous professional development?"
        ]

        selected_questions = fallback_questions[:num_questions]
        return [{"id": i+1, "question": question} for i, question in enumerate(selected_questions)]
