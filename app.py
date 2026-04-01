import streamlit as st
import pandas as pd
import re
from datetime import timedelta

# Page Configuration
st.set_page_config(page_title="Syrow Live Dashboard", layout="wide")

st.title("📊 Syrow Ticket Management Dashboard")
st.markdown("---")

# 1. Direct Upload on Dashboard Screen
uploaded_file = st.file_uploader("Upload your Syrow CSV file to generate the dashboard", type=["csv"])

def extract_assigned_person(row):
    note = str(row['Notes']) if pd.notna(row['Notes']) else ""
    category = str(row['Ticket Category']).lower() if pd.notna(row['Ticket Category']) else ""
    
    # Expanded regex to catch "assigned to", "escalated to", "allocated to", "moved to", etc.
    # It captures the first proper name (word starting with a capital or just the next word)
    patterns = [
        r'assigned to\s+([A-Za-z]+)',
        r'escalated to\s+([A-Za-z]+)',
        r'allocated to\s+([A-Za-z]+)',
        r'moved to\s+([A-Za-z]+)',
        r'forwarded to\s+([A-Za-z]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, note, re.IGNORECASE)
        if match:
            return match.group(1).title()
    
    # Fallback for Tech Issues if no name is mentioned
    if "tech issue" in category or "technical" in category:
        return "Tech Team"
    
    return "-"

@st.cache_data
def process_data(file):
    df = pd.read_csv(file)
    
    # Filter for "Working" status
    df = df[df['Status'].str.strip().str.lower() == 'working'].copy()
    
    # Map Severity (1,2,3,4 -> P1,P2,P3,P4)
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)
    
    # Extract Assigned To name using the new flexible logic
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)
    
    # SLA Calculation logic
    df['Created On'] = pd.to_datetime(df['Created On'])
    def get_sla_limit(row):
        c, p = row['Created On'], row['Priority']
        sla_hours = {'P1': 4, 'P2': 8, 'P3': 48, 'P4': 96}
        return c + timedelta(hours=sla_hours.get(p, 0))
    
    df['Expected Completion'] = df.apply(get_sla_limit, axis=1)
    
    # Select and Rename Columns
    dashboard_df = df[[
        'Ticket SR#', 'KAM', 'Company', 'Priority', 
        'Ticket Title', 'Assigned To', 'Expected Completion'
    ]].copy()
    
    dashboard_df.columns = [
        'Ticket No', 'KAM Name', 'Company Name', 
        'Priority', 'Issue Statement', 'Assigned To', 'Expected Completion'
    ]
    return dashboard_df

# 2. Display Logic
if uploaded_file:
    try:
        data = process_data(uploaded_file)
        
        # Dashboard Summary Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Active Working Tickets", len(data))
        m2.metric("Tech Team Workload", len(data[data['Assigned To'] == "Tech Team"]))
        m3.metric("P1/P2 Critical", len(data[data['Priority'].isin(['P1', 'P2'])]))
        
        st.markdown("### Ticket Details")
        
        # KAM Filter in Sidebar
        kams = sorted(data['KAM Name'].unique().tolist())
        selected_kams = st.sidebar.multiselect("Filter by KAM", kams, default=kams)
        
        # Display Final Table
        final_view = data[data['KAM Name'].isin(selected_kams)]
        st.dataframe(final_view, use_container_width=True, hide_index=True)
        
        # Download link
        st.download_button(
            label="Download Dashboard as CSV",
            data=final_view.to_csv(index=False),
            file_name="syrow_dashboard_export.csv",
            mime="text/csv"
        )
        
    except Exception as e:
        st.error(f"Error parsing file: {e}. Please ensure the CSV format matches the Syrow export.")
else:
    st.info("👋 Welcome! Please upload your Syrow CSV file above to view the live dashboard.")
