import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

# Set page configuration
st.set_page_config(page_title="Syrow Ticket Dashboard", layout="wide")
st.title("📋 Syrow Ticket Dashboard")

uploaded_file = st.file_uploader("Upload Syrow CSV File", type=["csv"])

def extract_assigned_person(row):
    """
    Identifies the handler from Notes, Category, or Title.
    """
    note = str(row['Notes']) if pd.notna(row['Notes']) else ""
    category = str(row['Ticket Category']).lower() if pd.notna(row['Ticket Category']) else ""
    title = str(row['Ticket Title']).lower() if pd.notna(row['Ticket Title']) else ""
    
    # Check for Deva
    if re.search(r'\b(Devagiri|Deva)\b', note, re.IGNORECASE):
        return "Devagiri"

    # Search for "Assigned to/Escalated to [Name]" or "[Name] working"
    action_patterns = [
        r'(?:assigned to|escalated to|allocated to|moved to|forwarded to|to)\s+([A-Z][a-z]+)',
        r'([A-Z][a-z]+)\s+is\s+working',
        r'([A-Z][a-z]+)\s+working'
    ]
    
    for pattern in action_patterns:
        match = re.search(pattern, note) # Case sensitive for names usually works better
        if match:
            name = match.group(1)
            if name.lower() not in ['tech', 'still', 'currently', 'team', 'the', 'is', 'hi', 'dear']:
                return name

    # Fallback to Tech Team if keywords found
    tech_keywords = ['tech', 'developer', 'dev ', 'development', 'backend', 'software']
    combined_text = (note + " " + category + " " + title).lower()
    if any(kw in combined_text for kw in tech_keywords):
        return "Tech Team"
    
    return "-"

@st.cache_data
def process_dashboard_data(file):
    # Load and clean headers
    df = pd.read_csv(file)
    df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    
    # Filter for 'Working' status to represent the active queue
    df = df[df['Status'].astype(str).str.strip().str.lower() == 'working'].copy()
    
    if df.empty:
        return pd.DataFrame()

    # 1. Map Severity to Priority (P1, P2, P3, P4)
    df['Severity'] = pd.to_numeric(df['Severity'], errors='coerce').fillna(4).astype(int)
    priority_map = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4'}
    df['Priority'] = df['Severity'].map(priority_map)

    # 2. Extract Assigned To
    df['Assigned To'] = df.apply(extract_assigned_person, axis=1)

    # 3. Parse Created On
    # Handles timestamps like 2026-05-08 14:58:14 or 08-05-2026
    df['Created On'] = pd.to_datetime(df['Created On'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Created On'])

    # 4. Calculate Active Days
    # Note: Using .days provides the integer difference
    today = pd.Timestamp.now()
    df['Active Days'] = (today - df['Created On']).dt.days

    # 5. Calculate Expected Completion based on strict Severity rules:
    # 1 -> 4 hrs, 2 -> 8 hrs, 3 -> 48 hrs, 4 -> 4 days (96 hrs)
    def calculate_sla(row):
        severity = row['Severity']
        created = row['Created On']
        if severity == 1:
            return created + timedelta(hours=4)
        elif severity == 2:
            return created + timedelta(hours=8)
        elif severity == 3:
            return created + timedelta(hours=48)
        else: # Severity 4
            return created + timedelta(days=4)

    df['Expected Completion'] = df.apply(calculate_sla, axis=1)
    
    # Format the completion date for display
    df['Expected Completion Display'] = df['Expected Completion'].dt.strftime('%-m/%-d/%Y %H:%M')

    # 6. Select and Rename Columns
    result = df[[
        'Ticket SR#', 'KAM', 'Company', 'Priority', 
        'Ticket Title', 'Assigned To', 'Active Days', 'Expected Completion Display'
    ]].copy()

    result.columns = [
        'Ticket No', 'KAM Name', 'Company Name', 'Priority', 
        'Issue Statement', 'Assigned To', 'Active Days', 'Expected Completion'
    ]
    
    return result

if uploaded_file:
    try:
        final_df = process_dashboard_data(uploaded_file)
        
        if final_df.empty:
            st.warning("No tickets with 'Working' status found.")
        else:
            # Display Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Working", len(final_df))
            c2.metric("Critical (P1/P2)", len(final_df[final_df['Priority'].isin(['P1', 'P2'])]))
            c3.metric("Oldest Ticket (Days)", final_df['Active Days'].max())

            # Display Table
            st.subheader("Ticket Management Table")
            st.dataframe(
                final_df.sort_values('Active Days', ascending=False),
                use_container_width=True,
                hide_index=True
            )

            # Download Option
            csv = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Dashboard CSV", csv, "syrow_dashboard.csv", "text/csv")

    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.info("Please upload the Caliper Report CSV to view the dashboard.")
