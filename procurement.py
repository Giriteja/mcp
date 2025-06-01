import streamlit as st
import json
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# =============================================================================
# STREAMLIT CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Procurement Multi-Agent System",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://docs.streamlit.io/',
        'Report a bug': None,
        'About': "Multi-Agent Procurement System built with Google's ADK and MCP architecture"
    }
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        padding: 1rem;
        border-bottom: 3px solid #1f77b4;
    }
    .agent-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 0.5rem 0;
    }
    .metric-card {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if 'procurement_history' not in st.session_state:
    st.session_state.procurement_history = []

if 'current_request' not in st.session_state:
    st.session_state.current_request = None

if 'demo_mode' not in st.session_state:
    st.session_state.demo_mode = True

# =============================================================================
# MOCK MCP SERVERS (Same as before but streamlined)
# =============================================================================

class ProcurementAgents:
    """All procurement agents in one class for Streamlit"""
    
    @staticmethod
    def find_suppliers(item: str, quantity: int) -> Dict:
        """Find suppliers for a specific item"""
        suppliers_db = {
            "laptops": [
                {"name": "TechCorp", "price": 899.99, "availability": 50, "lead_time": 5, "rating": 4.5},
                {"name": "ElectroSupply", "price": 849.99, "availability": 30, "lead_time": 7, "rating": 4.2},
                {"name": "BusinessTech", "price": 879.99, "availability": 100, "lead_time": 3, "rating": 4.7}
            ],
            "office_chairs": [
                {"name": "OfficePro", "price": 249.99, "availability": 200, "lead_time": 10, "rating": 4.3},
                {"name": "ComfortSeating", "price": 199.99, "availability": 150, "lead_time": 14, "rating": 4.0},
                {"name": "ErgoFurniture", "price": 299.99, "availability": 75, "lead_time": 7, "rating": 4.6}
            ],
            "printers": [
                {"name": "PrintTech", "price": 459.99, "availability": 25, "lead_time": 5, "rating": 4.4},
                {"name": "OfficePrint", "price": 429.99, "availability": 40, "lead_time": 8, "rating": 4.1},
                {"name": "ReliablePrint", "price": 489.99, "availability": 15, "lead_time": 3, "rating": 4.8}
            ],
            "monitors": [
                {"name": "DisplayTech", "price": 329.99, "availability": 60, "lead_time": 6, "rating": 4.5},
                {"name": "ScreenSupply", "price": 299.99, "availability": 45, "lead_time": 9, "rating": 4.2},
                {"name": "ViewPro", "price": 349.99, "availability": 30, "lead_time": 4, "rating": 4.7}
            ]
        }
        
        available_suppliers = suppliers_db.get(item.lower(), [])
        suitable_suppliers = [s for s in available_suppliers if s["availability"] >= quantity]
        
        return {
            "item": item,
            "quantity_requested": quantity,
            "suppliers": suitable_suppliers,
            "total_suppliers_found": len(suitable_suppliers)
        }
    
    @staticmethod
    def check_budget_availability(department: str, amount: float) -> Dict:
        """Check budget availability"""
        department_budgets = {
            "IT": {"total": 50000, "used": 23000, "remaining": 27000},
            "HR": {"total": 25000, "used": 12000, "remaining": 13000},
            "Marketing": {"total": 35000, "used": 18000, "remaining": 17000},
            "Operations": {"total": 75000, "used": 45000, "remaining": 30000},
            "Finance": {"total": 40000, "used": 15000, "remaining": 25000}
        }
        
        budget = department_budgets.get(department, {"total": 0, "used": 0, "remaining": 0})
        
        return {
            "department": department,
            "requested_amount": amount,
            "budget_status": budget,
            "approved": amount <= budget["remaining"],
            "shortfall": max(0, amount - budget["remaining"]),
            "utilization_rate": budget["used"] / budget["total"] if budget["total"] > 0 else 0
        }
    
    @staticmethod
    def optimize_cost(suppliers: List[Dict], quantity: int) -> Dict:
        """Optimize cost across suppliers"""
        if not suppliers:
            return {"error": "No suppliers available"}
        
        # Find best option considering price and rating
        best_option = min(suppliers, key=lambda x: x["price"] / x["rating"])
        total_cost = best_option["price"] * quantity
        
        # Calculate savings compared to most expensive
        most_expensive = max(suppliers, key=lambda x: x["price"])
        savings = (most_expensive["price"] - best_option["price"]) * quantity
        
        return {
            "recommended_supplier": best_option["name"],
            "unit_price": best_option["price"],
            "total_cost": total_cost,
            "quantity": quantity,
            "potential_savings": savings,
            "lead_time": best_option["lead_time"],
            "supplier_rating": best_option["rating"]
        }
    
    @staticmethod
    def check_approval_required(amount: float, department: str) -> Dict:
        """Check approval requirements"""
        approval_matrix = {
            "IT": {"manager": 5000, "director": 15000, "vp": 50000},
            "HR": {"manager": 3000, "director": 10000, "vp": 25000},
            "Marketing": {"manager": 2000, "director": 8000, "vp": 20000},
            "Operations": {"manager": 10000, "director": 25000, "vp": 75000},
            "Finance": {"manager": 7500, "director": 20000, "vp": 60000}
        }
        
        limits = approval_matrix.get(department, {"manager": 1000, "director": 5000, "vp": 15000})
        
        if amount <= limits["manager"]:
            required_approval = "Manager"
            approval_time = "1-2 days"
        elif amount <= limits["director"]:
            required_approval = "Director"
            approval_time = "3-5 days"
        elif amount <= limits["vp"]:
            required_approval = "VP"
            approval_time = "5-7 days"
        else:
            required_approval = "CEO"
            approval_time = "7-14 days"
        
        return {
            "amount": amount,
            "department": department,
            "required_approval": required_approval,
            "approval_limits": limits,
            "estimated_approval_time": approval_time,
            "auto_approved": amount <= limits["manager"]
        }
    
    @staticmethod
    def check_inventory(item: str) -> Dict:
        """Check current inventory"""
        inventory_db = {
            "laptops": {"current": 15, "minimum": 25, "maximum": 100, "on_order": 10},
            "office_chairs": {"current": 45, "minimum": 30, "maximum": 200, "on_order": 0},
            "printers": {"current": 8, "minimum": 15, "maximum": 50, "on_order": 5},
            "monitors": {"current": 22, "minimum": 20, "maximum": 80, "on_order": 0}
        }
        
        inventory = inventory_db.get(item.lower(), {"current": 0, "minimum": 0, "maximum": 0, "on_order": 0})
        
        reorder_needed = inventory["current"] + inventory["on_order"] < inventory["minimum"]
        suggested_quantity = max(0, inventory["minimum"] - inventory["current"] - inventory["on_order"])
        
        return {
            "item": item,
            "current_stock": inventory["current"],
            "minimum_required": inventory["minimum"],
            "maximum_capacity": inventory["maximum"],
            "on_order": inventory["on_order"],
            "reorder_needed": reorder_needed,
            "suggested_order_quantity": suggested_quantity,
            "stock_status": "Low" if reorder_needed else "Adequate",
            "stock_level_percentage": (inventory["current"] / inventory["maximum"]) * 100 if inventory["maximum"] > 0 else 0
        }

# =============================================================================
# PROCUREMENT WORKFLOW
# =============================================================================

class StreamlitProcurementWorkflow:
    """Main procurement workflow for Streamlit"""
    
    def __init__(self):
        self.agents = ProcurementAgents()
    
    def process_request(self, request: Dict) -> Dict:
        """Process complete procurement request"""
        try:
            request_id = f"PRQ-{uuid.uuid4().hex[:8].upper()}"
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: Inventory Check
            status_text.text("🔍 Checking inventory levels...")
            progress_bar.progress(20)
            inventory_check = self.agents.check_inventory(request["item"])
            
            # Step 2: Supplier Analysis
            status_text.text("🏢 Analyzing suppliers...")
            progress_bar.progress(40)
            suppliers = self.agents.find_suppliers(request["item"], request["quantity"])
            
            # Step 3: Cost Optimization
            status_text.text("💰 Optimizing costs...")
            progress_bar.progress(60)
            cost_optimization = self.agents.optimize_cost(suppliers["suppliers"], request["quantity"])
            
            # Step 4: Budget Validation
            status_text.text("📊 Validating budget...")
            progress_bar.progress(80)
            budget_check = self.agents.check_budget_availability(
                request["department"], 
                cost_optimization.get("total_cost", 0)
            )
            
            # Step 5: Approval Check
            status_text.text("✅ Checking approval requirements...")
            progress_bar.progress(100)
            approval_check = self.agents.check_approval_required(
                cost_optimization.get("total_cost", 0),
                request["department"]
            )
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Compile results
            result = {
                "request_id": request_id,
                "timestamp": datetime.now(),
                "request_details": request,
                "inventory_analysis": inventory_check,
                "supplier_analysis": suppliers,
                "cost_optimization": cost_optimization,
                "budget_validation": budget_check,
                "approval_requirements": approval_check,
                "recommendations": self._generate_recommendations(
                    inventory_check, suppliers, cost_optimization, budget_check, approval_check
                ),
                "overall_status": self._determine_status(budget_check, approval_check, inventory_check)
            }
            
            return result
            
        except Exception as e:
            return {"error": f"Processing failed: {str(e)}"}
    
    def _generate_recommendations(self, inventory, suppliers, cost_opt, budget, approval):
        """Generate actionable recommendations"""
        recommendations = []
        
        if inventory.get("reorder_needed"):
            recommendations.append({
                "type": "inventory",
                "priority": "high",
                "message": f"🔴 URGENT: Stock level critical ({inventory['stock_status']})"
            })
        
        if budget.get("approved"):
            recommendations.append({
                "type": "budget",
                "priority": "good",
                "message": "✅ Budget approved - proceed with purchase"
            })
        else:
            recommendations.append({
                "type": "budget",
                "priority": "high",
                "message": f"❌ Budget shortfall: ${budget.get('shortfall', 0):,.2f}"
            })
        
        if cost_opt.get("potential_savings", 0) > 0:
            recommendations.append({
                "type": "cost",
                "priority": "medium",
                "message": f"💡 Save ${cost_opt['potential_savings']:,.2f} with recommended supplier"
            })
        
        recommendations.append({
            "type": "timeline",
            "priority": "info",
            "message": f"⏱️ Lead time: {cost_opt.get('lead_time', 'Unknown')} days"
        })
        
        if approval.get("auto_approved"):
            recommendations.append({
                "type": "approval",
                "priority": "good",
                "message": "🚀 Auto-approved - can proceed immediately"
            })
        else:
            recommendations.append({
                "type": "approval",
                "priority": "medium",
                "message": f"📋 {approval.get('required_approval')} approval needed ({approval.get('estimated_approval_time')})"
            })
        
        return recommendations
    
    def _determine_status(self, budget, approval, inventory):
        """Determine overall request status"""
        if not budget.get("approved"):
            return "rejected"
        elif inventory.get("reorder_needed") and approval.get("auto_approved"):
            return "approved"
        elif not approval.get("auto_approved"):
            return "pending_approval"
        else:
            return "approved"

# =============================================================================
# STREAMLIT APP LAYOUT
# =============================================================================

def main():
    """Main Streamlit application"""
    
    # Header
    st.markdown('<h1 class="main-header">🛒 Procurement Multi-Agent System</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("🤖 Agent Status")
        
        agents_status = [
            ("Inventory Agent", "🟢 Active", "Monitoring stock levels"),
            ("Supplier Agent", "🟢 Active", "Finding best suppliers"),
            ("Budget Agent", "🟢 Active", "Validating budgets"),
            ("Approval Agent", "🟢 Active", "Managing approvals")
        ]
        
        for agent, status, description in agents_status:
            st.markdown(f"""
            <div class="agent-card">
                <strong>{agent}</strong><br>
                {status}<br>
                <small>{description}</small>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Quick stats
        st.subheader("📊 Quick Stats")
        total_requests = len(st.session_state.procurement_history)
        approved_requests = sum(1 for r in st.session_state.procurement_history 
                              if r.get('overall_status') == 'approved')
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Requests", total_requests)
        with col2:
            st.metric("Approved", approved_requests)
        
        if total_requests > 0:
            approval_rate = (approved_requests / total_requests) * 100
            st.metric("Approval Rate", f"{approval_rate:.1f}%")
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📝 New Request", "📊 Dashboard", "📈 Analytics", "🔧 System Demo"])
    
    with tab1:
        show_procurement_form()
    
    with tab2:
        show_dashboard()
    
    with tab3:
        show_analytics()
    
    with tab4:
        show_system_demo()

def show_procurement_form():
    """Show the procurement request form"""
    st.header("📝 Submit Procurement Request")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.form("procurement_form"):
            st.subheader("Request Details")
            
            # Basic request info
            col_a, col_b = st.columns(2)
            with col_a:
                item = st.selectbox(
                    "Item/Product*",
                    ["laptops", "office_chairs", "printers", "monitors"],
                    help="Select the item you want to procure"
                )
                quantity = st.number_input(
                    "Quantity*",
                    min_value=1,
                    max_value=1000,
                    value=10,
                    help="Number of items needed"
                )
            
            with col_b:
                department = st.selectbox(
                    "Department*",
                    ["IT", "HR", "Marketing", "Operations", "Finance"],
                    help="Your department"
                )
                urgency = st.selectbox(
                    "Urgency Level",
                    ["Normal", "Urgent", "Emergency"],
                    help="How urgent is this request?"
                )
            
            justification = st.text_area(
                "Justification*",
                placeholder="Please provide a clear justification for this procurement request...",
                help="Explain why this purchase is necessary"
            )
            
            # Additional options
            st.subheader("Additional Options")
            col_c, col_d = st.columns(2)
            with col_c:
                preferred_supplier = st.selectbox(
                    "Preferred Supplier (Optional)",
                    ["No Preference", "TechCorp", "ElectroSupply", "BusinessTech", "OfficePro", "PrintTech"],
                    help="Choose a preferred supplier if you have one"
                )
            
            with col_d:
                max_budget = st.number_input(
                    "Maximum Budget ($)",
                    min_value=0.0,
                    value=0.0,
                    help="Optional budget limit (0 = no limit)"
                )
            
            submitted = st.form_submit_button("🚀 Process Request", use_container_width=True)
            
            if submitted:
                if not justification.strip():
                    st.error("❌ Justification is required!")
                else:
                    # Process the request
                    request = {
                        "item": item,
                        "quantity": quantity,
                        "department": department,
                        "urgency": urgency,
                        "justification": justification,
                        "preferred_supplier": preferred_supplier if preferred_supplier != "No Preference" else None,
                        "max_budget": max_budget if max_budget > 0 else None
                    }
                    
                    # Process request
                    workflow = StreamlitProcurementWorkflow()
                    
                    with st.spinner("🤖 AI agents are processing your request..."):
                        result = workflow.process_request(request)
                    
                    if "error" in result:
                        st.error(f"❌ {result['error']}")
                    else:
                        # Save to history
                        st.session_state.procurement_history.append(result)
                        st.session_state.current_request = result
                        
                        # Show success message
                        st.success(f"✅ Request processed! ID: {result['request_id']}")
                        
                        # Show results
                        show_request_results(result)
    
    with col2:
        # Show current inventory levels
        st.subheader("📦 Current Inventory")
        
        items = ["laptops", "office_chairs", "printers", "monitors"]
        agents = ProcurementAgents()
        
        for item in items:
            inventory = agents.check_inventory(item)
            
            # Create a mini progress bar for stock level
            stock_pct = inventory['stock_level_percentage']
            
            if stock_pct < 30:
                color = "🔴"
            elif stock_pct < 60:
                color = "🟡"
            else:
                color = "🟢"
            
            st.markdown(f"""
            **{item.title()}** {color}
            - Current: {inventory['current_stock']}
            - Minimum: {inventory['minimum_required']}
            - Status: {inventory['stock_status']}
            """)
            
            # Progress bar
            st.progress(stock_pct / 100)

def show_request_results(result):
    """Display detailed request results"""
    st.markdown("---")
    st.header("📋 Request Analysis Results")
    
    # Overall status
    status = result['overall_status']
    if status == "approved":
        st.success("🎉 Request Approved!")
    elif status == "pending_approval":
        st.warning("⏳ Pending Approval")
    else:
        st.error("❌ Request Rejected")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    cost_opt = result['cost_optimization']
    budget_val = result['budget_validation']
    
    with col1:
        st.metric(
            "Total Cost",
            f"${cost_opt.get('total_cost', 0):,.2f}",
            delta=f"-${cost_opt.get('potential_savings', 0):,.2f}" if cost_opt.get('potential_savings', 0) > 0 else None
        )
    
    with col2:
        st.metric(
            "Lead Time",
            f"{cost_opt.get('lead_time', 0)} days"
        )
    
    with col3:
        st.metric(
            "Budget Remaining",
            f"${budget_val['budget_status']['remaining']:,.2f}",
            delta=f"-${budget_val['requested_amount']:,.2f}"
        )
    
    with col4:
        st.metric(
            "Supplier Rating",
            f"{cost_opt.get('supplier_rating', 0):.1f}/5.0"
        )
    
    # Recommendations
    st.subheader("💡 Recommendations")
    
    for rec in result['recommendations']:
        if rec['priority'] == 'good':
            st.success(rec['message'])
        elif rec['priority'] == 'high':
            st.error(rec['message'])
        elif rec['priority'] == 'medium':
            st.warning(rec['message'])
        else:
            st.info(rec['message'])
    
    # Detailed breakdown in expandable sections
    with st.expander("🏢 Supplier Analysis"):
        suppliers_df = pd.DataFrame(result['supplier_analysis']['suppliers'])
        if not suppliers_df.empty:
            st.dataframe(suppliers_df, use_container_width=True)
        else:
            st.warning("No suitable suppliers found for this request.")
    
    with st.expander("💰 Budget Breakdown"):
        budget_data = budget_val['budget_status']
        
        # Budget pie chart
        fig = go.Figure(data=[go.Pie(
            labels=['Used', 'Requested', 'Remaining'],
            values=[budget_data['used'], budget_val['requested_amount'], 
                   budget_data['remaining'] - budget_val['requested_amount']],
            hole=.3
        )])
        fig.update_layout(title="Budget Allocation")
        st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("📊 Approval Workflow"):
        approval_data = result['approval_requirements']
        
        st.write(f"**Required Approval Level:** {approval_data['required_approval']}")
        st.write(f"**Estimated Time:** {approval_data['estimated_approval_time']}")
        
        # Approval limits chart
        limits = approval_data['approval_limits']
        fig = go.Figure(data=[
            go.Bar(name='Approval Limits', x=list(limits.keys()), y=list(limits.values()))
        ])
        fig.add_hline(y=approval_data['amount'], line_dash="dash", 
                     annotation_text=f"Request Amount: ${approval_data['amount']:,.2f}")
        fig.update_layout(title="Department Approval Limits")
        st.plotly_chart(fig, use_container_width=True)

def show_dashboard():
    """Show procurement dashboard"""
    st.header("📊 Procurement Dashboard")
    
    if not st.session_state.procurement_history:
        st.info("🔍 No procurement requests yet. Submit your first request to see the dashboard!")
        return
    
    # Summary metrics
    history = st.session_state.procurement_history
    total_requests = len(history)
    total_value = sum(r.get('cost_optimization', {}).get('total_cost', 0) for r in history)
    approved_count = sum(1 for r in history if r.get('overall_status') == 'approved')
    pending_count = sum(1 for r in history if r.get('overall_status') == 'pending_approval')
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Requests", total_requests)
    with col2:
        st.metric("Total Value", f"${total_value:,.2f}")
    with col3:
        st.metric("Approved", approved_count, delta=f"{(approved_count/total_requests)*100:.1f}%")
    with col4:
        st.metric("Pending", pending_count)
    
    # Recent requests table
    st.subheader("📝 Recent Requests")
    
    # Create DataFrame from history
    requests_data = []
    for req in history[-10:]:  # Last 10 requests
        requests_data.append({
            "Request ID": req['request_id'],
            "Item": req['request_details']['item'],
            "Quantity": req['request_details']['quantity'],
            "Department": req['request_details']['department'],
            "Total Cost": f"${req.get('cost_optimization', {}).get('total_cost', 0):,.2f}",
            "Status": req['overall_status'].replace('_', ' ').title(),
            "Date": req['timestamp'].strftime("%Y-%m-%d %H:%M")
        })
    
    if requests_data:
        df = pd.DataFrame(requests_data)
        st.dataframe(df, use_container_width=True)
    
    # Department breakdown
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏢 Requests by Department")
        dept_counts = {}
        for req in history:
            dept = req['request_details']['department']
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
        
        if dept_counts:
            fig = px.pie(values=list(dept_counts.values()), names=list(dept_counts.keys()))
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📈 Request Status Distribution")
        status_counts = {}
        for req in history:
            status = req['overall_status'].replace('_', ' ').title()
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if status_counts:
            fig = px.bar(x=list(status_counts.keys()), y=list(status_counts.values()))
            st.plotly_chart(fig, use_container_width=True)

def show_analytics():
    """Show advanced analytics"""
    st.header("📈 Procurement Analytics")
    
    if not st.session_state.procurement_history:
        st.info("📊 No data available yet. Submit procurement requests to see analytics!")
        return
    
    history = st.session_state.procurement_history
    
    # Time series analysis
    st.subheader("📅 Request Volume Over Time")
    
    # Create time series data
    dates = [req['timestamp'].date() for req in history]
    date_counts = pd.Series(dates).value_counts().sort_index()
    
    fig = px.line(x=date_counts.index, y=date_counts.values, title="Daily Request Volume")
    st.plotly_chart(fig, use_container_width=True)
    
    # Cost analysis
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Cost Distribution by Department")
        dept_costs = {}
        for req in history:
            dept = req['request_details']['department']
            cost = req.get('cost_optimization', {}).get('total_cost', 0)
            dept_costs[dept] = dept_costs.get(dept, 0) + cost
        
        if dept_costs:
            fig = px.bar(x=list(dept_costs.keys()), y=list(dept_costs.values()),
                        title="Total Spending by Department")
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🎯 Approval Rate by Amount")
        # Group requests by cost ranges
        cost_ranges = {"<$1K": 0, "$1K-$5K": 0, "$5K-$15K": 0, "$15K+": 0}
        approved_ranges = {"<$1K": 0, "$1K-$5K": 0, "$5K-$15K": 0, "$15K+": 0}
        
        for req in history:
            cost = req.get('cost_optimization', {}).get('total_cost', 0)
            approved = req.get('overall_status') == 'approved'
            
            if cost < 1000:
                cost_ranges["<$1K"] += 1
                if approved: approved_ranges["<$1K"] += 1
            elif cost < 5000:
                cost_ranges["$1K-$5K"] += 1
                if approved: approved_ranges["$1K-$5K"] += 1
            elif cost < 15000:
                cost_ranges["$5K-$15K"] += 1
                if approved: approved_ranges["$5K-$15K"] += 1
            else:
                cost_ranges["$15K+"] += 1
                if approved: approved_ranges["$15K+"] += 1
        
        approval_rates = []
        for range_name in cost_ranges.keys():
            if cost_ranges[range_name] > 0:
                rate = (approved_ranges[range_name] / cost_ranges[range_name]) * 100
            else:
                rate = 0
            approval_rates.append(rate)
        
        fig = px.bar(x=list(cost_ranges.keys()), y=approval_rates,
                    title="Approval Rate by Cost Range (%)")
        st.plotly_chart(fig, use_container_width=True)
    
    # Supplier performance
    st.subheader("🏢 Supplier Performance Analysis")
    
    supplier_data = {}
    for req in history:
        supplier = req.get('cost_optimization', {}).get('recommended_supplier')
        if supplier:
            if supplier not in supplier_data:
                supplier_data[supplier] = {
                    'count': 0, 
                    'total_cost': 0, 
                    'avg_rating': 0, 
                    'total_rating': 0
                }
            
            supplier_data[supplier]['count'] += 1
            supplier_data[supplier]['total_cost'] += req.get('cost_optimization', {}).get('total_cost', 0)
            rating = req.get('cost_optimization', {}).get('supplier_rating', 0)
            supplier_data[supplier]['total_rating'] += rating
            supplier_data[supplier]['avg_rating'] = supplier_data[supplier]['total_rating'] / supplier_data[supplier]['count']
    
    if supplier_data:
        # Create supplier performance DataFrame
        supplier_df = pd.DataFrame.from_dict(supplier_data, orient='index')
        supplier_df['avg_cost'] = supplier_df['total_cost'] / supplier_df['count']
        supplier_df = supplier_df.round(2)
        
        # Display top suppliers
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Most Used Suppliers**")
            top_by_count = supplier_df.nlargest(5, 'count')[['count', 'avg_rating']]
            st.dataframe(top_by_count)
        
        with col2:
            st.write("**Highest Rated Suppliers**")
            top_by_rating = supplier_df.nlargest(5, 'avg_rating')[['avg_rating', 'count']]
            st.dataframe(top_by_rating)
        
        # Supplier scatter plot
        fig = px.scatter(supplier_df, x='avg_cost', y='avg_rating', size='count',
                        title="Supplier Performance: Cost vs Rating",
                        labels={'avg_cost': 'Average Cost per Item ($)', 'avg_rating': 'Average Rating'})
        st.plotly_chart(fig, use_container_width=True)
    
    # Budget utilization
    st.subheader("💳 Budget Utilization Analysis")
    
    # Get latest budget status for each department
    dept_budgets = {}
    for req in history:
        dept = req['request_details']['department']
        budget_info = req.get('budget_validation', {}).get('budget_status', {})
        if budget_info:
            dept_budgets[dept] = budget_info
    
    if dept_budgets:
        budget_df = pd.DataFrame.from_dict(dept_budgets, orient='index')
        budget_df['utilization_rate'] = (budget_df['used'] / budget_df['total']) * 100
        
        # Budget utilization chart
        fig = px.bar(budget_df, x=budget_df.index, y='utilization_rate',
                    title="Budget Utilization by Department (%)",
                    color='utilization_rate',
                    color_continuous_scale='RdYlGn_r')
        fig.add_hline(y=80, line_dash="dash", annotation_text="80% Threshold")
        st.plotly_chart(fig, use_container_width=True)
        
        # Budget breakdown table
        st.write("**Detailed Budget Status**")
        budget_display = budget_df.copy()
        budget_display['total'] = budget_display['total'].apply(lambda x: f"${x:,.2f}")
        budget_display['used'] = budget_display['used'].apply(lambda x: f"${x:,.2f}")
        budget_display['remaining'] = budget_display['remaining'].apply(lambda x: f"${x:,.2f}")
        budget_display['utilization_rate'] = budget_display['utilization_rate'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(budget_display)

def show_system_demo():
    """Show system demonstration and testing"""
    st.header("🔧 System Demonstration")
    
    st.markdown("""
    This section demonstrates the multi-agent system capabilities and allows you to test individual components.
    """)
    
    # Agent testing section
    st.subheader("🤖 Individual Agent Testing")
    
    demo_type = st.selectbox(
        "Select Demo Type",
        ["Supplier Analysis", "Budget Validation", "Inventory Check", "Approval Workflow", "Full Workflow Demo"]
    )
    
    if demo_type == "Supplier Analysis":
        st.markdown("### 🏢 Supplier Agent Demo")
        
        col1, col2 = st.columns(2)
        with col1:
            test_item = st.selectbox("Test Item", ["laptops", "office_chairs", "printers", "monitors"])
            test_quantity = st.number_input("Test Quantity", min_value=1, value=25)
        
        if st.button("🔍 Find Suppliers"):
            agents = ProcurementAgents()
            result = agents.find_suppliers(test_item, test_quantity)
            
            st.json(result)
            
            if result['suppliers']:
                df = pd.DataFrame(result['suppliers'])
                st.dataframe(df, use_container_width=True)
                
                # Supplier comparison chart
                fig = px.scatter(df, x='price', y='rating', size='availability',
                               hover_name='name', title="Supplier Comparison")
                st.plotly_chart(fig, use_container_width=True)
    
    elif demo_type == "Budget Validation":
        st.markdown("### 💰 Budget Agent Demo")
        
        col1, col2 = st.columns(2)
        with col1:
            test_dept = st.selectbox("Test Department", ["IT", "HR", "Marketing", "Operations", "Finance"])
            test_amount = st.number_input("Test Amount ($)", min_value=0.0, value=10000.0)
        
        if st.button("💳 Check Budget"):
            agents = ProcurementAgents()
            result = agents.check_budget_availability(test_dept, test_amount)
            
            # Display result
            if result['approved']:
                st.success("✅ Budget Approved!")
            else:
                st.error(f"❌ Budget Insufficient - Shortfall: ${result['shortfall']:,.2f}")
            
            # Budget visualization
            budget_data = result['budget_status']
            fig = go.Figure(data=[go.Pie(
                labels=['Used', 'Requested', 'Remaining Available'],
                values=[
                    budget_data['used'],
                    min(test_amount, budget_data['remaining']),
                    max(0, budget_data['remaining'] - test_amount)
                ],
                hole=.3
            )])
            fig.update_layout(title=f"{test_dept} Department Budget")
            st.plotly_chart(fig, use_container_width=True)
            
            st.json(result)
    
    elif demo_type == "Inventory Check":
        st.markdown("### 📦 Inventory Agent Demo")
        
        test_item = st.selectbox("Test Item", ["laptops", "office_chairs", "printers", "monitors"])
        
        if st.button("📊 Check Inventory"):
            agents = ProcurementAgents()
            result = agents.check_inventory(test_item)
            
            # Display inventory status
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Current Stock", result['current_stock'])
            with col2:
                st.metric("Minimum Required", result['minimum_required'])
            with col3:
                status_color = "🔴" if result['reorder_needed'] else "🟢"
                st.metric("Status", f"{status_color} {result['stock_status']}")
            
            # Inventory level chart
            categories = ['Current', 'On Order', 'Minimum', 'Maximum']
            values = [
                result['current_stock'],
                result['on_order'],
                result['minimum_required'],
                result['maximum_capacity']
            ]
            
            fig = go.Figure(data=[
                go.Bar(name='Inventory Levels', x=categories, y=values)
            ])
            fig.update_layout(title=f"{test_item.title()} Inventory Status")
            st.plotly_chart(fig, use_container_width=True)
            
            st.json(result)
    
    elif demo_type == "Approval Workflow":
        st.markdown("### ✅ Approval Agent Demo")
        
        col1, col2 = st.columns(2)
        with col1:
            test_dept = st.selectbox("Department", ["IT", "HR", "Marketing", "Operations", "Finance"])
            test_amount = st.number_input("Amount ($)", min_value=0.0, value=7500.0)
        
        if st.button("🔍 Check Approval Requirements"):
            agents = ProcurementAgents()
            result = agents.check_approval_required(test_amount, test_dept)
            
            # Display approval info
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Required Approval", result['required_approval'])
            with col2:
                st.metric("Estimated Time", result['estimated_approval_time'])
            
            if result['auto_approved']:
                st.success("🚀 Auto-approved! Can proceed immediately.")
            else:
                st.warning(f"📋 {result['required_approval']} approval required")
            
            # Approval limits chart
            limits = result['approval_limits']
            fig = go.Figure(data=[
                go.Bar(name='Approval Limits', x=list(limits.keys()), y=list(limits.values()))
            ])
            fig.add_hline(y=test_amount, line_dash="dash", 
                         annotation_text=f"Request Amount: ${test_amount:,.2f}")
            fig.update_layout(title=f"{test_dept} Department Approval Matrix")
            st.plotly_chart(fig, use_container_width=True)
            
            st.json(result)
    
    elif demo_type == "Full Workflow Demo":
        st.markdown("### 🚀 Complete Workflow Demo")
        
        st.info("This will run a complete procurement workflow with sample data.")
        
        if st.button("🎬 Run Full Demo"):
            sample_requests = [
                {"item": "laptops", "quantity": 20, "department": "IT", "justification": "Team expansion"},
                {"item": "office_chairs", "quantity": 50, "department": "HR", "justification": "New office setup"},
                {"item": "printers", "quantity": 5, "department": "Marketing", "justification": "Marketing materials"}
            ]
            
            workflow = StreamlitProcurementWorkflow()
            
            for i, request in enumerate(sample_requests, 1):
                st.markdown(f"#### Demo Request {i}: {request['item'].title()}")
                
                with st.expander(f"Processing {request['item']}..."):
                    result = workflow.process_request(request)
                    
                    if "error" not in result:
                        # Add to history for demo
                        st.session_state.procurement_history.append(result)
                        
                        # Show key results
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Cost", f"${result['cost_optimization']['total_cost']:,.2f}")
                        with col2:
                            st.metric("Status", result['overall_status'].replace('_', ' ').title())
                        with col3:
                            st.metric("Supplier", result['cost_optimization']['recommended_supplier'])
                        
                        # Show recommendations
                        for rec in result['recommendations'][:3]:  # Show top 3
                            if rec['priority'] == 'good':
                                st.success(rec['message'])
                            elif rec['priority'] == 'high':
                                st.error(rec['message'])
                            else:
                                st.info(rec['message'])
                    else:
                        st.error(f"Demo failed: {result['error']}")
            
            st.success("🎉 Full workflow demo completed! Check the Dashboard tab to see results.")
    
    # System architecture explanation
    st.markdown("---")
    st.subheader("🏗️ System Architecture")
    
    st.markdown("""
    ### Multi-Agent Architecture Overview
    
    This procurement system is built using Google's ADK (Agent Development Kit) and MCP (Model Context Protocol) architecture:
    
    **🤖 Specialized Agents:**
    - **Inventory Agent**: Monitors stock levels and forecasts needs
    - **Supplier Agent**: Finds and evaluates suppliers based on multiple criteria
    - **Budget Agent**: Validates budgets and optimizes costs across departments
    - **Approval Agent**: Manages complex approval workflows and routing
    
    **🔧 MCP Servers:**
    - Each agent has its own MCP server providing specialized tools
    - Standardized communication protocol between agents and tools
    - Easy integration with external systems (ERP, inventory management, etc.)
    
    **🚀 Key Benefits:**
    - **Modular Design**: Easy to add new agents or modify existing ones
    - **Fault Tolerance**: System continues working even if components fail
    - **Scalability**: Can handle multiple requests simultaneously
    - **Standardization**: MCP provides universal tool access protocol
    """)
    
    # Performance metrics
    if st.session_state.procurement_history:
        st.subheader("📊 System Performance")
        
        history = st.session_state.procurement_history
        
        # Calculate metrics
        avg_processing_time = "~2-3 seconds"  # Mock metric
        success_rate = len([r for r in history if "error" not in r]) / len(history) * 100
        total_savings = sum(r.get('cost_optimization', {}).get('potential_savings', 0) for r in history)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Avg Processing Time", avg_processing_time)
        with col2:
            st.metric("Success Rate", f"{success_rate:.1f}%")
        with col3:
            st.metric("Total Savings", f"${total_savings:,.2f}")

# =============================================================================
# RUN THE APP
# =============================================================================

if __name__ == "__main__":
    main()

# =============================================================================
# ADDITIONAL UTILITIES FOR STREAMLIT
# =============================================================================

def export_data():
    """Export procurement data to CSV"""
    if st.session_state.procurement_history:
        # Convert history to DataFrame
        export_data = []
        for req in st.session_state.procurement_history:
            export_data.append({
                'Request_ID': req['request_id'],
                'Item': req['request_details']['item'],
                'Quantity': req['request_details']['quantity'],
                'Department': req['request_details']['department'],
                'Total_Cost': req.get('cost_optimization', {}).get('total_cost', 0),
                'Supplier': req.get('cost_optimization', {}).get('recommended_supplier', ''),
                'Status': req['overall_status'],
                'Date': req['timestamp'].isoformat(),
                'Budget_Approved': req.get('budget_validation', {}).get('approved', False),
                'Approval_Required': req.get('approval_requirements', {}).get('required_approval', ''),
                'Lead_Time': req.get('cost_optimization', {}).get('lead_time', 0)
            })
        
        df = pd.DataFrame(export_data)
        return df.to_csv(index=False)
    return None

def reset_system():
    """Reset system data"""
    st.session_state.procurement_history = []
    st.session_state.current_request = None
    st.success("🔄 System data reset successfully!")

# Add sidebar options for data management
with st.sidebar:
    st.markdown("---")
    st.subheader("⚙️ System Management")
    
    if st.button("📤 Export Data"):
        csv_data = export_data()
        if csv_data:
            st.download_button(
                label="💾 Download CSV",
                data=csv_data,
                file_name=f"procurement_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("No data to export")
    
    if st.button("🔄 Reset System"):
        reset_system()
    
    st.markdown("---")
    st.markdown("**💡 Tips:**")
    st.markdown("- Submit requests to see analytics")
    st.markdown("- Use the demo tab to test features")
    st.markdown("- Check dashboard for insights")
    st.markdown("- Export data for external analysis")