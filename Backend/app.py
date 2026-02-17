import streamlit as st
import fitz
import pandas as pd
from datetime import datetime, timedelta
import re
from pymongo import MongoClient
from bson.objectid import ObjectId
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import certifi

# --- CONFIGURATION ---
st.set_page_config(page_title="Attendance Tracker Pro", page_icon="📅", layout="wide")

# --- DATABASE CONNECTION (Cached with SSL Fix) ---
@st.cache_resource
def get_mongodb_connection():
    uri = "mongodb+srv://badhriprasathdr_db_user:H2Jm044LSmpRNfP0@cluster0.ko8iccx.mongodb.net/?appName=Cluster0"
    # tlsCAFile=certifi.where() solves the SSL handshake/cryptography errors
    client = MongoClient(uri, tlsCAFile=certifi.where())
    return client

client = get_mongodb_connection()
db = client.AttendanceDB
collection = db.employee_records

# --- PROFESSIONAL UI STYLING ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { color: #004085 !important; font-weight: bold !important; }
    [data-testid="stMetricLabel"] { color: #333333 !important; }
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #dee2e6;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    div.row-widget.stRadio > div {
        flex-direction: row;
        justify-content: center;
        background: #e9ecef;
        padding: 10px;
        border-radius: 50px;
        margin-bottom: 20px;
    }
    .stButton button { border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
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
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
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
    # Updated Logic: 20-minute tolerance (1200 seconds) for earned leave calculation
    earned_days = int((total_extra_sec + 1200) // divisor_seconds)
    
    df = pd.DataFrame(processed_data).drop_duplicates(subset=['Date'])
    return emp_info, df, total_extra_sec, absent_count, earned_days

# --- PERSISTENT SIDEBAR ---
with st.sidebar:
    st.header("🎛️ App Controls")
    gender_input = st.selectbox("Employee Gender", ["Male", "Female"])
    uploaded_file = st.file_uploader("Upload Attendance PDF", type="pdf")
    st.divider()

# --- MAIN PAGE NAVIGATION ---
st.title("📅 Attendance Analytics Dashboard")
choice = st.radio("Navigation", ["📊 Calculator", "📂 Records History"], horizontal=True)

# --- CALCULATOR VIEW ---
if choice == "📊 Calculator":
    if uploaded_file:
        info, df, extra_sec, absents, earned_days = process_pdf(uploaded_file, gender_input)
        
        st.markdown(f"### 👤 Profile: **{info.get('Name', 'N/A')}** (`{info.get('Code', 'N/A')}`)")
        
        m1, m2, m3 = st.columns(3)
        extra_time_str = format_td(timedelta(seconds=extra_sec))
        m1.metric("Total Extra Time", extra_time_str)
        m2.metric("Earned Leave", f"{earned_days} Days")
        m3.metric("Absents", absents)
        
        if st.button("💾 Save Record to Database", use_container_width=True):
            record = {
                "name": info.get('Name', 'N/A'),
                "code": info.get('Code', 'N/A'),
                "extra_time": extra_time_str,
                "earned_days": earned_days,
                "absents": absents,
                "save_date": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            collection.insert_one(record)
            st.success("✅ Record Successfully Saved!")

        st.divider()
        with st.expander("🔍 View Detailed Daily Breakdown Table", expanded=False):
            st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.warning("👈 Please upload a PDF file from the sidebar to begin.")

# --- HISTORY VIEW ---
else:
    st.header("📂 Saved Database Records")
    # Wrap in try/except to catch any remaining connection issues immediately
    try:
        data = list(collection.find())
    except Exception as e:
        st.error(f"Database connection error: {e}")
        data = []

    if data:
        c1, c2, _ = st.columns([1, 1, 1])
        with c1:
            if st.button("📄 Export Professional PDF", use_container_width=True):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Helvetica", 'B', 14)
                pdf.cell(0, 10, "CoE - Monthly Biometric Summary", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(5)
                
                pdf.set_font("Helvetica", 'B', 10)
                # Layout based on the user's reference image
                w = [80, 40, 40, 30] 
                cols = ["CoE Faculty Name", "Extra working hours", "Work Nature", "Remarks"]
                
                for i, col in enumerate(cols):
                    nxt_x = XPos.LMARGIN if i == len(cols)-1 else XPos.RIGHT
                    nxt_y = YPos.NEXT if i == len(cols)-1 else YPos.TOP
                    pdf.cell(w[i], 10, col, border=1, align='C', new_x=nxt_x, new_y=nxt_y)
                
                pdf.set_font("Helvetica", '', 9)
                for item in data:
                    faculty_display = f"{item.get('name', 'N/A')} - {item.get('code', 'N/A')}"
                    pdf.cell(w[0], 10, faculty_display, border=1, align='L', new_x=XPos.RIGHT, new_y=YPos.TOP)
                    pdf.cell(w[1], 10, str(item.get('extra_time', '00:00')), border=1, align='C', new_x=XPos.RIGHT, new_y=YPos.TOP)
                    pdf.cell(w[2], 10, "CoE Work", border=1, align='C', new_x=XPos.RIGHT, new_y=YPos.TOP)
                    
                    e_days = item.get('earned_days', 0)
                    remarks = str(e_days) if str(e_days) != '0' else "-"
                    pdf.cell(w[3], 10, remarks, border=1, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                
                st.download_button("📥 Click to Download PDF", data=bytes(pdf.output()), file_name="CoE_Report.pdf", mime="application/pdf")
        
        with c2:
             if st.button("🔥 Wipe All Data", use_container_width=True):
                collection.delete_many({})
                st.rerun()

        st.divider()

        for item in data:
            with st.container():
                r1, r2 = st.columns([0.92, 0.08])
                with r1:
                    name = item.get('name', 'N/A')
                    code = item.get('code', 'N/A')
                    extra = item.get('extra_time', '00:00')
                    leave = item.get('earned_days', 0)
                    absent = item.get('absents', 0)
                    date = item.get('save_date', 'Unknown')
                    st.markdown(f"**{name}** ({code})  \n`Extra: {extra}` | `Leave: {leave}d` | `Absents: {absent}` | _Saved: {date}_")
                with r2:
                    if st.button("🗑️", key=str(item['_id'])):
                        collection.delete_one({"_id": item['_id']})
                        st.rerun()
                st.markdown("---")
    else:
        st.info("No records found.")