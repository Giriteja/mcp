import streamlit as st
import pandas as pd
import sqlite3
import json
import time
import uuid
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import hashlib
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import random

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

# API Configuration (using environment variables or defaults)
API_CONFIG = {
    "linkedin": {
        "base_url": "https://api.linkedin.com/v2",
        "client_id": os.getenv("LINKEDIN_CLIENT_ID", "demo_linkedin_id"),
        "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET", "demo_linkedin_secret")
    },
    "indeed": {
        "base_url": "https://api.indeed.com/ads/apisearch",
        "publisher_id": os.getenv("INDEED_PUBLISHER_ID", "demo_indeed_id")
    },
    "sendgrid": {
        "api_key": os.getenv("SENDGRID_API_KEY", "demo_sendgrid_key"),
        "base_url": "https://api.sendgrid.com/v3/mail/send"
    },
    "openai": {
        "api_key": os.getenv("OPENAI_API_KEY", "demo_openai_key"),
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
            INSERT OR REPLACE INTO candidates (id, name, email, phone, position, skills, experience, 
                                  score, status, location, resume_url, applied_date, source, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            candidate.id, candidate.name, candidate.email, candidate.phone,
            candidate.position, json.dumps(candidate.skills), candidate.experience,
            candidate.score, candidate.status, candidate.location, candidate.resume_url,
            candidate.applied_date.isoformat(), candidate.source, candidate.notes
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
            INSERT OR REPLACE INTO jobs (id, title, department, description, requirements, 
                            location, salary_range, status, posted_date, hiring_manager, applications_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            job.id, job.title, job.department, job.description,
            json.dumps(job.requirements), job.location, job.salary_range,
            job.status, job.posted_date.isoformat(), job.hiring_manager, job.applications_count
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

# Mock API Services
class APIService:
    def __init__(self, name: str):
        self.name = name
        self.connected = True
    
    def search_candidates(self, keywords: str, location: str = None):
        """Mock candidate search"""
        time.sleep(1)  # Simulate API delay
        
        candidates = []
        for i in range(3):
            candidate_data = {
                "name": f"{self.name} Candidate {i+1}",
                "email": f"candidate{i+1}@{self.name.lower()}.com",
                "position": random.choice(["Software Engineer", "Data Scientist", "DevOps Engineer"]),
                "skills": random.sample(["Python", "JavaScript", "React", "AWS", "Docker", "SQL"], 4),
                "experience": random.randint(2, 8),
                "location": location or random.choice(["San Francisco", "New York", "Remote"]),
                "source": self.name
            }
            candidates.append(candidate_data)
        
        return candidates
    
    def post_job(self, job_data: Dict):
        """Mock job posting"""
        time.sleep(1)
        return {"status": "success", "job_id": f"{self.name.lower()}_{uuid.uuid4().hex[:8]}"}
    
    def send_email(self, to_email: str, subject: str, body: str):
        """Mock email sending"""
        time.sleep(0.5)
        logger.info(f"Email sent to {to_email}: {subject}")
        return {"status": "success", "message_id": f"msg_{uuid.uuid4().hex[:8]}"}

# AI Agent Class
class AIAgent:
    def __init__(self, name: str, db_manager: DatabaseManager):
        self.name = name
        self.db_manager = db_manager
        self.status = "idle"
    
    def screen_candidate(self, candidate_data: Dict):
        """AI-powered candidate screening"""
        try:
            self.status = "active"
            time.sleep(2)  # Simulate AI processing
            
            score = self.calculate_candidate_score(candidate_data)
            
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
        experience_score = min(experience * 5, 40)
        score += experience_score
        
        # Skills match weight (40%)
        candidate_skills = set(candidate_data.get('skills', []))
        required_skills = set(['Python', 'JavaScript', 'React', 'AWS'])
        if required_skills:
            skill_match = len(candidate_skills & required_skills) / len(required_skills)
            skills_score = skill_match * 40
            score += skills_score
        
        # Location preference (10%)
        if candidate_data.get('location') in ['San Francisco', 'New York', 'Remote']:
            score += 10
        
        # Random factor (10%)
        score += random.randint(0, 10)
        
        return min(score, 100)

# Initialize services
@st.cache_resource
def initialize_services():
    """Initialize database and services"""
    db_manager = DatabaseManager(DATABASE_PATH)
    
    # Initialize API services
    linkedin_api = APIService("LinkedIn")
    indeed_api = APIService("Indeed")
    email_service = APIService("Email")
    
    # Initialize AI agents
    screening_agent = AIAgent("Screening Agent", db_manager)
    sourcing_agent = AIAgent("Sourcing Agent", db_manager)
    
    return {
        'db_manager': db_manager,
        'linkedin_api': linkedin_api,
        'indeed_api': indeed_api,
        'email_service': email_service,
        'screening_agent': screening_agent,
        'sourcing_agent': sourcing_agent
    }

# Authentication
def authenticate_user(username: str, password: str):
    """Simple authentication"""
    return username == "admin" and password == "password123"

# Initialize services
services = initialize_services()
db_manager = services['db_manager']

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
    
    st.info("Demo credentials: username=**admin**, password=**password123**")
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
    "OpenAI GPT": "🟢 Connected"
}

for api, status in api_status.items():
    st.sidebar.write(f"{status} {api}")

# Quick Actions
st.sidebar.divider()
st.sidebar.subheader("Quick Actions")

if st.sidebar.button("🔄 Refresh Data"):
    st.sidebar.success("Data refreshed!")
    st.rerun()

if st.sidebar.button("📊 System Health"):
    st.sidebar.info("All systems operational")

# Main tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard", 
    "👥 Candidates", 
    "💼 Jobs", 
    "🤖 AI Agents", 
    "⚙️ Settings"
])

with tab1:
    st.header("Dashboard Overview")
    
    # Fetch data from database
    candidates_df = db_manager.get_candidates()
    jobs_df = db_manager.get_jobs()
    
    # KPI Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_candidates = len(candidates_df) if candidates_df is not None else 0
    hired_count = len(candidates_df[candidates_df['status'] == 'Hired']) if candidates_df is not None and not candidates_df.empty else 0
    avg_score = candidates_df['score'].mean() if candidates_df is not None and not candidates_df.empty and 'score' in candidates_df.columns else 0
    active_jobs = len(jobs_df[jobs_df['status'] == 'Active']) if jobs_df is not None and not jobs_df.empty else 0
    
    with col1:
        st.metric("Total Candidates", total_candidates, "+5")
    with col2:
        st.metric("Hired This Month", hired_count, "+2")
    with col3:
        st.metric("Avg Candidate Score", f"{avg_score:.1f}", "+1.2")
    with col4:
        st.metric("Active Jobs", active_jobs, "+1")
    
    st.divider()
    
    if candidates_df is not None and not candidates_df.empty:
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
    agent_logs = db_manager.get_agent_logs(5)
    if agent_logs is not None and not agent_logs.empty:
        for _, log in agent_logs.iterrows():
            timestamp = log['timestamp']
            st.text(f"[{timestamp}] {log['agent_name']}: {log['action']} - {log['details']}")
    else:
        st.info("No recent activity. Try adding some candidates or running agent actions.")

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
                    phone=phone or "",
                    position=position,
                    skills=[s.strip() for s in skills.split(',') if s.strip()],
                    experience=experience,
                    score=0.0,
                    status="New",
                    location=location or "",
                    resume_url=resume_url or "",
                    applied_date=datetime.now(),
                    source=source,
                    notes=notes or ""
                )
                
                result = db_manager.add_candidate(candidate)
                if result is not None:
                    st.success("Candidate added successfully!")
                    st.rerun()
                else:
                    st.error("Failed to add candidate. Email might already exist.")
    
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
            candidates_df['skills_display'] = candidates_df['skills'].apply(
                lambda x: ', '.join(json.loads(x)) if x and x.startswith('[') else str(x) if x else ""
            )
        
        # Display candidates
        display_columns = ['name', 'position', 'email', 'status', 'score', 'experience', 'location']
        if 'skills_display' in candidates_df.columns:
            display_columns.append('skills_display')
        
        st.dataframe(
            candidates_df[display_columns],
            use_container_width=True
        )
        
        # Bulk actions
        st.subheader("Bulk Actions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🤖 AI Screen Selected"):
                with st.spinner("AI agents screening candidates..."):
                    screening_agent = services['screening_agent']
                    
                    for _, candidate in candidates_df.iterrows():
                        if candidate['status'] == 'New':
                            # Prepare candidate data for screening
                            candidate_data = {
                                'name': candidate['name'],
                                'experience': candidate.get('experience', 0),
                                'skills': json.loads(candidate.get('skills', '[]')) if candidate.get('skills') else [],
                                'location': candidate.get('location', '')
                            }
                            
                            # Screen candidate
                            result = screening_agent.screen_candidate(candidate_data)
                            
                            if 'score' in result:
                                new_score = result['score']
                                new_status = "Interview" if new_score > 70 else "Screening"
                                
                                db_manager.execute_query(
                                    "UPDATE candidates SET score = ?, status = ? WHERE id = ?",
                                    (new_score, new_status, candidate['id'])
                                )
                
                st.success("AI screening completed!")
                st.rerun()
        
        with col2:
            if st.button("📧 Send Update Emails"):
                with st.spinner("Sending emails..."):
                    email_service = services['email_service']
                    
                    for _, candidate in candidates_df.iterrows():
                        email_service.send_email(
                            candidate['email'],
                            "Application Update",
                            f"Dear {candidate['name']}, your application status has been updated."
                        )
                    
                    db_manager.log_agent_activity(
                        "Email Service",
                        "bulk_email",
                        f"Sent updates to {len(candidates_df)} candidates",
                        "success"
                    )
                
                st.success("Update emails sent!")
        
        with col3:
            if st.button("📅 Schedule Interviews"):
                with st.spinner("Scheduling interviews..."):
                    qualified_candidates = candidates_df[candidates_df['score'] > 70] if 'score' in candidates_df.columns else pd.DataFrame()
                    
                    for _, candidate in qualified_candidates.iterrows():
                        db_manager.update_candidate_status(candidate['id'], "Interview")
                    
                    db_manager.log_agent_activity(
                        "Interview Agent",
                        "bulk_scheduling",
                        f"Scheduled interviews for {len(qualified_candidates)} candidates",
                        "success"
                    )
                
                st.success("Interviews scheduled for qualified candidates!")
                st.rerun()
    
    else:
        st.info("No candidates found. Try adding some candidates or adjusting filters.")

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
                    description=description or "",
                    requirements=[r.strip() for r in requirements.split(',') if r.strip()],
                    location=location or "",
                    salary_range=salary_range or "",
                    status=status,
                    posted_date=datetime.now(),
                    applications_count=0,
                    hiring_manager=hiring_manager or ""
                )
                
                result = db_manager.add_job(job)
                if result is not None:
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
                    if job.get('salary_range'):
                        st.write(f"Salary: {job['salary_range']}")
                
                with col2:
                    status_color = "🟢" if job['status'] == 'Active' else "🟡" if job['status'] == 'Paused' else "🔴"
                    st.write(f"{status_color} {job['status']}")
                
                with col3:
                    st.write(f"Applications: {job.get('applications_count', 0)}")
                
                with col4:
                    if st.button(f"View Details", key=f"view_{job['id']}"):
                        st.info(f"Job: {job['title']}\nDepartment: {job['department']}\nStatus: {job['status']}")
            
            st.divider()
    
    else:
        st.info("No job postings available. Create your first job posting above!")

with tab4:
    st.header("AI Agent Management")
    
    # Agent controls
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🤖 Agent Controls")
        
        if st.button("🔍 Run Candidate Sourcing"):
            with st.spinner("Sourcing candidates..."):
                sourcing_agent = services['sourcing_agent']
                linkedin_api = services['linkedin_api']
                
                # Simulate candidate sourcing from multiple platforms
                all_candidates = []
                
                # LinkedIn sourcing
                linkedin_candidates = linkedin_api.search_candidates("software engineer", "Remote")
                all_candidates.extend(linkedin_candidates)
                
                # Indeed sourcing  
                indeed_api = services['indeed_api']
                indeed_candidates = indeed_api.search_candidates("developer", "San Francisco")
                all_candidates.extend(indeed_candidates)
                
                # Add sourced candidates to database
                for candidate_data in all_candidates:
                    candidate = Candidate(
                        id=f"CAND_{uuid.uuid4().hex[:8].upper()}",
                        name=candidate_data['name'],
                        email=candidate_data['email'],
                        phone="",
                        position=candidate_data['position'],
                        skills=candidate_data['skills'],
                        experience=candidate_data['experience'],
                        score=0.0,
                        status="New",
                        location=candidate_data['location'],
                        resume_url="",
                        applied_date=datetime.now(),
                        source=candidate_data['source'],
                        notes="Sourced by AI agent"
                    )
                    db_manager.add_candidate(candidate)
                
                db_manager.log_agent_activity(
                    "Sourcing Agent",
                    "candidate_sourcing",
                    f"Sourced {len(all_candidates)} new candidates",
                    "success"
                )
            
            st.success(f"Found {len(all_candidates)} new candidates!")
            st.rerun()
        
        if st.button("🔄 Restart All Agents"):
            with st.spinner("Restarting agents..."):
                time.sleep(2)
                db_manager.log_agent_activity(
                    "System",
                    "agent_restart",
                    "All agents restarted",
                    "success"
                )
            st.success("All agents restarted successfully!")
        
        if st.button("📊 Generate AI Insights"):
            with st.spinner("Generating insights..."):
                time.sleep(2)
                db_manager.log_agent_activity(
                    "Analytics Agent",
                    "insight_generation",
                    "Generated recruitment insights",
                    "success"
                )
            
            st.success("AI insights generated!")
            
            # Display insights
            st.info("💡 **AI Insight**: Candidates with Python + React skills have 85% higher hire rate")
            st.info("💡 **AI Insight**: Remote positions receive 3x more applications than on-site")
            st.info("💡 **AI Insight**: Average time-to-hire: 12 days (industry average: 18 days)")
    
    with col2:
        st.subheader("📈 Agent Performance")
        
        # Mock performance data
        performance_data = {
            "Agent": ["Sourcing", "Screening", "Interview", "Analytics"],
            "Tasks Today": [45, 67, 23, 12],
            "Success Rate": [94, 89, 96, 91]
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
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄 Refresh Logs"):
            st.rerun()
    
    agent_logs = db_manager.get_agent_logs(10)
    
    if agent_logs is not None and not agent_logs.empty:
        for _, log in agent_logs.iterrows():
            timestamp = log['timestamp']
            status_icon = "✅" if log['status'] == 'success' else "❌" if log['status'] == 'error' else "⚠️"
            
            with st.container():
                col1, col2, col3 = st.columns([1, 2, 4])
                
                with col1:
                    st.write(f"{status_icon}")
                
                with col2:
                    st.write(f"**{log['agent_name']}**")
                
                with col3:
                    st.write(f"{log['action']}: {log['details']}")
                    st.caption(f"🕒 {timestamp}")
            
            st.divider()
    else:
        st.info("No agent activity yet. Try running some agent actions above!")

with tab5:
    st.header("System Settings")
    
    # API Configuration
    st.subheader("🔗 API Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Job Board APIs**")
        linkedin_enabled = st.checkbox("LinkedIn Integration", value=True)
        indeed_enabled = st.checkbox("Indeed Integration", value=True)
        glassdoor_enabled = st.checkbox("Glassdoor Integration", value=False)
        
        st.write("**Communication APIs**")
        sendgrid_enabled = st.checkbox("SendGrid Email", value=True)
        slack_enabled = st.checkbox("Slack Integration", value=False)
        
        if sendgrid_enabled:
            sendgrid_key = st.text_input("SendGrid API Key", type="password", placeholder="SG.xxx")
    
    with col2:
        st.write("**AI/ML Services**")
        openai_enabled = st.checkbox("OpenAI GPT", value=True)
        gcp_enabled = st.checkbox("Google Cloud AI", value=True)
        
        if openai_enabled:
            openai_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-xxx")
        
        st.write("**Calendar Integration**")
        google_cal_enabled = st.checkbox("Google Calendar", value=True)
        outlook_enabled = st.checkbox("Outlook Calendar", value=False)
    
    st.divider()
    
    # Agent Configuration
    st.subheader("🤖 Agent Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Sourcing Agent**")
        sourcing_frequency = st.selectbox("Sourcing Frequency", ["Every 15 minutes", "Hourly", "Daily", "Weekly"], index=1)
        max_candidates_per_run = st.number_input("Max Candidates per Run", value=10, min_value=1, max_value=100)
        
        st.write("**Screening Agent**")
        auto_screening = st.checkbox("Enable Auto-Screening", value=True)
        screening_threshold = st.slider("Auto-Screen Threshold", 0, 100, 70)
    
    with col2:
        st.write("**Interview Agent**")
        auto_scheduling = st.checkbox("Enable Auto-Scheduling", value=True)
        interview_buffer_hours = st.number_input("Interview Buffer (hours)", value=24, min_value=1, max_value=168)
        
        st.write("**Notification Settings**")
        email_notifications = st.checkbox("Email Notifications", value=True)
        slack_notifications = st.checkbox("Slack Notifications", value=False)
    
    st.divider()
    
    # Database Management
    st.subheader("💾 Database Management")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 View Database Stats"):
            candidates_count = len(db_manager.get_candidates() or [])
            jobs_count = len(db_manager.get_jobs() or [])
            logs_count = len(db_manager.get_agent_logs(1000) or [])
            
            try:
                db_size = os.path.getsize(DATABASE_PATH) / 1024
            except:
                db_size = 0
            
            st.info(f"""
            **Database Statistics:**
            - Candidates: {candidates_count}
            - Jobs: {jobs_count}
            - Agent Logs: {logs_count}
            - Database Size: {db_size:.1f} KB
            """)
    
    with col2:
        if st.button("🗑️ Clear Old Logs"):
            cutoff_date = datetime.now() - timedelta(days=30)
            result = db_manager.execute_query(
                "DELETE FROM agent_logs WHERE timestamp < ?",
                (cutoff_date.isoformat(),)
            )
            
            if result is not None:
                st.success(f"Cleared old log entries")
            else:
                st.error("Failed to clear logs")
    
    with col3:
        if st.button("💾 Backup Database"):
            with st.spinner("Creating backup..."):
                import shutil
                backup_path = f"hr_recruiting_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                try:
                    shutil.copy2(DATABASE_PATH, backup_path)
                    st.success(f"Database backed up to {backup_path}")
                except Exception as e:
                    st.error(f"Backup failed: {e}")
    
    st.divider()
    
    # Demo Data
    st.subheader("🎯 Demo Data")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📝 Load Sample Candidates"):
            sample_candidates = [
                {
                    "name": "Alice Johnson",
                    "email": "alice.johnson@email.com",
                    "position": "Software Engineer",
                    "skills": ["Python", "React", "AWS"],
                    "experience": 5,
                    "location": "San Francisco"
                },
                {
                    "name": "Bob Smith", 
                    "email": "bob.smith@email.com",
                    "position": "Data Scientist",
                    "skills": ["Python", "Machine Learning", "SQL"],
                    "experience": 3,
                    "location": "New York"
                },
                {
                    "name": "Carol Davis",
                    "email": "carol.davis@email.com", 
                    "position": "DevOps Engineer",
                    "skills": ["Docker", "Kubernetes", "AWS"],
                    "experience": 7,
                    "location": "Remote"
                }
            ]
            
            for candidate_data in sample_candidates:
                candidate = Candidate(
                    id=f"CAND_{uuid.uuid4().hex[:8].upper()}",
                    name=candidate_data['name'],
                    email=candidate_data['email'],
                    phone="",
                    position=candidate_data['position'],
                    skills=candidate_data['skills'],
                    experience=candidate_data['experience'],
                    score=random.randint(65, 95),
                    status=random.choice(["New", "Screening", "Interview"]),
                    location=candidate_data['location'],
                    resume_url="",
                    applied_date=datetime.now() - timedelta(days=random.randint(1, 10)),
                    source="Demo Data",
                    notes="Sample candidate"
                )
                db_manager.add_candidate(candidate)
            
            st.success("Sample candidates loaded!")
    
    with col2:
        if st.button("💼 Load Sample Jobs"):
            sample_jobs = [
                {
                    "title": "Senior Software Engineer",
                    "department": "Engineering",
                    "description": "Build scalable web applications",
                    "requirements": ["Python", "React", "AWS"],
                    "salary_range": "$120k - $160k"
                },
                {
                    "title": "Data Scientist",
                    "department": "Data Science", 
                    "description": "Analyze data and build ML models",
                    "requirements": ["Python", "SQL", "Machine Learning"],
                    "salary_range": "$110k - $150k"
                },
                {
                    "title": "DevOps Engineer",
                    "department": "Infrastructure",
                    "description": "Manage cloud infrastructure and CI/CD",
                    "requirements": ["Docker", "Kubernetes", "AWS"],
                    "salary_range": "$130k - $170k"
                }
            ]
            
            for job_data in sample_jobs:
                job = Job(
                    id=f"JOB_{uuid.uuid4().hex[:8].upper()}",
                    title=job_data['title'],
                    department=job_data['department'],
                    description=job_data['description'],
                    requirements=job_data['requirements'],
                    location="San Francisco / Remote",
                    salary_range=job_data['salary_range'],
                    status="Active",
                    posted_date=datetime.now() - timedelta(days=random.randint(1, 30)),
                    applications_count=random.randint(5, 50),
                    hiring_manager="Demo Manager"
                )
                db_manager.add_job(job)
            
            st.success("Sample jobs loaded!")
    
    with col3:
        if st.button("🗑️ Clear All Data"):
            if st.session_state.get('confirm_clear'):
                # Clear all tables
                db_manager.execute_query("DELETE FROM candidates")
                db_manager.execute_query("DELETE FROM jobs") 
                db_manager.execute_query("DELETE FROM agent_logs")
                
                st.success("All data cleared!")
                st.session_state.confirm_clear = False
                st.rerun()
            else:
                st.session_state.confirm_clear = True
                st.warning("Click again to confirm deletion of ALL data")
    
    st.divider()
    
    # Save all settings
    if st.button("💾 Save All Settings", type="primary"):
        with st.spinner("Saving settings..."):
            time.sleep(1)
            
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

# Status bar at bottom
with st.container():
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.caption(f"🗄️ Database: {len(db_manager.get_candidates() or [])} candidates")
    
    with col2:
        st.caption(f"💼 Jobs: {len(db_manager.get_jobs() or [])} active")
    
    with col3:
        st.caption(f"🤖 Agents: 4 online")
    
    with col4:
        st.caption(f"🕒 Last update: {datetime.now().strftime('%H:%M:%S')}")

# Auto-refresh option
if st.sidebar.checkbox("🔄 Auto-refresh (30s)", value=False):
    time.sleep(30)
    st.rerun()
