import streamlit as st
import pandas as pd
import sqlite3
import requests
import json
import time
import uuid
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import hashlib
import os
from typing import Dict, List, Optional
import asyncio
import aiohttp
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="HR Recruiting Automation Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database Configuration
DATABASE_PATH = "hr_recruiting.db"

# API Configuration
API_CONFIG = {
    "linkedin": {
        "base_url": "https://api.linkedin.com/v2",
        "client_id": os.getenv("LINKEDIN_CLIENT_ID", "your_linkedin_client_id"),
        "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET", "your_linkedin_secret")
    },
    "indeed": {
        "base_url": "https://api.indeed.com/ads/apisearch",
        "publisher_id": os.getenv("INDEED_PUBLISHER_ID", "your_indeed_publisher_id")
    },
    "sendgrid": {
        "api_key": os.getenv("SENDGRID_API_KEY", "your_sendgrid_api_key"),
        "base_url": "https://api.sendgrid.com/v3/mail/send"
    },
    "google_calendar": {
        "api_key": os.getenv("GOOGLE_CALENDAR_API_KEY", "your_google_calendar_key"),
        "base_url": "https://www.googleapis.com/calendar/v3"
    },
    "openai": {
        "api_key": os.getenv("OPENAI_API_KEY", "your_openai_api_key"),
        "base_url": "https://api.openai.com/v1"
    }
}

# Database Models
@dataclass
class Candidate:
    id: str
    name: str
    email: str
    phone: str
    position: str
    skills: List[str]
    experience: int
    score: float
    status: str
    location: str
    resume_url: str
    applied_date: datetime
    source: str
    notes: str

@dataclass
class Job:
    id: str
    title: str
    department: str
    description: str
    requirements: List[str]
    location: str
    salary_range: str
    status: str
    posted_date: datetime
    applications_count: int
    hiring_manager: str

@dataclass
class Interview:
    id: str
    candidate_id: str
    job_id: str
    interviewer: str
    scheduled_time: datetime
    status: str
    feedback: str
    score: int

# Database Manager
class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Candidates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                position TEXT,
                skills TEXT,
                experience INTEGER,
                score REAL,
                status TEXT,
                location TEXT,
                resume_url TEXT,
                applied_date TIMESTAMP,
                source TEXT,
                notes TEXT
            )
        ''')
        
        # Jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                department TEXT,
                description TEXT,
                requirements TEXT,
                location TEXT,
                salary_range TEXT,
                status TEXT,
                posted_date TIMESTAMP,
                applications_count INTEGER DEFAULT 0,
                hiring_manager TEXT
            )
        ''')
        
        # Interviews table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interviews (
                id TEXT PRIMARY KEY,
                candidate_id TEXT,
                job_id TEXT,
                interviewer TEXT,
                scheduled_time TIMESTAMP,
                status TEXT,
                feedback TEXT,
                score INTEGER,
                FOREIGN KEY (candidate_id) REFERENCES candidates (id),
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        ''')
        
        # Agent logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT
            )
        ''')
        
        # System settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query: str, params: tuple = None):
        """Execute a database query"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return pd.DataFrame(result, columns=columns)
            else:
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Database error: {e}")
            return None
        finally:
            conn.close()
    
    def add_candidate(self, candidate: Candidate):
        """Add a new candidate to the database"""
        query = '''
            INSERT INTO candidates (id, name, email, phone, position, skills, experience, 
                                  score, status, location, resume_url, applied_date, source, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            candidate.id, candidate.name, candidate.email, candidate.phone,
            candidate.position, json.dumps(candidate.skills), candidate.experience,
            candidate.score, candidate.status, candidate.location, candidate.resume_url,
            candidate.applied_date, candidate.source, candidate.notes
        )
        return self.execute_query(query, params)
    
    def get_candidates(self, filters: Dict = None):
        """Get candidates with optional filters"""
        query = "SELECT * FROM candidates"
        params = []
        
        if filters:
            conditions = []
            if filters.get('status'):
                conditions.append("status = ?")
                params.append(filters['status'])
            if filters.get('position'):
                conditions.append("position = ?")
                params.append(filters['position'])
            if filters.get('min_score'):
                conditions.append("score >= ?")
                params.append(filters['min_score'])
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY applied_date DESC"
        return self.execute_query(query, tuple(params))
    
    def update_candidate_status(self, candidate_id: str, status: str):
        """Update candidate status"""
        query = "UPDATE candidates SET status = ? WHERE id = ?"
        return self.execute_query(query, (status, candidate_id))
    
    def add_job(self, job: Job):
        """Add a new job posting"""
        query = '''
            INSERT INTO jobs (id, title, department, description, requirements, 
                            location, salary_range, status, posted_date, hiring_manager)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            job.id, job.title, job.department, job.description,
            json.dumps(job.requirements), job.location, job.salary_range,
            job.status, job.posted_date, job.hiring_manager
        )
        return self.execute_query(query, params)
    
    def get_jobs(self):
        """Get all job postings"""
        return self.execute_query("SELECT * FROM jobs ORDER BY posted_date DESC")
    
    def log_agent_activity(self, agent_name: str, action: str, details: str, status: str = "success"):
        """Log agent activity"""
        query = '''
            INSERT INTO agent_logs (agent_name, action, details, status)
            VALUES (?, ?, ?, ?)
        '''
        return self.execute_query(query, (agent_name, action, details, status))
    
    def get_agent_logs(self, limit: int = 50):
        """Get recent agent logs"""
        query = "SELECT * FROM agent_logs ORDER BY timestamp DESC LIMIT ?"
        return self.execute_query(query, (limit,))

# API Integration Classes
class LinkedInAPI:
    def __init__(self, config: Dict):
        self.config = config
        self.access_token = None
    
    async def search_candidates(self, keywords: str, location: str = None):
        """Search for candidates on LinkedIn"""
        # Simulated API call - replace with actual LinkedIn API
        await asyncio.sleep(1)  # Simulate API delay
        
        # Mock response
        candidates = [
            {
                "name": f"LinkedIn Candidate {i}",
                "title": "Software Engineer",
                "location": location or "San Francisco",
                "skills": ["Python", "JavaScript", "React"],
                "profile_url": f"https://linkedin.com/in/candidate{i}"
            }
            for i in range(1, 4)
        ]
        
        return candidates
    
    async def post_job(self, job_data: Dict):
        """Post a job to LinkedIn"""
        await asyncio.sleep(1)  # Simulate API delay
        return {"status": "success", "job_id": f"linkedin_{uuid.uuid4().hex[:8]}"}

class IndeedAPI:
    def __init__(self, config: Dict):
        self.config = config
    
    async def search_jobs(self, query: str, location: str = None):
        """Search jobs on Indeed"""
        await asyncio.sleep(1)  # Simulate API delay
        
        # Mock response
        jobs = [
            {
                "title": f"Indeed Job {i}",
                "company": f"Company {i}",
                "location": location or "Remote",
                "description": f"Job description for position {i}",
                "url": f"https://indeed.com/job{i}"
            }
            for i in range(1, 6)
        ]
        
        return jobs
    
    async def post_job(self, job_data: Dict):
        """Post a job to Indeed"""
        await asyncio.sleep(1)  # Simulate API delay
        return {"status": "success", "job_id": f"indeed_{uuid.uuid4().hex[:8]}"}

class EmailService:
    def __init__(self, config: Dict):
        self.config = config
    
    async def send_email(self, to_email: str, subject: str, body: str):
        """Send email using SendGrid API"""
        try:
            # Simulate email sending
            await asyncio.sleep(0.5)
            
            # In production, use actual SendGrid API
            logger.info(f"Email sent to {to_email}: {subject}")
            return {"status": "success", "message_id": f"msg_{uuid.uuid4().hex[:8]}"}
        
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def send_bulk_emails(self, recipients: List[Dict]):
        """Send bulk emails"""
        results = []
        for recipient in recipients:
            result = await self.send_email(
                recipient['email'],
                recipient['subject'],
                recipient['body']
            )
            results.append(result)
        return results

class AIAgent:
    def __init__(self, name: str, config: Dict, db_manager: DatabaseManager):
        self.name = name
        self.config = config
        self.db_manager = db_manager
        self.status = "idle"
    
    async def screen_candidate(self, candidate_data: Dict):
        """AI-powered candidate screening"""
        try:
            self.status = "active"
            
            # Simulate AI screening process
            await asyncio.sleep(2)
            
            # Calculate score based on skills, experience, etc.
            score = self.calculate_candidate_score(candidate_data)
            
            # Log activity
            self.db_manager.log_agent_activity(
                self.name,
                "candidate_screening",
                f"Screened candidate {candidate_data.get('name', 'Unknown')}",
                "success"
            )
            
            self.status = "idle"
            return {"score": score, "recommendation": "interview" if score > 70 else "reject"}
        
        except Exception as e:
            logger.error(f"Screening failed: {e}")
            self.status = "error"
            return {"error": str(e)}
    
    def calculate_candidate_score(self, candidate_data: Dict):
        """Calculate candidate score based on various factors"""
        score = 0
        
        # Experience weight (40%)
        experience = candidate_data.get('experience', 0)
        experience_score = min(experience * 10, 40)  # Max 40 points
        score += experience_score
        
        # Skills match weight (40%)
        candidate_skills = set(candidate_data.get('skills', []))
        required_skills = set(['Python', 'JavaScript', 'React', 'AWS'])  # Mock requirements
        skill_match = len(candidate_skills & required_skills) / len(required_skills)
        skills_score = skill_match * 40
        score += skills_score
        
        # Location preference (10%)
        if candidate_data.get('location') in ['San Francisco', 'New York', 'Remote']:
            score += 10
        
        # Random factor (10%)
        import random
        score += random.randint(0, 10)
        
        return min(score, 100)

# Initialize database and services
@st.cache_resource
def initialize_services():
    """Initialize database and API services"""
    db_manager = DatabaseManager(DATABASE_PATH)
    
    # Initialize API services
    linkedin_api = LinkedInAPI(API_CONFIG['linkedin'])
    indeed_api = IndeedAPI(API_CONFIG['indeed'])
    email_service = EmailService(API_CONFIG['sendgrid'])
    
    # Initialize AI agents
    screening_agent = AIAgent("Screening Agent", API_CONFIG['openai'], db_manager)
    sourcing_agent = AIAgent("Sourcing Agent", API_CONFIG['openai'], db_manager)
    
    return {
        'db_manager': db_manager,
        'linkedin_api': linkedin_api,
        'indeed_api': indeed_api,
        'email_service': email_service,
        'screening_agent': screening_agent,
        'sourcing_agent': sourcing_agent
    }

# Initialize services
services = initialize_services()
db_manager = services['db_manager']

# Authentication
def authenticate_user(username: str, password: str):
    """Simple authentication"""
    # In production, use proper authentication with hashed passwords
    return username == "admin" and password == "password123"

# Session state initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None

# Login page
if not st.session_state.authenticated:
    st.title("🤖 HR Recruiting Automation Platform")
    st.subheader("Please log in to continue")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            if authenticate_user(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")
    
    st.info("Demo credentials: username=admin, password=password123")
    st.stop()

# Main application
st.title(f"🤖 HR Recruiting Automation Platform")
st.subheader(f"Welcome, {st.session_state.username}!")

# Logout button
if st.button("Logout", key="logout_main"):
    st.session_state.authenticated = False
    st.session_state.username = None
    st.rerun()

# Sidebar - System Status
st.sidebar.title("🔧 System Status")

# Agent status
st.sidebar.subheader("AI Agents")
agents_status = {
    "Sourcing Agent": "🟢 Active",
    "Screening Agent": "🟢 Active",
    "Interview Agent": "🟡 Idle",
    "Evaluation Agent": "🟢 Active"
}

for agent, status in agents_status.items():
    st.sidebar.write(f"{status} {agent}")

st.sidebar.divider()

# API Integration status
st.sidebar.subheader("API Integrations")
api_status = {
    "LinkedIn API": "🟢 Connected",
    "Indeed API": "🟢 Connected",
    "SendGrid Email": "🟢 Connected",
    "Google Calendar": "🟡 Limited",
    "OpenAI GPT": "🟢 Connected"
}

for api, status in api_status.items():
    st.sidebar.write(f"{status} {api}")

# Main tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboard", 
    "👥 Candidates", 
    "💼 Jobs", 
    "🤖 AI Agents", 
    "📧 Communications", 
    "⚙️ Settings"
])

with tab1:
    st.header("Dashboard Overview")
    
    # Fetch data from database
    candidates_df = db_manager.get_candidates()
    jobs_df = db_manager.get_jobs()
    
    if candidates_df is not None and not candidates_df.empty:
        # KPI Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_candidates = len(candidates_df)
            st.metric("Total Candidates", total_candidates, "+12")
        
        with col2:
            hired_count = len(candidates_df[candidates_df['status'] == 'Hired'])
            st.metric("Hired This Month", hired_count, "+3")
        
        with col3:
            avg_score = candidates_df['score'].mean() if 'score' in candidates_df.columns else 0
            st.metric("Avg Candidate Score", f"{avg_score:.1f}", "+2.1")
        
        with col4:
            active_jobs = len(jobs_df[jobs_df['status'] == 'Active']) if jobs_df is not None else 0
            st.metric("Active Jobs", active_jobs, "+1")
        
        st.divider()
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Candidate status distribution
            if 'status' in candidates_df.columns:
                status_counts = candidates_df['status'].value_counts()
                fig = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    title="Candidate Status Distribution"
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Score distribution
            if 'score' in candidates_df.columns:
                fig = px.histogram(
                    candidates_df,
                    x='score',
                    nbins=10,
                    title="Candidate Score Distribution"
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Recent activity
        st.subheader("Recent Agent Activity")
        agent_logs = db_manager.get_agent_logs(10)
        if agent_logs is not None and not agent_logs.empty:
            for _, log in agent_logs.iterrows():
                timestamp = log['timestamp']
                st.text(f"[{timestamp}] {log['agent_name']}: {log['action']} - {log['details']}")
        else:
            st.info("No recent activity")
    
    else:
        st.info("No data available. Start by adding some candidates and jobs.")

with tab2:
    st.header("Candidate Management")
    
    # Add new candidate
    with st.expander("➕ Add New Candidate"):
        with st.form("add_candidate"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name*")
                email = st.text_input("Email*")
                phone = st.text_input("Phone")
                position = st.selectbox("Position", [
                    "Software Engineer", "Data Scientist", "DevOps Engineer",
                    "Frontend Developer", "Backend Developer", "Full Stack Developer"
                ])
            
            with col2:
                experience = st.number_input("Years of Experience", min_value=0, max_value=50)
                location = st.text_input("Location")
                source = st.selectbox("Source", ["LinkedIn", "Indeed", "Referral", "Company Website"])
                skills = st.text_input("Skills (comma-separated)")
            
            resume_url = st.text_input("Resume URL")
            notes = st.text_area("Notes")
            
            submit = st.form_submit_button("Add Candidate")
            
            if submit and name and email:
                candidate = Candidate(
                    id=f"CAND_{uuid.uuid4().hex[:8].upper()}",
                    name=name,
                    email=email,
                    phone=phone,
                    position=position,
                    skills=skills.split(',') if skills else [],
                    experience=experience,
                    score=0.0,
                    status="New",
                    location=location,
                    resume_url=resume_url,
                    applied_date=datetime.now(),
                    source=source,
                    notes=notes
                )
                
                result = db_manager.add_candidate(candidate)
                if result:
                    st.success("Candidate added successfully!")
                    st.rerun()
                else:
                    st.error("Failed to add candidate")
    
    # Candidate filters
    st.subheader("Candidate Filters")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox("Status", ["All", "New", "Screening", "Interview", "Hired", "Rejected"])
    with col2:
        position_filter = st.selectbox("Position", ["All", "Software Engineer", "Data Scientist", "DevOps Engineer"])
    with col3:
        min_score = st.slider("Minimum Score", 0, 100, 0)
    
    # Fetch and display candidates
    filters = {}
    if status_filter != "All":
        filters['status'] = status_filter
    if position_filter != "All":
        filters['position'] = position_filter
    if min_score > 0:
        filters['min_score'] = min_score
    
    candidates_df = db_manager.get_candidates(filters)
    
    if candidates_df is not None and not candidates_df.empty:
        # Process skills column
        if 'skills' in candidates_df.columns:
            candidates_df['skills'] = candidates_df['skills'].apply(
                lambda x: ', '.join(json.loads(x)) if x and x.startswith('[') else x
            )
        
        st.dataframe(
            candidates_df[['name', 'position', 'email', 'status', 'score', 'experience', 'location']],
            use_container_width=True
        )
        
        # Bulk actions
        st.subheader("Bulk Actions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🤖 AI Screen Selected"):
                with st.spinner("AI agents screening candidates..."):
                    # Simulate AI screening
                    for _, candidate in candidates_df.iterrows():
                        if candidate['status'] == 'New':
                            # Update score and status
                            import random
                            new_score = random.randint(60, 95)
                            new_status = "Interview" if new_score > 75 else "Screening"
                            
                            db_manager.execute_query(
                                "UPDATE candidates SET score = ?, status = ? WHERE id = ?",
                                (new_score, new_status, candidate['id'])
                            )
                    
                    # Log activity
                    db_manager.log_agent_activity(
                        "Screening Agent",
                        "bulk_screening",
                        f"Screened {len(candidates_df)} candidates",
                        "success"
                    )
                
                st.success("AI screening completed!")
                st.rerun()
        
        with col2:
            if st.button("📧 Send Update Emails"):
                with st.spinner("Sending emails..."):
                    time.sleep(2)  # Simulate email sending
                    
                    # Log activity
                    db_manager.log_agent_activity(
                        "Communication Agent",
                        "bulk_email",
                        f"Sent updates to {len(candidates_df)} candidates",
                        "success"
                    )
                
                st.success("Update emails sent!")
        
        with col3:
            if st.button("📅 Schedule Interviews"):
                with st.spinner("Scheduling interviews..."):
                    time.sleep(2)  # Simulate scheduling
                    
                    # Update qualified candidates
                    qualified_candidates = candidates_df[candidates_df['score'] > 75]
                    for _, candidate in qualified_candidates.iterrows():
                        db_manager.update_candidate_status(candidate['id'], "Interview")
                    
                    # Log activity
                    db_manager.log_agent_activity(
                        "Interview Agent",
                        "bulk_scheduling",
                        f"Scheduled interviews for {len(qualified_candidates)} candidates",
                        "success"
                    )
                
                st.success("Interviews scheduled for qualified candidates!")
                st.rerun()
    
    else:
        st.info("No candidates found matching the filters.")

with tab3:
    st.header("Job Management")
    
    # Add new job
    with st.expander("➕ Post New Job"):
        with st.form("add_job"):
            col1, col2 = st.columns(2)
            
            with col1:
                job_title = st.text_input("Job Title*")
                department = st.selectbox("Department", [
                    "Engineering", "Data Science", "DevOps", "Product", "Marketing", "Sales"
                ])
                location = st.text_input("Location")
                salary_range = st.text_input("Salary Range")
            
            with col2:
                hiring_manager = st.text_input("Hiring Manager")
                status = st.selectbox("Status", ["Active", "Paused", "Closed"])
                requirements = st.text_input("Requirements (comma-separated)")
            
            description = st.text_area("Job Description")
            
            submit = st.form_submit_button("Post Job")
            
            if submit and job_title:
                job = Job(
                    id=f"JOB_{uuid.uuid4().hex[:8].upper()}",
                    title=job_title,
                    department=department,
                    description=description,
                    requirements=requirements.split(',') if requirements else [],
                    location=location,
                    salary_range=salary_range,
                    status=status,
                    posted_date=datetime.now(),
                    applications_count=0,
                    hiring_manager=hiring_manager
                )
                
                result = db_manager.add_job(job)
                if result:
                    # Log activity
                    db_manager.log_agent_activity(
                        "Sourcing Agent",
                        "job_posted",
                        f"Posted job: {job_title}",
                        "success"
                    )
                    
                    st.success("Job posted successfully! Sourcing agents activated.")
                    st.rerun()
                else:
                    st.error("Failed to post job")
    
    # Display jobs
    st.subheader("Current Job Openings")
    jobs_df = db_manager.get_jobs()
    
    if jobs_df is not None and not jobs_df.empty:
        for _, job in jobs_df.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.write(f"**{job['title']}** - {job['department']}")
                    st.write(f"Job ID: {job['id']}")
                    if job['salary_range']:
                        st.write(f"Salary: {job['salary_range']}")
                
                with col2:
                    status_color = "🟢" if job['status'] == 'Active' else "🟡" if job['status'] == 'Paused' else "🔴"
                    st.write(f"{status_color} {job['status']}")
                
                with col3:
                    st.write(f"Applications: {job['applications_count']}")
                
                with col4:
                    if st.button(f"Manage", key=f"manage_{job['id']}"):
                        st.info(f"Managing job: {job['title']}")
            
            st.divider()
    
    else:
        st.info("No job postings available.")

with tab4:
    st.header("AI Agent Management")
    
    # Agent controls
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🤖 Agent Controls")
        
        if st.button("🔄 Restart All Agents"):
            with st.spinner("Restarting agents..."):
                time.sleep(3)
                
                # Log activity
                db_manager.log_agent_activity(
                    "System",
                    "agent_restart",
                    "All agents restarted",
                    "success"
                )
            
            st.success("All agents restarted successfully!")
        
        if st.button("🔍 Run Candidate Sourcing"):
            with st.spinner("Sourcing candidates..."):
                # Simulate candidate sourcing
                time.sleep(4)
                
                # Add some mock candidates
                for i in range(3):
                    candidate = Candidate(
                        id=f"CAND_{uuid.uuid4().hex[:8].upper()}",
                        name=f"AI Sourced Candidate {i+1}",
                        email=f"sourced.candidate{i+1}@email.com",
                        phone=f"+1-555-{random.randint(1000, 9999)}",
                        position="Software Engineer",
                        skills=["Python", "JavaScript", "React", "AWS"],
                        experience=random.randint(2, 8),
                        score=random.randint(70, 90),
                        status="New",
                        location="Remote",
                        resume_url=f"https://example.com/resume{i+1}.pdf",
                        applied_date=datetime.now(),
                        source="AI Sourcing",
                        notes="Sourced by AI agent"
                    )
                    db_manager.add_candidate(candidate)
                
                # Log activity
                db_manager.log_agent_activity(
                    "Sourcing Agent",
                    "candidate_sourcing",
                    "Sourced 3 new candidates from job boards",
                    "success"
                )
            
            st.success("Found 3 new candidates!")
            st.rerun()
        
        if st.button("📊 Generate AI Insights"):
            with st.spinner("Generating insights..."):
                time.sleep(2)
                
                # Log activity
                db_manager.log_agent_activity(
                    "Analytics Agent",
                    "insight_generation",
                    "Generated recruitment insights",
                    "success"
                )
            
            st.success("AI insights generated!")
            
            # Display mock insights
            st.info("💡 **AI Insight**: Top performing candidates have 5+ years experience and Python skills")
            st.info("💡 **AI Insight**: 73% of hired candidates came from LinkedIn sourcing")
            st.info("💡 **AI Insight**: Average time-to-hire decreased by 23% with AI screening")
    
    with col2:
        st.subheader("📈 Agent Performance")
        
        # Mock performance data
        performance_data = {
            "Agent": ["Sourcing", "Screening", "Interview", "Analytics"],
            "Tasks Today": [45, 67, 23, 12],
            "Success Rate": [94, 89, 96, 91],
            "Avg Response Time": ["1.2s", "3.4s", "15.3s", "2.1s"]
        }
        
        df_performance = pd.DataFrame(performance_data)
        st.dataframe(df_performance, use_container_width=True)
        
        # Performance chart
        fig = px.bar(
            df_performance, 
            x="Agent", 
            y="Tasks Today",
            title="Agent Task Completion Today",
            color="Success Rate",
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Agent activity logs
    st.subheader("🔍 Recent Agent Activity")
    
    # Refresh button
    if st.button("🔄 Refresh Logs"):
        st.rerun()
    
    agent_logs = db_manager.get_agent_logs(20)
    
    if agent_logs is not None and not agent_logs.empty:
        # Display logs in a nice format
        for _, log in agent_logs.iterrows():
            timestamp = log['timestamp']
            status_icon = "✅" if log['status'] == 'success' else "❌" if log['status'] == 'error' else "⚠️"
            
            with st.container():
                col1, col2, col3 = st.columns([1, 2, 4])
                
                with col1:
                    st.write(f"{status_icon} {log['status'].title()}")
                
                with col2:
                    st.write(f"**{log['agent_name']}**")
                
                with col3:
                    st.write(f"{log['action']}: {log['details']}")
                    st.caption(f"🕒 {timestamp}")
            
            st.divider()
    else:
        st.info("No agent activity logs available.")

with tab5:
    st.header("Communication Center")
    
    # Email templates
    st.subheader("📧 Email Templates")
    
    col1, col2 = st.columns(2)
    
    with col1:
        template_type = st.selectbox("Template Type", [
            "Application Received",
            "Interview Invitation", 
            "Rejection Notice",
            "Offer Letter",
            "Follow-up Reminder"
        ])
        
        # Template content based on type
        templates = {
            "Application Received": {
                "subject": "Application Received - {position}",
                "body": """Dear {candidate_name},

Thank you for your interest in the {position} role at our company. We have received your application and our team will review it shortly.

You can expect to hear back from us within 3-5 business days.

Best regards,
HR Team"""
            },
            "Interview Invitation": {
                "subject": "Interview Invitation - {position}",
                "body": """Dear {candidate_name},

We are pleased to invite you for an interview for the {position} role.

Interview Details:
- Date: {interview_date}
- Time: {interview_time}
- Duration: 45 minutes
- Format: Video call (link will be sent separately)

Please confirm your availability.

Best regards,
{hiring_manager}"""
            },
            "Rejection Notice": {
                "subject": "Update on Your Application - {position}",
                "body": """Dear {candidate_name},

Thank you for your interest in the {position} role and for taking the time to interview with us.

After careful consideration, we have decided to move forward with another candidate whose experience more closely matches our current needs.

We encourage you to apply for future opportunities that match your skills and experience.

Best regards,
HR Team"""
            }
        }
        
        current_template = templates.get(template_type, {"subject": "", "body": ""})
        
        subject = st.text_input("Subject", value=current_template["subject"])
        body = st.text_area("Email Body", value=current_template["body"], height=200)
    
    with col2:
        st.subheader("📊 Email Statistics")
        
        # Mock email stats
        email_stats = {
            "Total Sent Today": 47,
            "Open Rate": "68%",
            "Response Rate": "34%",
            "Bounce Rate": "2%"
        }
        
        for stat, value in email_stats.items():
            st.metric(stat, value)
        
        st.divider()
        
        # Send test email
        st.subheader("🧪 Send Test Email")
        test_email = st.text_input("Test Email Address")
        
        if st.button("Send Test Email") and test_email:
            with st.spinner("Sending test email..."):
                time.sleep(1)
                
                # Log activity
                db_manager.log_agent_activity(
                    "Email Service",
                    "test_email",
                    f"Test email sent to {test_email}",
                    "success"
                )
            
            st.success(f"Test email sent to {test_email}")
    
    st.divider()
    
    # Bulk email sending
    st.subheader("📤 Bulk Email Campaign")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        recipient_filter = st.selectbox("Send to", [
            "All New Candidates",
            "Interview Scheduled",
            "Pending Response",
            "Custom Selection"
        ])
    
    with col2:
        campaign_template = st.selectbox("Use Template", list(templates.keys()))
    
    with col3:
        if st.button("📧 Send Campaign"):
            with st.spinner("Sending bulk emails..."):
                # Get candidates based on filter
                candidates_df = db_manager.get_candidates()
                
                if candidates_df is not None and not candidates_df.empty:
                    if recipient_filter == "All New Candidates":
                        recipients = candidates_df[candidates_df['status'] == 'New']
                    elif recipient_filter == "Interview Scheduled":
                        recipients = candidates_df[candidates_df['status'] == 'Interview']
                    else:
                        recipients = candidates_df
                    
                    time.sleep(2)  # Simulate sending
                    
                    # Log activity
                    db_manager.log_agent_activity(
                        "Email Service",
                        "bulk_campaign",
                        f"Bulk email sent to {len(recipients)} candidates",
                        "success"
                    )
                    
                    st.success(f"Campaign sent to {len(recipients)} recipients!")
                else:
                    st.warning("No candidates found to send emails to.")
    
    st.divider()
    
    # Communication history
    st.subheader("📜 Recent Communications")
    
    # Mock communication history
    communications = [
        {"timestamp": "2024-06-14 10:30", "type": "Email", "recipient": "john.doe@email.com", "subject": "Interview Invitation", "status": "Delivered"},
        {"timestamp": "2024-06-14 09:15", "type": "SMS", "recipient": "+1-555-1234", "subject": "Interview Reminder", "status": "Delivered"},
        {"timestamp": "2024-06-14 08:45", "type": "Email", "recipient": "jane.smith@email.com", "subject": "Application Received", "status": "Opened"},
        {"timestamp": "2024-06-13 16:20", "type": "Email", "recipient": "mike.johnson@email.com", "subject": "Follow-up", "status": "Bounced"},
    ]
    
    for comm in communications:
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 1, 3, 1])
            
            with col1:
                st.write(f"📧 {comm['type']}")
                st.caption(comm['timestamp'])
            
            with col2:
                st.write(comm['recipient'])
            
            with col3:
                st.write(comm['subject'])
            
            with col4:
                status_color = "🟢" if comm['status'] == 'Delivered' else "🟡" if comm['status'] == 'Opened' else "🔴"
                st.write(f"{status_color} {comm['status']}")
        
        st.divider()

with tab6:
    st.header("System Settings")
    
    # API Configuration
    st.subheader("🔗 API Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Job Board APIs**")
        linkedin_enabled = st.checkbox("LinkedIn Integration", value=True)
        indeed_enabled = st.checkbox("Indeed Integration", value=True)
        glassdoor_enabled = st.checkbox("Glassdoor Integration", value=False)
        
        if linkedin_enabled:
            linkedin_key = st.text_input("LinkedIn API Key", type="password", placeholder="Enter LinkedIn API key")
        
        st.write("**Communication APIs**")
        sendgrid_enabled = st.checkbox("SendGrid Email", value=True)
        twilio_enabled = st.checkbox("Twilio SMS", value=False)
        
        if sendgrid_enabled:
            sendgrid_key = st.text_input("SendGrid API Key", type="password", placeholder="Enter SendGrid API key")
    
    with col2:
        st.write("**AI/ML Services**")
        openai_enabled = st.checkbox("OpenAI GPT", value=True)
        gcp_enabled = st.checkbox("Google Cloud AI", value=True)
        aws_enabled = st.checkbox("AWS Comprehend", value=False)
        
        if openai_enabled:
            openai_key = st.text_input("OpenAI API Key", type="password", placeholder="Enter OpenAI API key")
        
        st.write("**Calendar Integration**")
        google_cal_enabled = st.checkbox("Google Calendar", value=True)
        outlook_enabled = st.checkbox("Outlook Calendar", value=False)
        
        if google_cal_enabled:
            google_key = st.text_input("Google Calendar API Key", type="password", placeholder="Enter Google API key")
    
    st.divider()
    
    # Agent Configuration
    st.subheader("🤖 Agent Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Sourcing Agent**")
        sourcing_frequency = st.selectbox("Sourcing Frequency", ["Every 15 minutes", "Hourly", "Daily", "Weekly"], index=1)
        max_candidates_per_run = st.number_input("Max Candidates per Run", value=10, min_value=1, max_value=100)
        sourcing_keywords = st.text_area("Default Keywords", value="software engineer, python, javascript, react")
        
        st.write("**Screening Agent**")
        auto_screening = st.checkbox("Enable Auto-Screening", value=True)
        screening_threshold = st.slider("Auto-Screen Threshold", 0, 100, 70)
        rejection_threshold = st.slider("Auto-Rejection Threshold", 0, 100, 40)
    
    with col2:
        st.write("**Interview Agent**")
        auto_scheduling = st.checkbox("Enable Auto-Scheduling", value=True)
        interview_buffer_hours = st.number_input("Interview Buffer (hours)", value=24, min_value=1, max_value=168)
        default_duration = st.selectbox("Default Interview Duration", ["30 min", "45 min", "60 min", "90 min"], index=1)
        
        st.write("**Notification Settings**")
        email_notifications = st.checkbox("Email Notifications", value=True)
        slack_notifications = st.checkbox("Slack Notifications", value=False)
        sms_notifications = st.checkbox("SMS Notifications", value=False)
        
        if slack_notifications:
            slack_webhook = st.text_input("Slack Webhook URL", placeholder="https://hooks.slack.com/...")
    
    st.divider()
    
    # Database Management
    st.subheader("💾 Database Management")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 View Database Stats"):
            candidates_count = len(db_manager.get_candidates() or [])
            jobs_count = len(db_manager.get_jobs() or [])
            logs_count = len(db_manager.get_agent_logs(1000) or [])
            
            st.info(f"""
            **Database Statistics:**
            - Candidates: {candidates_count}
            - Jobs: {jobs_count}
            - Agent Logs: {logs_count}
            - Database Size: {os.path.getsize(DATABASE_PATH) / 1024:.1f} KB
            """)
    
    with col2:
        if st.button("🗑️ Clear Old Logs"):
            # Clear logs older than 30 days
            cutoff_date = datetime.now() - timedelta(days=30)
            result = db_manager.execute_query(
                "DELETE FROM agent_logs WHERE timestamp < ?",
                (cutoff_date,)
            )
            
            if result is not None:
                st.success(f"Cleared {result} old log entries")
            else:
                st.error("Failed to clear logs")
    
    with col3:
        if st.button("💾 Backup Database"):
            with st.spinner("Creating backup..."):
                import shutil
                backup_path = f"hr_recruiting_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(DATABASE_PATH, backup_path)
                time.sleep(1)
            
            st.success(f"Database backed up to {backup_path}")
    
    st.divider()
    
    # Save all settings
    if st.button("💾 Save All Settings", type="primary"):
        with st.spinner("Saving settings..."):
            time.sleep(2)
            
            # In a real application, save settings to database
            # db_manager.save_settings({...})
            
            # Log activity
            db_manager.log_agent_activity(
                "System",
                "settings_update",
                "System settings updated",
                "success"
            )
        
        st.success("All settings saved successfully!")
        st.balloons()

# Footer
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("🤖 HR Recruiting Automation Platform")

with col2:
    st.caption("Powered by GCP Agentic Framework & MCP")

with col3:
    if st.button("📞 Support"):
        st.info("Contact: support@hrautomation.com")

# Auto-refresh for real-time updates
if st.checkbox("🔄 Auto-refresh (every 30s)", value=False):
    time.sleep(30)
    st.rerun()
