import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
from typing import List
import os
import time

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, smtp_server: str = None, smtp_port: int = None, username: str = None, password: str = None, use_tls: bool = True):
        # Load from environment if not provided
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", 587))
        self.username = username or os.getenv("SMTP_USERNAME")
        self.password = password or os.getenv("SMTP_PASSWORD")
        self.sender_email = self.username
        self.hr_email = os.getenv("HR_EMAIL")
        self.use_tls = use_tls

        # Validate configuration
        if not all([self.sender_email, self.password, self.hr_email]):
            logger.warning("Email service configuration incomplete - some emails may not be sent")
            self.configured = False
        else:
            self.configured = True
            logger.info("Email service configured successfully")

    def send_email(self, subject: str, body: str, from_addr: str, to_addrs: List[str], html: bool = False) -> bool:
        """Send an email with optional HTML content and retry logic."""
        msg = MIMEMultipart()
        msg['From'] = from_addr
        msg['To'] = ', '.join(to_addrs)
        msg['Subject'] = subject

        if html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    if self.use_tls:
                        server.starttls()
                    server.login(self.username, self.password)
                    server.sendmail(from_addr, to_addrs, msg.as_string())

                logger.info(f"Email sent to {to_addrs} with subject '{subject}'")
                return True
            except Exception as e:
                logger.warning(f"Email send attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to send email after {max_retries} attempts: {e}")
                    return False

    def send_interview_report(self, candidate_email: str, report_content: str) -> bool:
        """Send interview report to both candidate and HR with retry logic"""
        if not self.configured:
            logger.warning("Email service not configured - report not sent")
            return False

        # Create messages
        candidate_msg = MIMEMultipart()
        candidate_msg['From'] = self.sender_email
        candidate_msg['To'] = candidate_email
        candidate_msg['Subject'] = "Your Interview Report"

        candidate_body = f"""
        <html>
        <body>
            <h2>Interview Report</h2>
            <p>Dear Candidate,</p>
            <p>Thank you for participating in the interview. Please find your interview report below:</p>
            {report_content}
            <p>Best regards,<br>Interview Team</p>
        </body>
        </html>
        """
        candidate_msg.attach(MIMEText(candidate_body, 'html'))

        hr_msg = MIMEMultipart()
        hr_msg['From'] = self.sender_email
        hr_msg['To'] = self.hr_email
        hr_msg['Subject'] = f"Interview Report - {candidate_email}"

        hr_body = f"""
        <html>
        <body>
            <h2>Interview Report for Review</h2>
            <p>Dear HR Team,</p>
            <p>Please find the interview report for candidate {candidate_email}:</p>
            {report_content}
            <p>Please review and take appropriate action.</p>
            <p>Best regards,<br>Interview System</p>
        </body>
        </html>
        """
        hr_msg.attach(MIMEText(hr_body, 'html'))

        max_retries = 3
        for attempt in range(max_retries):
            server = None
            try:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                server.login(self.sender_email, self.password)

                # Send to candidate
                candidate_text = candidate_msg.as_string()
                server.sendmail(self.sender_email, candidate_email, candidate_text)
                logger.info(f"✅ Interview report sent to candidate: {candidate_email}")

                # Send to HR
                hr_text = hr_msg.as_string()
                server.sendmail(self.sender_email, self.hr_email, hr_text)
                logger.info(f"✅ Interview report sent to HR: {self.hr_email}")

                return True

            except Exception as e:
                logger.warning(f"Interview report send attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"❌ Failed to send interview report after {max_retries} attempts: {e}")
                    return False
            finally:
                if server:
                    try:
                        server.quit()
                    except Exception as e:
                        logger.warning(f"Error closing SMTP server: {e}")

    def send_interview_report_with_pdf(self, candidate_email: str, pdf_data: bytes, session_id: str) -> bool:
        """Send interview report as PDF attachment to both candidate and HR"""
        if not self.configured:
            logger.warning("Email service not configured - report not sent")
            return False

        # Create candidate message
        candidate_msg = MIMEMultipart()
        candidate_msg['From'] = self.sender_email
        candidate_msg['To'] = candidate_email
        candidate_msg['Subject'] = "Your Interview Assessment Report"

        candidate_body = """
        <html>
        <body>
            <h2>Interview Assessment Report</h2>
            <p>Dear Candidate,</p>
            <p>Thank you for participating in the interview. Please find your interview assessment report attached as a PDF document.</p>
            <p>The report includes:</p>
            <ul>
                <li>Your interview responses and analysis</li>
                <li>Assessment of your qualifications and fit</li>
                <li>Feedback and recommendations</li>
            </ul>
            <p>If you have any questions about the report, please don't hesitate to contact us.</p>
            <p>Best regards,<br>Interview Team</p>
        </body>
        </html>
        """
        candidate_msg.attach(MIMEText(candidate_body, 'html'))

        # Attach PDF to candidate email
        candidate_pdf_attachment = MIMEBase('application', 'octet-stream')
        candidate_pdf_attachment.set_payload(pdf_data)
        encoders.encode_base64(candidate_pdf_attachment)
        candidate_pdf_attachment.add_header('Content-Disposition', 'attachment', filename=f'interview_report_{session_id}.pdf')
        candidate_msg.attach(candidate_pdf_attachment)

        # Create HR message
        hr_msg = MIMEMultipart()
        hr_msg['From'] = self.sender_email
        hr_msg['To'] = self.hr_email
        hr_msg['Subject'] = f"Interview Assessment Report - {candidate_email}"

        hr_body = f"""
        <html>
        <body>
            <h2>Interview Assessment Report for Review</h2>
            <p>Dear HR Team,</p>
            <p>Please find the interview assessment report for candidate {candidate_email} attached as a PDF document.</p>
            <p>Session ID: {session_id}</p>
            <p>Please review the candidate's performance and qualifications, and take appropriate action regarding their application.</p>
            <p>Best regards,<br>Interview System</p>
        </body>
        </html>
        """
        hr_msg.attach(MIMEText(hr_body, 'html'))

        # Attach PDF to HR email
        hr_pdf_attachment = MIMEBase('application', 'octet-stream')
        hr_pdf_attachment.set_payload(pdf_data)
        encoders.encode_base64(hr_pdf_attachment)
        hr_pdf_attachment.add_header('Content-Disposition', 'attachment', filename=f'interview_report_{session_id}.pdf')
        hr_msg.attach(hr_pdf_attachment)

        max_retries = 3
        for attempt in range(max_retries):
            server = None
            try:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                server.login(self.sender_email, self.password)

                # Send to candidate
                candidate_text = candidate_msg.as_string()
                server.sendmail(self.sender_email, candidate_email, candidate_text)
                logger.info(f"✅ Interview report PDF sent to candidate: {candidate_email}")

                # Send to HR
                hr_text = hr_msg.as_string()
                server.sendmail(self.sender_email, self.hr_email, hr_text)
                logger.info(f"✅ Interview report PDF sent to HR: {self.hr_email}")

                return True

            except Exception as e:
                logger.warning(f"Interview report PDF send attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"❌ Failed to send interview report PDF after {max_retries} attempts: {e}")
                    return False
            finally:
                if server:
                    try:
                        server.quit()
                    except Exception as e:
                        logger.warning(f"Error closing SMTP server: {e}")
