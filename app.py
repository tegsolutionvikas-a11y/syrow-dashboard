import streamlit as st
import pandas as pd
import re
from datetime import timedelta

# Page Setup
st.set_page_config(page_title="Syrow Live Dashboard", layout="wide")

st.title("📊 Syrow Ticket Management Dashboard")
st.markdown("---")

# 1. File Upload Section (Directly on screen)
uploaded_file = st.file_uploader("Step 1: Upload your Syrow CSV dump here", type=["csv"])

def extract_assigned_to(row):
    note = str(row['Notes']) if pd.notna(row['Notes']) else ""
    category = str(row['Ticket Category']).lower() if pd.notna(row['Ticket Category']) else ""
    
    # First: Try to find a name after "assigned to"
    match = re.search(r'(?:assigned to|allocated to)\s+([A-Za-z]+)', note, re.IGNORECASE)
    if match:
        return match.group(1).title()
    
    # Second: If no name found and it's a Tech Issue, assign to Tech Team
    if "tech issue" in category:
        return "Tech Team"
    
    return "-"

@st.cache_data
def process_syrow_data(file):
    # Read CSV
    df = pd.read_csv(file)
    
    # Filter for "Working" status only
    df = df[df['Status'].str.strip().str.lower() == 'working'].copy()
    
    # Map Severity to Priority
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)
    
    # Apply Assignment Logic
    df['Assigned To'] = df.apply(extract_assigned_to, axis=1)
    
    # Calculate Expected Completion (SLA)
    df['Created On'] = pd.to_datetime(df['Created On'])
    def calc_sla(row):
        created, p = row['Created On'], row['Priority']
        # Rules: P1=4h, P2=8h, P3=2d, P4=4d
        sla_hours = {'P1': 4, 'P2': 8, 'P3': 48, 'P4': 96}
        return created + timedelta(hours=sla_hours.get(p, 0))
    
    df['Expected Completion'] = df.apply(calc_sla, axis=1)
    
    # Final Table Selection
    result = df[[
        'Ticket SR#', 
        'KAM', 
        'Company', 
        'Priority', 
        'Ticket Title', 
        'Assigned To', 
        'Expected Completion'
    ]].copy()
    
    # Rename for Dashboard
    result.columns = [
        'Ticket No', 'KAM Name', 'Company Name', 
        'Priority', 'Issue Statement', 'Assigned To', 'Expected Completion'
    ]
    return result

# 2. Dashboard Logic
if uploaded_file is not None:
    try:
        data = process_syrow_data(uploaded_file)
        
        # Dashboard KPIs (Total counts)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Working Tickets", len(data))
        col2.metric("Critical (P1/P2)", len(data[data['Priority'].isin(['P1','P2'])]))
        col3.metric("Tech Team Tickets", len(data[data['Assigned To'] == "Tech Team"]))

        # Filters
        st.sidebar.header("Filters")
        kam_list = sorted(data['KAM Name'].unique().tolist())
        selected_kam = st.sidebar.multiselect("Filter by KAM", kam_list, default=kam_list)
        
        # Display Table
        filtered_df = data[data['KAM Name'].isin(selected_kam)]
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
        # Download Button
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Filtered Report", csv, "syrow_report.csv", "text/csv")

    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.info("Waiting for file upload... Please drag and drop the Syrow CSV file above.")
