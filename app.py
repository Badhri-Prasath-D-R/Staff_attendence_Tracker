import streamlit as st
import fitz
import pandas as pd
from datetime import datetime, timedelta
import re
import hashlib
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import io

st.set_page_config(page_title="Attendance Tracker", page_icon="📅", layout="wide")

# ===== YOUR ORIGINAL CSS =====
st.markdown("""
<style>
[data-testid="stMetricValue"] { color: #1f77b4 !important; font-weight: bold; }
[data-testid="stMetricLabel"] { color: #31333F !important; font-size: 1.1rem !important; }
.stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
</style>
""", unsafe_allow_html=True)

# ---------- NAVBAR ----------
page = st.radio("Navigation",
                ["📊 Attendance Dashboard", "📄 CoE Monthly Summary"],
                horizontal=True)

# ---------- HELPERS ----------
def format_td(td):
    total_sec = int(td.total_seconds())
    if total_sec <= 0:
        return "00:00"
    return f"{total_sec // 3600:02d}:{(total_sec % 3600) // 60:02d}"

def dataframe_to_pdf(df):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    data = [df.columns.tolist()] + df.values.tolist()
    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.grey),
        ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke),
        ("GRID",(0,0),(-1,-1),1,colors.black)
    ]))
    doc.build([table])
    buffer.seek(0)
    return buffer

# ---------- PROCESS PDF ----------
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
        if "Employee Name" in line:
            emp_info['Name'] = line.split(":")[-1].strip()
        if "Employee Code" in line:
            emp_info['Code'] = line.split(":")[-1].strip()

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
            if not day_match:
                continue

            day_str = day_match.group(1)
            is_absent = "AB" in context[:50]
            in_time, out_time = "-", "-"
            work_td, extra_td = timedelta(0), timedelta(0)

            time_match = re.search(r'(\d{2}:\d{2})\s+(\d{2}:\d{2})', context)

            if time_match and not is_absent:
                t1, t2 = [datetime.strptime(t, '%H:%M') for t in time_match.groups()]
                in_t, out_t = (t1, t2) if t1 < t2 else (t2, t1)
                in_time, out_time = in_t.strftime('%H:%M'), out_t.strftime('%H:%M')
                work_td = out_t - in_t
                std = STD_SATURDAY if day_str == "Sat" else current_std_weekday
                if work_td > std:
                    extra_td = work_td - std
                    total_extra_sec += extra_td.total_seconds()

            if is_absent:
                absent_count += 1

            processed_data.append({
                "Date": date_str,
                "Day": day_str,
                "In": in_time,
                "Out": out_time,
                "Work": format_td(work_td),
                "Extra": format_td(extra_td),
                "Status": "Absent" if is_absent else ("Present" if in_time != "-" else "Off/Holiday")
            })

    earned_days = int(total_extra_sec // current_std_weekday.total_seconds())
    df = pd.DataFrame(processed_data).drop_duplicates(subset=['Date'])
    return emp_info, df, total_extra_sec, absent_count, earned_days

def generate_coe_summary(emp_info, total_extra_sec, absent_count):
    return pd.DataFrame([{
        "CoE Faculty Name": f"{emp_info.get('Name')} - {emp_info.get('Code')}",
        "Extra working hours": format_td(timedelta(seconds=total_extra_sec)),
        "Work Nature": "CoE Work",
        "Remarks": f"{absent_count} Absent Days"
    }])

# ---------- SIDEBAR ----------
gender_input = st.sidebar.selectbox("Select Gender", ["Male", "Female"])
uploaded_file = st.sidebar.file_uploader("Upload PDF", type="pdf")

# ================= PAGE 1 =================
if page == "📊 Attendance Dashboard":
    st.title("📊 Attendance Dashboard")

    if uploaded_file:
        info, df, extra_sec, absents, earned_days = process_pdf(uploaded_file, gender_input)

        st.subheader(f"Employee: {info.get('Name')} ({info.get('Code')})")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Extra Time", format_td(timedelta(seconds=extra_sec)))
        col2.metric("Earned Leave Days", f"{earned_days} Days")
        col3.metric("Absents", absents)

        st.divider()
        st.dataframe(df, use_container_width=True, hide_index=True)

# ================= PAGE 2 =================
if page == "📄 CoE Monthly Summary":
    st.title("📄 CoE Monthly Summary")

    if uploaded_file:
        file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()

        if "last_file_hash" not in st.session_state:
            st.session_state.last_file_hash = None

        if st.session_state.last_file_hash != file_hash:
            info, df, extra_sec, absents, earned_days = process_pdf(uploaded_file, gender_input)
            st.session_state.summary_df = generate_coe_summary(info, extra_sec, absents)
            st.session_state.last_file_hash = file_hash

        st.dataframe(st.session_state.summary_df, use_container_width=True)

        if len(st.session_state.summary_df) > 0:
            row_index = st.number_input("Row index to delete",0,len(st.session_state.summary_df)-1,0)

            col1, col2 = st.columns(2)

            if col1.button("🗑 Delete Row"):
                st.session_state.summary_df = st.session_state.summary_df.drop(index=row_index).reset_index(drop=True)
                st.success("Row deleted!")

            pdf_buffer = dataframe_to_pdf(st.session_state.summary_df)
            col2.download_button("📥 Export as PDF", pdf_buffer, "CoE_Summary.pdf", "application/pdf")
