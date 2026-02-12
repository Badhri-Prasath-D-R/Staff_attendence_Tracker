import streamlit as st
import fitz
import pandas as pd
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Attendance Tracker", page_icon="📅", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { color: #1f77b4 !important; font-weight: bold; }
    [data-testid="stMetricLabel"] { color: #31333F !important; font-size: 1.1rem !important; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

def format_td(td):
    total_sec = int(td.total_seconds())
    if total_sec <= 0: return "00:00"
    return f"{total_sec // 3600:02d}:{(total_sec % 3600) // 60:02d}"

def process_pdf(uploaded_file, gender):
    STD_WEEKDAY_MALE = timedelta(hours=9, minutes=10)
    STD_WEEKDAY_FEMALE = timedelta(hours=8, minutes=25)
    STD_SATURDAY = timedelta(hours=7, minutes=10)
    
    current_std_weekday = STD_WEEKDAY_MALE if gender == "Male" else STD_WEEKDAY_FEMALE
    
    pdf_stream = uploaded_file.read()
    doc = fitz.open(stream=pdf_stream, filetype="pdf")
    text = "".join([page.get_text() for page in doc])
    doc.close()

    emp_info = {}
    for line in text.split('\n'):
        if "Employee Name" in line: emp_info['Name'] = line.split(":")[-1].strip()
        if "Employee Code" in line: emp_info['Code'] = line.split(":")[-1].strip()

    processed_data = []
    total_extra_sec = 0
    absent_count = 0
    lines = text.split('\n')

    for i, line in enumerate(lines):
        date_match = re.search(r'(\d{2}/\d{2}/2025)', line)
        if date_match:
            date_str = date_match.group(1)
            context = " ".join(lines[i:i+10]) 
            day_match = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)', context)
            if not day_match: continue
            
            day_str = day_match.group(1)
            is_absent = "AB" in context[:50]
            in_time, out_time = "-", "-"
            work_td, extra_td = timedelta(0), timedelta(0)
            time_match = re.search(r'(\d{2}:\d{2})\s+(\d{2}:\d{2})', context)
            
            if time_match and not is_absent:
                t1_str, t2_str = time_match.groups()
                t1 = datetime.strptime(t1_str, '%H:%M')
                t2 = datetime.strptime(t2_str, '%H:%M')
                in_t, out_t = (t1, t2) if t1 < t2 else (t2, t1)
                in_time, out_time = in_t.strftime('%H:%M'), out_t.strftime('%H:%M')
                work_td = out_t - in_t
                
                std = STD_SATURDAY if day_str == "Sat" else current_std_weekday
                if work_td > std:
                    extra_td = work_td - std
                    total_extra_sec += extra_td.total_seconds()

            if is_absent: absent_count += 1
            processed_data.append({
                "Date": date_str, "Day": day_str, "In": in_time, "Out": out_time,
                "Work": format_td(work_td), "Extra": format_td(extra_td),
                "Status": "Absent" if is_absent else ("Present" if in_time != "-" else "Off/Holiday")
            })

    divisor_seconds = current_std_weekday.total_seconds()
    earned_days = int(total_extra_sec // divisor_seconds)
    
    df = pd.DataFrame(processed_data).drop_duplicates(subset=['Date'])
    return emp_info, df, total_extra_sec, absent_count, earned_days

st.title("📅 Attendance & Earned Leave Tracker")
gender_input = st.sidebar.selectbox("Select Gender", ["Male", "Female"])
uploaded_file = st.sidebar.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    info, df, extra_sec, absents, earned_days = process_pdf(uploaded_file, gender_input)
    
    st.subheader(f"Employee: {info.get('Name', 'N/A')} ({info.get('Code', 'N/A')})")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Extra Time", format_td(timedelta(seconds=extra_sec)))
    col2.metric("Earned Leave Days", f"{earned_days} Days")
    col3.metric("Absents", absents)
    
    st.divider()
    st.dataframe(df, width="stretch", hide_index=True)