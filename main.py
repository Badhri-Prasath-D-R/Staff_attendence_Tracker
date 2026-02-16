import fitz
import pandas as pd
from datetime import datetime, timedelta
import re

PDF_PATH = "pdffile.pdf"
GENDER = "Male"

STD_WEEKDAY_MALE = timedelta(hours=9, minutes=10)
STD_WEEKDAY_FEMALE = timedelta(hours=8, minutes=25)
STD_SATURDAY = timedelta(hours=7, minutes=10)


# ---------- HELPER ----------
def format_td(td):
    total_sec = int(td.total_seconds())
    if total_sec <= 0:
        return "00:00"
    return f"{total_sec // 3600:02d}:{(total_sec % 3600) // 60:02d}"


# ---------- PROCESS ATTENDANCE ----------
def process_attendance():
    try:
        doc = fitz.open(PDF_PATH)
        text = "".join([page.get_text() for page in doc])
        doc.close()

        emp_info = {}
        for line in text.split('\n'):
            if "Employee Name" in line: emp_info['Name'] = line.split(":")[-1].strip()
            if "Employee Code" in line: emp_info['Code'] = line.split(":")[-1].strip()
            if "Department" in line: emp_info['Dept'] = line.split(":")[-1].strip()

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
                    t1_str, t2_str = time_match.groups()
                    t1 = datetime.strptime(t1_str, '%H:%M')
                    t2 = datetime.strptime(t2_str, '%H:%M')

                    in_t, out_t = (t1, t2) if t1 < t2 else (t2, t1)
                    in_time, out_time = in_t.strftime('%H:%M'), out_t.strftime('%H:%M')
                    work_td = out_t - in_t

                    std = STD_SATURDAY if day_str == "Sat" else (
                        STD_WEEKDAY_MALE if GENDER == "Male" else STD_WEEKDAY_FEMALE
                    )

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

        # ---------- DAILY TABLE ----------
        df = pd.DataFrame(processed_data).drop_duplicates(subset=['Date'])

        # ---------- COE SUMMARY TABLE ----------
        extra_hours = format_td(timedelta(seconds=total_extra_sec))
        coe_summary_df = pd.DataFrame([{
            "CoE Faculty Name": f"{emp_info.get('Name','N/A')} - {emp_info.get('Code','')}",
            "Extra working hours": extra_hours,
            "Work Nature": "CoE Work",
            "Remarks": "-"
        }])

        # ---------- PRINT REPORT ----------
        print(f"\n{'='*70}")
        print("EMPLOYEE DETAILS")
        print(f"{'='*70}")
        print(f"Name : {emp_info.get('Name')}")
        print(f"Code : {emp_info.get('Code')}")
        print(f"Dept : {emp_info.get('Dept')}")

        print(f"\n{'='*70}")
        print("DAILY ATTENDANCE")
        print(f"{'='*70}")
        print(df.to_string(index=False))

        print(f"\n{'='*70}")
        print("MONTHLY SUMMARY")
        print(f"{'='*70}")
        print(f"Total Extra Hours : {extra_hours}")
        print(f"Total Absents     : {absent_count}")

        print(f"\n{'='*70}")
        print("CoE MONTHLY SUMMARY TABLE")
        print(f"{'='*70}")
        print(coe_summary_df.to_string(index=False))

    except Exception as e:
        print(f"Error: {e}")


# ---------- RUN ----------
if __name__ == "__main__":
    process_attendance()
