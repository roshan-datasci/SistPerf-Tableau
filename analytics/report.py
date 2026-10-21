"""Excel and PDF progress reports built from the dashboard tables."""
import io
import pandas as pd

def _t(s):
    s = str(s).replace("→", "->").replace("·", "-").replace("–", "-")
    return s.encode("latin-1", "replace").decode("latin-1")

def make_excel(sub, sgpa, cgpa, arrears, risk, att, student):
    buf = io.BytesIO()
    cols = ["Semester", "Subject_Code", "Subject", "CAE 1", "CAE 2", "Internal", "Exam", "Final %", "Grade", "Alert"]
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"Item": ["Student", "CGPA", "Arrears (RA)"], "Value": [student, None if pd.isna(cgpa) else round(cgpa, 2), arrears]}).to_excel(xw, sheet_name="Summary", index=False)
        sub[[c for c in cols if c in sub]].round(1).to_excel(xw, sheet_name="Subjects", index=False)
        sgpa.round(2).to_excel(xw, sheet_name="SGPA", index=False)
        if risk is not None and len(risk):
            risk.to_excel(xw, sheet_name="Arrear risk", index=False)
        if att is not None and len(att):
            att.to_excel(xw, sheet_name="Attendance", index=False)
    return buf.getvalue()

def make_pdf(sub, sgpa, cgpa, arrears, risk, att, student, classification=""):
    from fpdf import FPDF
    pdf = FPDF(); pdf.add_page(); pdf.set_auto_page_break(True, 15)
    pdf.set_font("Helvetica", "B", 16); pdf.cell(0, 10, "SistPerf - progress summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _t(f"Student: {student}   CGPA: {'-' if pd.isna(cgpa) else format(cgpa, '.2f')}   Arrears (RA): {arrears}"), new_x="LMARGIN", new_y="NEXT")
    if classification:
        pdf.cell(0, 6, _t(f"Degree class at this CGPA: {classification}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    def table(title, df, widths):
        pdf.set_font("Helvetica", "B", 11); pdf.cell(0, 8, _t(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 8)
        for c, w in zip(df.columns, widths):
            pdf.cell(w, 6, _t(c)[:18], border=1)
        pdf.ln(); pdf.set_font("Helvetica", "", 8)
        for _, r in df.iterrows():
            for v, w in zip(r, widths):
                pdf.cell(w, 6, _t(round(v, 1) if isinstance(v, float) else v)[:34], border=1)
            pdf.ln()
        pdf.ln(2)
    table("SGPA by semester", sgpa.round(2), [40, 30]) if len(sgpa) else None
    s = sub[["Semester", "Subject", "Final %", "Grade", "Alert"]].copy(); s["Final %"] = s["Final %"].round(1)
    table("Subjects", s.fillna("-"), [20, 70, 22, 20, 50])
    if risk is not None and len(risk):
        table("Arrear risk (exam pending)", risk, [60, 30, 25, 30, 25])
    if att is not None and len(att):
        table("Attendance", att[["Subject", "Type", "Percent", "Required %", "Status", "Can still miss"]], [60, 22, 20, 24, 28, 28])
    pdf.set_font("Helvetica", "I", 8); pdf.multi_cell(0, 5, "Estimates use the SIST Academic Regulations 2019 and placeholder credits unless set in config.yaml.")
    return bytes(pdf.output())
