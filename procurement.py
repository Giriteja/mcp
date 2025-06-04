import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="HR Recruiting Automation",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'candidates' not in st.session_state:
    st.session_state.candidates = []
if 'jobs' not in st.session_state:
    st.session_state.jobs = []
if 'agent_logs' not in st.session_state:
    st.session_state.agent_logs = []

# Sample data
def generate_sample_candidates():
    names = ["John Smith", "Sarah Johnson", "Mike Chen", "Emily Davis", "Alex Rodriguez", "Lisa Wang", "David Brown", "Anna Garcia"]
    skills = ["Python", "Java", "React", "AWS", "Machine Learning", "Docker", "Kubernetes", "SQL"]
    positions = ["Software Engineer", "Data Scientist", "DevOps Engineer", "Frontend Developer"]
    
    candidates = []
    for i in range(8):
        candidate = {
            "id": f"CAND_{i+1:03d}",
            "name": names[i],
            "email": f"{names[i].lower().replace(' ', '.')}@email.com",
            "position": random.choice(positions),
            "skills": random.sample(skills, random.randint(3, 6)),
            "experience": random.randint(1, 10),
            "score": random.randint(65, 95),
            "status": random.choice(["New", "Screening", "Interview", "Hired", "Rejected"]),
            "applied_date": datetime.now() - timedelta(days=random.randint(1, 30)),
            "location": random.choice(["San Francisco", "New York", "Austin", "Seattle", "Boston"])
        }
        candidates.append(candidate)
    return candidates

def generate_sample_jobs():
    jobs = [
        {"id": "JOB_001", "title": "Senior Software Engineer", "department": "Engineering", "status": "Active", "applications": 45},
        {"id": "JOB_002", "title": "Data Scientist", "department": "Data", "status": "Active", "applications": 32},
        {"id": "JOB_003", "title": "DevOps Engineer", "department": "Infrastructure", "status": "Active", "applications": 28},
        {"id": "JOB_004", "title": "Frontend Developer", "department": "Engineering", "status": "Paused", "applications": 15},
    ]
    return jobs

# Initialize sample data if empty
if not st.session_state.candidates:
    st.session_state.candidates = generate_sample_candidates()
if not st.session_state.jobs:
    st.session_state.jobs = generate_sample_jobs()

# Sidebar - Agent Controls
st.sidebar.title("🤖 Agent Controls")

# Agent status indicators
st.sidebar.subheader("Agent Status")
agents = {
    "Sourcing Agent": "🟢 Active",
    "Screening Agent": "🟢 Active", 
    "Interview Agent": "🟡 Idle",
    "Evaluation Agent": "🟢 Active"
}

for agent, status in agents.items():
    st.sidebar.write(f"{status} {agent}")

st.sidebar.divider()

# MCP Server Status
st.sidebar.subheader("MCP Server Status")
mcp_servers = {
    "ATS Integration": "🟢 Connected",
    "Job Boards API": "🟢 Connected",
    "Email Service": "🟢 Connected",
    "Calendar API": "🟡 Degraded"
}

for server, status in mcp_servers.items():
    st.sidebar.write(f"{status} {server}")

st.sidebar.divider()

# Quick Actions
st.sidebar.subheader("Quick Actions")
if st.sidebar.button("🔄 Refresh All Agents"):
    st.sidebar.success("Agents refreshed!")
    
if st.sidebar.button("📤 Sync with ATS"):
    with st.sidebar:
        with st.spinner("Syncing..."):
            time.sleep(2)
        st.success("ATS sync complete!")

if st.sidebar.button("📧 Send Bulk Updates"):
    st.sidebar.success("Bulk updates sent!")

# Main content
st.title("🤖 HR Recruiting Automation Dashboard")
st.subheader("GCP Agentic Framework + MCP Integration")

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Overview", "👥 Candidates", "💼 Jobs", "🤖 Agent Activity", "⚙️ Configuration"])

with tab1:
    # KPI Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Candidates", len(st.session_state.candidates), "+5")
    with col2:
        hired_count = len([c for c in st.session_state.candidates if c['status'] == 'Hired'])
        st.metric("Hired This Month", hired_count, "+2")
    with col3:
        avg_score = sum(c['score'] for c in st.session_state.candidates) / len(st.session_state.candidates)
        st.metric("Avg Candidate Score", f"{avg_score:.1f}", "+1.2")
    with col4:
        active_jobs = len([j for j in st.session_state.jobs if j['status'] == 'Active'])
        st.metric("Active Jobs", active_jobs, "0")

    st.divider()

    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Candidate status distribution
        status_counts = {}
        for candidate in st.session_state.candidates:
            status = candidate['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        fig = px.pie(
            values=list(status_counts.values()),
            names=list(status_counts.keys()),
            title="Candidate Status Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Score distribution
        scores = [c['score'] for c in st.session_state.candidates]
        fig = px.histogram(
            x=scores,
            nbins=10,
            title="Candidate Score Distribution",
            labels={'x': 'Score', 'y': 'Count'}
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Candidate Management")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Filter by Status", ["All"] + list(set(c['status'] for c in st.session_state.candidates)))
    with col2:
        position_filter = st.selectbox("Filter by Position", ["All"] + list(set(c['position'] for c in st.session_state.candidates)))
    with col3:
        min_score = st.slider("Minimum Score", 0, 100, 0)
    
    # Filter candidates
    filtered_candidates = st.session_state.candidates
    if status_filter != "All":
        filtered_candidates = [c for c in filtered_candidates if c['status'] == status_filter]
    if position_filter != "All":
        filtered_candidates = [c for c in filtered_candidates if c['position'] == position_filter]
    filtered_candidates = [c for c in filtered_candidates if c['score'] >= min_score]
    
    # Candidate table
    if filtered_candidates:
        df = pd.DataFrame(filtered_candidates)
        df['skills'] = df['skills'].apply(lambda x: ', '.join(x))
        df['applied_date'] = df['applied_date'].dt.strftime('%Y-%m-%d')
        
        st.dataframe(
            df[['name', 'position', 'score', 'status', 'experience', 'skills', 'location', 'applied_date']],
            use_container_width=True
        )
    else:
        st.info("No candidates match the current filters.")
    
    # Bulk actions
    st.subheader("Bulk Actions")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🤖 Auto-Screen Selected"):
            with st.spinner("AI agents screening candidates..."):
                time.sleep(3)
            st.success("Auto-screening completed for selected candidates!")
    
    with col2:
        if st.button("📧 Send Update Emails"):
            st.success("Update emails sent to all candidates!")
    
    with col3:
        if st.button("📅 Schedule Interviews"):
            st.success("Interviews scheduled for qualified candidates!")

with tab3:
    st.subheader("Job Management")
    
    # Job posting form
    with st.expander("➕ Post New Job"):
        col1, col2 = st.columns(2)
        with col1:
            job_title = st.text_input("Job Title")
            department = st.selectbox("Department", ["Engineering", "Data", "Infrastructure", "Marketing", "Sales"])
        with col2:
            location = st.text_input("Location")
            experience_level = st.selectbox("Experience Level", ["Entry", "Mid", "Senior", "Lead"])
        
        job_description = st.text_area("Job Description")
        required_skills = st.text_input("Required Skills (comma-separated)")
        
        if st.button("🚀 Post Job & Activate Sourcing Agent"):
            with st.spinner("Posting job and activating AI sourcing..."):
                time.sleep(2)
            st.success("Job posted successfully! Sourcing agent is now actively searching for candidates.")
    
    # Current jobs
    st.subheader("Current Job Openings")
    df_jobs = pd.DataFrame(st.session_state.jobs)
    
    for _, job in df_jobs.iterrows():
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.write(f"**{job['title']}** - {job['department']}")
                st.write(f"Job ID: {job['id']}")
            with col2:
                st.write(f"Status: {job['status']}")
            with col3:
                st.write(f"Applications: {job['applications']}")
            with col4:
                if st.button(f"View Details", key=f"view_{job['id']}"):
                    st.info(f"Viewing details for {job['title']}")
        st.divider()

with tab4:
    st.subheader("Agent Activity Monitor")
    
    # Real-time agent logs
    st.subheader("🔴 Live Agent Activity")
    
    # Simulate agent activity
    if st.button("🔄 Refresh Activity"):
        activities = [
            "Sourcing Agent: Found 3 new candidates for Senior Software Engineer position",
            "Screening Agent: Completed initial screening for candidate CAND_001",
            "Interview Agent: Scheduled interview for candidate CAND_003 with hiring manager",
            "Evaluation Agent: Updated candidate scores based on technical assessment",
            "MCP ATS Server: Synced 12 candidate records with Workday",
            "MCP Email Server: Sent follow-up emails to 8 candidates"
        ]
        
        for activity in activities:
            timestamp = datetime.now().strftime("%H:%M:%S")
            st.text(f"[{timestamp}] {activity}")
    
    st.divider()
    
    # Agent performance metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Agent Performance")
        performance_data = {
            "Agent": ["Sourcing", "Screening", "Interview", "Evaluation"],
            "Tasks Completed": [142, 89, 34, 67],
            "Success Rate": [94, 87, 92, 89]
        }
        df_performance = pd.DataFrame(performance_data)
        
        fig = px.bar(df_performance, x="Agent", y="Tasks Completed", title="Tasks Completed by Agent")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("MCP Server Health")
        server_health = {
            "Server": ["ATS Integration", "Job Boards", "Email Service", "Calendar API"],
            "Uptime %": [99.8, 99.2, 98.9, 97.5],
            "Response Time (ms)": [145, 230, 89, 340]
        }
        df_health = pd.DataFrame(server_health)
        
        fig = px.bar(df_health, x="Server", y="Uptime %", title="MCP Server Uptime")
        st.plotly_chart(fig, use_container_width=True)

with tab5:
    st.subheader("System Configuration")
    
    # Agent configuration
    st.subheader("🤖 Agent Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Sourcing Agent**")
        sourcing_enabled = st.checkbox("Enable Sourcing Agent", value=True)
        sourcing_frequency = st.selectbox("Sourcing Frequency", ["Hourly", "Daily", "Weekly"])
        max_candidates_per_job = st.number_input("Max Candidates per Job", value=50, min_value=10, max_value=200)
        
        st.write("**Screening Agent**")
        screening_enabled = st.checkbox("Enable Screening Agent", value=True)
        min_score_threshold = st.slider("Minimum Score Threshold", 0, 100, 70)
        auto_reject_below = st.slider("Auto-reject Below Score", 0, 100, 50)
    
    with col2:
        st.write("**Interview Agent**") 
        interview_enabled = st.checkbox("Enable Interview Agent", value=True)
        auto_schedule = st.checkbox("Auto-schedule Interviews", value=True)
        interview_buffer_days = st.number_input("Interview Buffer Days", value=2, min_value=1, max_value=7)
        
        st.write("**Evaluation Agent**")
        evaluation_enabled = st.checkbox("Enable Evaluation Agent", value=True)
        skill_matching_weight = st.slider("Skill Matching Weight", 0.0, 1.0, 0.6)
        experience_weight = st.slider("Experience Weight", 0.0, 1.0, 0.4)
    
    st.divider()
    
    # MCP Server configuration
    st.subheader("🔗 MCP Server Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**ATS Integration**")
        ats_provider = st.selectbox("ATS Provider", ["Workday", "Greenhouse", "Lever", "BambooHR"])
        ats_sync_frequency = st.selectbox("Sync Frequency", ["Real-time", "Every 15 mins", "Hourly"])
        
        st.write("**Job Board APIs**")
        job_boards = st.multiselect("Enabled Job Boards", ["LinkedIn", "Indeed", "Glassdoor", "AngelList"], default=["LinkedIn", "Indeed"])
    
    with col2:
        st.write("**Communication Settings**")
        email_provider = st.selectbox("Email Provider", ["SendGrid", "AWS SES", "Mailgun"])
        enable_sms = st.checkbox("Enable SMS Notifications")
        
        st.write("**Calendar Integration**")
        calendar_provider = st.selectbox("Calendar Provider", ["Google Calendar", "Outlook", "Calendly"])
        default_interview_duration = st.selectbox("Default Interview Duration", ["30 min", "45 min", "60 min"], index=1)
    
    if st.button("💾 Save Configuration"):
        st.success("Configuration saved successfully! Agents will restart with new settings.")

# Footer
st.divider()
st.caption("HR Recruiting Automation Dashboard - Powered by GCP Agentic Framework & MCP Integration")
