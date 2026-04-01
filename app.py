import streamlit as st
import pandas as pd
import re
from datetime import timedelta

st.set_page_config(page_title="Syrow Ticket Dashboard", layout="wide")

st.title("📋 Syrow Ticket Management Dashboard")

# Load Data
@st.cache_data
def load_data():
    df = pd.read_csv('Caliper Reports - Combined Report  Syrow Portal (63).csv')
    
    # Filter for Working status
    df = df[df['Status'].str.strip().str.lower() == 'working'].copy()
    
    # Priority Mapping
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)
    
    # Extract Assigned To
    def extract_name(note):
        if pd.isna(note): return "-"
        match = re.search(r'(?:assigned to|allocated to)\s+([A-Za-z]+)', str(note), re.IGNORECASE)
        return match.group(1).title() if match else "-"
    df['Assigned To'] = df['Notes'].apply(extract_name)
    
    # SLA Calculation
    df['Created On'] = pd.to_datetime(df['Created On'])
    def calc_sla(row):
        c, p = row['Created On'], row['Priority']
        days = {'P1': 0.16, 'P2': 0.33, 'P3': 2, 'P4': 4} # 0.16 is ~4hrs
        return c + timedelta(days=days.get(p, 0))
    
    df['Expected Completion'] = df.apply(calc_sla, axis=1)
    return df[['Ticket SR#', 'KAM', 'Company', 'Priority', 'Ticket Title', 'Assigned To', 'Expected Completion']]

data = load_data()

# Sidebar Filters
st.sidebar.header("Filters")
kam_filter = st.sidebar.multiselect("Select KAM", options=data['KAM'].unique(), default=data['KAM'].unique())
priority_filter = st.sidebar.multiselect("Select Priority", options=['P1','P2','P3','P4'], default=['P1','P2','P3','P4'])

# Apply Filters
filtered_data = data[(data['KAM'].isin(kam_filter)) & (data['Priority'].isin(priority_filter))]

# Display Dashboard
st.dataframe(filtered_data, use_container_width=True)

# Export Button
st.download_button("Download as CSV", filtered_data.to_csv(index=False), "dashboard.csv", "text/csv")
