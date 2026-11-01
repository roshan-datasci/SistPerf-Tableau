"""Generate the SistPerf Tableau workbook: 11 dashboards, ~60 sheets, all calculated fields, parameters, filters and actions.

  python scripts/build_tableau_workbook.py     # writes tableau/SistPerf_Demo.twbx (synthetic) and, if present, tableau/SistPerf_Live.twbx (your real marks)

Needs: pip install tableauhyperapi. Open the .twbx in Tableau Desktop Public Edition.
Live data: after `python -m tracker.tracker --adapter browser --export-tableau`, use Data > <source> > Refresh Extract in Tableau.
Never publish the Live workbook to Tableau Public: published data can be downloaded."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import twb_lib as T
from twb_lib import Source, Pill, Sheet, Dash, Param, members, all_values

# ------------------------------------------------------------------------------------------------ parameters
P_EXAM = Param("exam", "Expected exam mark (%)", "integer", 75, 0, 100, 1)
P_GRADE = Param("grade", "Target grade", "string", "A+", members=["A++", "A+", "B++", "B+", "C"])
P_ATT_TARGET = Param("att_target", "Attendance target (%)", "integer", 80, 50, 100, 1)
P_ATTEND = Param("att_attend", "Classes I will attend next", "integer", 10, 0, 60, 1)
P_MISS = Param("att_miss", "Classes I will miss next", "integer", 0, 0, 60, 1)
P_REMAIN = Param("att_remaining", "Classes remaining this semester", "integer", 30, 0, 80, 1)
P_FUTURE = Param("att_future", "Share of remaining classes I will attend (%)", "integer", 90, 0, 100, 1)

# ------------------------------------------------------------------------------------------------ sources
STR, INT, REAL = "string", "integer", "real"
M_COLS = [("Student_ID", STR), ("Academic_Year", STR), ("Term", STR), ("Semester", INT), ("Semester_Label", STR), ("Subject_Code", STR), ("Subject", STR),
          ("Assessment", STR), ("Assessment_Order", INT), ("Marks", REAL), ("Maximum_Marks", REAL), ("Max_Is_Assumed", INT), ("ERP_Total", REAL),
          ("Result", STR), ("Credits", REAL), ("Fetched_On", STR), ("Att_Type", STR), ("Att_Present", REAL), ("Att_Total", REAL)]
m = Source("marks_long", "marks_long.csv", M_COLS, {"Student_ID", "Academic_Year", "Term", "Semester", "Semester_Label", "Subject_Code", "Subject", "Assessment",
                                                    "Assessment_Order", "Max_Is_Assumed", "Result", "Fetched_On", "Att_Type"})
pr = Source("predictions", "predictions.csv", [("Student_ID", STR), ("Kind", STR), ("Semester", INT), ("Semester_Label", STR), ("Subject_Code", STR), ("Subject", STR),
                                              ("Series", STR), ("Pct", REAL), ("Low", REAL), ("High", REAL), ("Error", REAL), ("Method", STR), ("Trained_On", STR),
                                              ("N_Train", INT), ("Run_At", STR)],
            {"Student_ID", "Kind", "Semester", "Semester_Label", "Subject_Code", "Subject", "Series", "Method", "Trained_On", "N_Train", "Run_At"})
ch = Source("change_history", "change_history.csv", [("Time", STR), ("Event", STR), ("Semester", INT), ("Subject_Code", STR), ("Subject", STR), ("Assessment", STR),
                                                    ("Old", REAL), ("New", REAL), ("Maximum", REAL)], {"Time", "Event", "Semester", "Subject_Code", "Subject", "Assessment"})
sy = Source("sync_log", "sync_log.csv", [("Time", STR), ("Status", STR), ("Source", STR), ("Records_Fetched", INT), ("New", INT), ("Changed", INT), ("Invalid", INT),
                                         ("Message", STR)], {"Time", "Status", "Source", "Message"})
dq = Source("data_quality", "data_quality.csv", [("Check", STR), ("Issues", INT), ("Total_Records", INT), ("Run_At", STR)], {"Check", "Run_At"})
SOURCES = [m, pr, ch, sy, dq]

K = "[Student_ID],[Semester],[Subject_Code]"
FIX = "{FIXED " + K + " : "
PCT = "[Marks] / [Maximum_Marks]"
GRADE_CASE = ('IF {{Has Exam}} = 0 THEN "Pending"\nELSEIF {{Exam %}} < 0.3 OR {{Subject Total %}} < 0.5 THEN "RA"\nELSEIF {{Subject Total %}} >= 0.9 THEN "A++"\n'
              'ELSEIF {{Subject Total %}} >= 0.8 THEN "A+"\nELSEIF {{Subject Total %}} >= 0.7 THEN "B++"\nELSEIF {{Subject Total %}} >= 0.6 THEN "B+"\nELSE "C" END')
GP = 'CASE {{%s}} WHEN "A++" THEN 10 WHEN "A+" THEN 9 WHEN "B++" THEN 8 WHEN "B+" THEN 7 WHEN "C" THEN 6 ELSE 0 END'

# --- marks: row level
m.row("Pct", REAL, PCT, "p0.0%")
m.row("Is Centum", INT, "IF [Marks] = [Maximum_Marks] THEN 1 ELSE 0 END")
m.row("CAE Centum", INT, 'IF CONTAINS([Assessment], "CAE") AND [Marks] = [Maximum_Marks] THEN 1 ELSE 0 END')
m.row("Exam Centum", INT, 'IF [Assessment] = "Exam" AND [Marks] = [Maximum_Marks] THEN 1 ELSE 0 END')
m.dim("Assessment Label", STR, 'STR([Assessment_Order]) + ". " + [Assessment]')
m.dim("Timeline Step", STR, '[Semester_Label] + " - " + STR([Assessment_Order]) + ". " + [Assessment]')
m.dim("Max Source", STR, 'IF [Max_Is_Assumed] = 1 THEN "Assumed" ELSE "From curriculum / ERP" END')
m.dim("Score Band", STR, 'IF {{Pct}} >= 0.9 THEN "90-100" ELSEIF {{Pct}} >= 0.8 THEN "80-89" ELSEIF {{Pct}} >= 0.7 THEN "70-79" ELSEIF {{Pct}} >= 0.6 THEN "60-69" '
      'ELSEIF {{Pct}} >= 0.5 THEN "50-59" ELSE "Below 50" END')
m.row("Weighted Points", REAL, "[Marks] / [Maximum_Marks] * 50", "0.0")
# --- marks: per subject (LOD)
m.row("Total Marks", REAL, FIX + 'SUM(IF [Assessment] = "Internal" OR [Assessment] = "Exam" THEN [Marks] END)}')
m.row("Total Max", REAL, FIX + 'SUM(IF [Assessment] = "Internal" OR [Assessment] = "Exam" THEN [Maximum_Marks] END)}')
m.row("Subject Total %", REAL, "{{Total Marks}} / {{Total Max}}", "p0.0%")
m.row("Exam %", REAL, FIX + 'SUM(IF [Assessment] = "Exam" THEN [Marks] END)} / ' + FIX + 'SUM(IF [Assessment] = "Exam" THEN [Maximum_Marks] END)}', "p0.0%")
m.dim("Has Exam", INT, FIX + 'MAX(IF [Assessment] = "Exam" THEN 1 ELSE 0 END)}')
m.dim("Grade", STR, GRADE_CASE)
m.row("Grade Points", INT, GP % "Grade")
m.row("Credit Points", REAL, 'IF [Assessment] = "Exam" AND {{Grade}} <> "RA" AND {{Grade}} <> "Pending" THEN {{Grade Points}} * [Credits] END')
m.row("Credits Cleared", REAL, 'IF [Assessment] = "Exam" AND {{Grade}} <> "RA" AND {{Grade}} <> "Pending" THEN [Credits] END')
m.agg("SGPA", REAL, "SUM({{Credit Points}}) / SUM({{Credits Cleared}})", "0.00")
m.row("CGPA", REAL, "{FIXED [Student_ID] : SUM({{Credit Points}})} / {FIXED [Student_ID] : SUM({{Credits Cleared}})}", "0.00")
m.agg("CGPA Running", REAL, "RUNNING_SUM(SUM({{Credit Points}})) / RUNNING_SUM(SUM({{Credits Cleared}}))", "0.00", tc=True)
m.row("Arrear", INT, 'IF [Assessment] = "Exam" AND {{Grade}} = "RA" THEN 1 ELSE 0 END')
m.row("CAE 1 Pct", REAL, 'IF [Assessment] = "CAE 1" THEN {{Pct}} END', "p0.0%")
m.row("CAE 2 Pct", REAL, 'IF [Assessment] = "CAE 2" THEN {{Pct}} END', "p0.0%")
m.agg("CAE Improvement", REAL, "AVG({{CAE 2 Pct}}) - AVG({{CAE 1 Pct}})", "p0.0%")
m.agg("CAE 1 Avg", REAL, "AVG({{CAE 1 Pct}})", "p0.0%")
m.agg("CAE 2 Avg", REAL, "AVG({{CAE 2 Pct}})", "p0.0%")
m.agg("Semesters Completed", INT, 'COUNTD(IF [Assessment] = "Exam" THEN [Semester] END)')
m.agg("Subjects", INT, "COUNTD([Subject_Code])")
m.agg("Current Semester Avg", REAL, "AVG(IF [Semester] = {FIXED [Student_ID] : MAX([Semester])} THEN {{Pct}} END)", "p0.0%")
m.agg("Pct Range", REAL, "MAX({{Pct}}) - MIN({{Pct}})", "p0.0%")
# --- attendance
m.row("Att Anchor", INT, "IF [Assessment_Order] = " + FIX + "MIN([Assessment_Order])} THEN 1 ELSE 0 END")
m.row("Att Present 1x", REAL, "IF {{Att Anchor}} = 1 THEN [Att_Present] END")
m.row("Att Total 1x", REAL, "IF {{Att Anchor}} = 1 THEN [Att_Total] END")
m.agg("Attendance Overall", REAL, "SUM({{Att Present 1x}}) / SUM({{Att Total 1x}})", "p0.0%")
m.row("Att Pct", REAL, "[Att_Present] / [Att_Total]", "p0.0%")
m.row("Att Required", REAL, 'IF [Att_Type] = "Practical" THEN 1.0 ELSE 0.8 END', "p0%")
m.dim("Has Attendance", INT, "IF ISNULL([Att_Total]) THEN 0 ELSE 1 END")
m.dim("Att Status", STR, 'IF ISNULL([Att_Total]) THEN "No data" ELSEIF {{Att Pct}} < {{Att Required}} THEN "Below minimum" ELSEIF {{Att Pct}} < {{Att Required}} + 0.0001 THEN "No margin" ELSE "OK" END')
m.row("Can Miss", INT, "IF ISNULL([Att_Total]) THEN NULL ELSEIF {{Att Pct}} >= {{Att Required}} THEN INT([Att_Present] / {{Att Required}} - [Att_Total] + 0.000001) ELSE 0 END")
m.row("Classes Needed", INT, "IF ISNULL([Att_Total]) OR {{Att Pct}} >= {{Att Required}} THEN 0 ELSEIF {{Att Required}} >= 1 THEN NULL "
      "ELSE CEILING(({{Att Required}} * [Att_Total] - [Att_Present]) / (1 - {{Att Required}}) - 0.000001) END")
m.row("Shortage", REAL, "{{Att Required}} - {{Att Pct}}", "p0.0%")
m.row("Bunk Capacity", INT, "IF ISNULL([Att_Total]) THEN NULL ELSEIF [Att_Present] / [Att_Total] >= {{P:att_target}} / 100 THEN "
      "INT([Att_Present] / ({{P:att_target}} / 100) - [Att_Total] + 0.000001) ELSE 0 END")
m.row("Projected Att %", REAL, "([Att_Present] + {{P:att_attend}}) / ([Att_Total] + {{P:att_attend}} + {{P:att_miss}})", "p0.0%")
m.row("Year-end Att %", REAL, "([Att_Present] + {{P:att_remaining}} * {{P:att_future}} / 100) / ([Att_Total] + {{P:att_remaining}})", "p0.0%")
m.agg("Subjects Below Minimum", INT, 'COUNTD(IF {{Att Status}} = "Below minimum" THEN [Subject_Code] END)')
# --- risk, early warning
m.row("CAE Avg Subject", REAL, FIX + 'AVG(IF CONTAINS([Assessment], "CAE") THEN [Marks] / [Maximum_Marks] END)}', "p0.0%")
m.row("Internal Basis %", REAL, "IF " + FIX + 'COUNT(IF [Assessment] = "Internal" THEN 1 END)} > 0 THEN ' + FIX +
      'AVG(IF [Assessment] = "Internal" THEN [Marks] / [Maximum_Marks] END)} ELSE {{CAE Avg Subject}} END', "p0.0%")
m.row("Exam Needed To Pass", REAL, "IF (1 - {{Internal Basis %}}) > 0.3 THEN (1 - {{Internal Basis %}}) ELSE 0.3 END", "p0.0%")
m.dim("Pass Risk", STR, 'IF {{Has Exam}} = 1 THEN "Result published" ELSEIF {{Exam Needed To Pass}} > 1 THEN "Unreachable" ELSEIF {{Exam Needed To Pass}} >= 0.75 THEN "High" '
      'ELSEIF {{Exam Needed To Pass}} >= 0.5 THEN "Watch" ELSE "Low" END')
m.dim("Needs Attention", INT, 'IF {{Has Exam}} = 0 AND ({{Pass Risk}} = "High" OR {{Pass Risk}} = "Watch" OR {{Pass Risk}} = "Unreachable" OR {{Att Status}} = "Below minimum") THEN 1 ELSE 0 END')
m.dim("Warning Text", STR, '[Subject] + ": CAE average " + STR(ROUND({{CAE Avg Subject}} * 100, 0)) + "%, needs " + STR(ROUND({{Exam Needed To Pass}} * 100, 0)) + "% in the exam"'
      ' + IF {{Att Status}} = "Below minimum" THEN "; attendance " + STR(ROUND({{Att Pct}} * 100, 0)) + "% (minimum " + STR(ROUND({{Att Required}} * 100, 0)) + "%)" ELSE "" END')
# --- success score (experimental index)
m.agg("Academic Avg", REAL, 'AVG(IF [Assessment] = "Internal" OR [Assessment] = "Exam" THEN {{Pct}} END)', "p0.0%")
m.agg("Consistency Index", REAL, "IF STDEV({{Pct}}) * 4 > 1 THEN 0 ELSE 1 - STDEV({{Pct}}) * 4 END", "p0%")
m.agg("Improvement Index", REAL, "IF ISNULL({{CAE Improvement}}) THEN 0.5 ELSEIF 0.5 + {{CAE Improvement}} > 1 THEN 1 ELSEIF 0.5 + {{CAE Improvement}} < 0 THEN 0 ELSE 0.5 + {{CAE Improvement}} END", "p0%")
m.agg("Success Score", REAL, "100 * (0.5 * {{Academic Avg}} + 0.2 * IFNULL({{Attendance Overall}}, {{Academic Avg}}) + 0.15 * {{Consistency Index}} + 0.15 * {{Improvement Index}})", "0")
# --- what-if and goal planner
m.row("Projected Exam %", REAL, "{{P:exam}} / 100", "p0%")
m.row("Projected Total %", REAL, "0.5 * {{Internal Basis %}} + 0.5 * {{Projected Exam %}}", "p0.0%")
m.dim("Projected Grade", STR, 'IF {{Projected Exam %}} < 0.3 OR {{Projected Total %}} < 0.5 THEN "RA" ELSEIF {{Projected Total %}} >= 0.9 THEN "A++" ELSEIF {{Projected Total %}} >= 0.8 THEN "A+" '
      'ELSEIF {{Projected Total %}} >= 0.7 THEN "B++" ELSEIF {{Projected Total %}} >= 0.6 THEN "B+" ELSE "C" END')
m.row("Projected GP", INT, GP % "Projected Grade")
m.row("Proj Credit Points", REAL, 'IF {{Att Anchor}} = 1 AND {{Has Exam}} = 0 AND {{Projected Grade}} <> "RA" THEN {{Projected GP}} * [Credits] END')
m.row("Proj Credits Cleared", REAL, 'IF {{Att Anchor}} = 1 AND {{Has Exam}} = 0 AND {{Projected Grade}} <> "RA" THEN [Credits] END')
m.agg("Projected SGPA", REAL, "SUM({{Proj Credit Points}}) / SUM({{Proj Credits Cleared}})", "0.00")
m.row("Target %", REAL, 'CASE {{P:grade}} WHEN "A++" THEN 0.9 WHEN "A+" THEN 0.8 WHEN "B++" THEN 0.7 WHEN "B+" THEN 0.6 ELSE 0.5 END', "p0%")
m.row("Exam Needed For Goal", REAL, "IF (2 * {{Target %}} - {{Internal Basis %}}) < 0.3 THEN 0.3 ELSE (2 * {{Target %}} - {{Internal Basis %}}) END", "p0.0%")
m.dim("Goal Status", STR, 'IF {{Has Exam}} = 1 THEN "Result published" ELSEIF {{Exam Needed For Goal}} > 1 THEN "Not reachable" ELSE "Reachable" END')
m.dim("Goal Label", STR, 'STR(ROUND({{Exam Needed For Goal}} * 100, 0)) + "% in the exam (about " + STR(ROUND({{Exam Needed For Goal}} * IF CONTAINS(LOWER([Subject]), "lab") THEN 25 ELSE 50 END, 0)) '
      '+ " / " + STR(IF CONTAINS(LOWER([Subject]), "lab") THEN 25 ELSE 50 END) + ")"')
# --- predictions
pr.dim("Range Label", STR, 'STR(ROUND([Pct] * 100, 0)) + "%   (range " + STR(ROUND([Low] * 100, 0)) + "-" + STR(ROUND([High] * 100, 0)) + "%)"')
pr.row("Abs Error", REAL, "ABS([Error])", "p0.0%")
pr.agg("Mean Abs Error", REAL, "AVG({{Abs Error}})", "p0.0%")
pr.agg("Subjects Tested", INT, 'COUNTD(IF [Kind] = "Backtest" THEN [Subject_Code] END)')
# --- changes, sync, data quality
ch.dim("Change", STR, 'IFNULL(STR([Old]), "new") + " -> " + STR([New]) + " / " + STR([Maximum])')
sy.agg("Last OK", STR, 'MAX(IF [Status] = "OK" THEN [Time] END)')
sy.agg("Failed Syncs", INT, 'SUM(IF [Status] <> "OK" THEN 1 ELSE 0 END)')
sy.agg("Syncs", INT, "COUNT([Time])")
sy.agg("Records Changed", INT, "SUM([New]) + SUM([Changed])")
sy.dim("Sync Summary", STR, 'STR([Records_Fetched]) + " fetched, " + STR([New]) + " new, " + STR([Changed]) + " changed, " + STR([Invalid]) + " invalid" + IF [Message] <> "" THEN "  |  " + [Message] ELSE "" END')
dq.agg("Records Checked", INT, "MAX([Total_Records])")
dq.agg("Issue Rate", REAL, "SUM([Issues]) / MAX([Total_Records])", "p1")

# ------------------------------------------------------------------------------------------------ palettes (black and white, red only for problems)
RED = "#B42318"
ASSESS = [("1. CAE 1", "#B5B5B9"), ("2. CAE 2", "#6B6B70"), ("3. Internal", "#3A3A3D"), ("4. Exam", "#1F1F1F")]
GRADES = [("A++", "#1F1F1F"), ("A+", "#3A3A3D"), ("B++", "#6B6B70"), ("B+", "#9A9AA0"), ("C", "#C9C9CD"), ("RA", RED), ("Pending", "#E0E0E2")]
BANDS = [("90-100", "#1F1F1F"), ("80-89", "#4A4A4E"), ("70-79", "#7C7C80"), ("60-69", "#B5B5B9"), ("50-59", "#DADADD"), ("Below 50", RED)]
RISK = [("Low", "#B5B5B9"), ("Watch", "#6B6B70"), ("High", "#1F1F1F"), ("Unreachable", RED), ("Result published", "#E0E0E2")]
ATT = [("OK", "#6B6B70"), ("No margin", "#9A9AA0"), ("Below minimum", RED), ("No data", "#E0E0E2")]
SERIES = [("Predicted", "#B5B5B9"), ("Actual", "#1F1F1F")]
SEMS = [(f"Sem {i}", c) for i, c in enumerate(["#C9C9CD", "#9A9AA0", "#1F1F1F", "#6B6B70", "#3A3A3D", "#B5B5B9", "#4A4A4E", "#7C7C80"], 1)]
GOAL = [("Reachable", "#1F1F1F"), ("Not reachable", RED), ("Result published", "#E0E0E2")]
SYNC = [("OK", "#1F1F1F"), ("FAILED", RED)]
DARK = "#1F1F1F"

def build_sheets(student, has_att):
    d = lambda f, s=m: Pill(s, f)
    a = lambda f, s=m: Pill(s, f, "avg")
    sm = lambda f, s=m: Pill(s, f, "sum")
    cd = lambda f, s=m: Pill(s, f, "cntd")
    sd = lambda f, s=m: Pill(s, f, "stdev")
    QF3 = [all_values(m, "Academic_Year", 1), all_values(m, "Semester_Label", 2), all_values(m, "Subject", 3)]
    QF4 = QF3 + [all_values(m, "Assessment", 4)]
    CAE = members(m, "Assessment", ["CAE 1", "CAE 2"]); IE = members(m, "Assessment", ["Internal", "Exam"]); EX = members(m, "Assessment", ["Exam"])
    PEND = members(m, "Has Exam", [0]); ATTF = members(m, "Has Attendance", [1]); ATTN = members(m, "Needs Attention", [1])
    S = {}
    def add(src, name, title, mark, **kw):
        kw.setdefault("student", student if src in (m, pr) else None)
        S[name] = Sheet(src, name, title, mark, **kw)
    def kpi(name, title, pill, filters=None, src=m, font=26):
        add(src, name, title, "Text", text=pill, filters=filters if filters is not None else QF3, labels=True, font=font)
    # KPI tiles
    kpi("KPI Current Semester", "Current semester average", d("Current Semester Avg"))
    kpi("KPI Overall Average", "Overall average", a("Pct"), QF4)
    kpi("KPI CAE 1", "CAE 1 average", d("CAE 1 Avg"))
    kpi("KPI CAE 2", "CAE 2 average", d("CAE 2 Avg"))
    kpi("KPI Subjects", "Subjects", d("Subjects"))
    kpi("KPI Semesters", "Semesters completed", d("Semesters Completed"))
    kpi("KPI CGPA", "CGPA", a("CGPA"))
    kpi("KPI Centums", "Total centums", sm("Is Centum"), QF4)
    kpi("KPI CAE Centums", "CAE centums", sm("CAE Centum"))
    kpi("KPI Exam Centums", "Exam centums", sm("Exam Centum"))
    kpi("KPI Arrears", "Arrears (RA)", sm("Arrear"))
    kpi("KPI Success Score", "Success score (experimental)", d("Success Score"))
    kpi("KPI Academic", "Academic average", d("Academic Avg"))
    kpi("KPI Consistency", "Consistency index", d("Consistency Index"))
    kpi("KPI Improvement", "Improvement index", d("Improvement Index"))
    kpi("KPI Attendance", "Attendance (all subjects)", d("Attendance Overall"), QF3 + [ATTF])
    kpi("KPI Below Min", "Subjects below minimum", d("Subjects Below Minimum"), QF3 + [ATTF])
    kpi("KPI Projected SGPA", "Projected SGPA (with your exam mark)", d("Projected SGPA"), [PEND])
    # marks charts
    add(m, "Overall Trend", "Overall performance trend", "Line", rows=[a("Pct")], cols=[d("Semester_Label")], filters=QF4, labels=True, mark_color=DARK, actions=True)
    add(m, "Semester Progression", "Progression within each semester (CAE 1 > CAE 2 > Internal > Exam)", "Line", rows=[a("Pct")], cols=[d("Assessment Label")], color=d("Semester_Label"),
        palette=SEMS, filters=QF3, labels=True, legend=True)
    add(m, "CAE 1 vs CAE 2", "CAE 1 vs CAE 2 by subject", "Bar", rows=[a("Pct")], cols=[d("Subject"), d("Assessment Label")], color=d("Assessment Label"), palette=ASSESS,
        filters=QF3 + [CAE], labels=True, hide_axes=[a("Pct")], legend=True, actions=True)
    add(m, "Semester Performance", "Internal vs Exam by semester", "Bar", rows=[a("Pct")], cols=[d("Semester_Label"), d("Assessment Label")], color=d("Assessment Label"), palette=ASSESS,
        filters=QF3 + [IE], labels=True, hide_axes=[a("Pct")], legend=True, actions=True)
    add(m, "Internal vs Exam by Subject", "Internal vs Exam by subject", "Bar", rows=[d("Subject"), d("Assessment Label")], cols=[a("Pct")], color=d("Assessment Label"), palette=ASSESS,
        filters=QF3 + [IE], labels=True, hide_axes=[a("Pct")], legend=True, actions=True)
    add(m, "Subject Heatmap", "Subject performance heatmap", "Square", rows=[d("Subject")], cols=[d("Assessment Label")], color=d("Score Band"), palette=BANDS, text=a("Pct"),
        filters=QF4, labels=True, legend=True, actions=True)
    add(m, "CAE Improvement", "CAE improvement (CAE 2 minus CAE 1)", "Bar", rows=[d("Subject")], cols=[d("CAE Improvement")], filters=QF3 + [CAE], labels=True, mark_color=DARK,
        hide_axes=[d("CAE Improvement")], actions=True)
    add(m, "Subject Consistency", "Variation (std. deviation of scores)", "Bar", rows=[d("Subject")], cols=[sd("Pct")], filters=QF4, labels=True, mark_color=DARK, hide_axes=[sd("Pct")])
    add(m, "Subject Range", "Range (highest minus lowest score)", "Bar", rows=[d("Subject")], cols=[d("Pct Range")], filters=QF4, labels=True, mark_color="#6B6B70", hide_axes=[d("Pct Range")])
    add(m, "Subject Average", "Average score by subject", "Bar", rows=[d("Subject")], cols=[a("Pct")], filters=QF4, labels=True, mark_color=DARK, hide_axes=[a("Pct")],
        sorts=[(d("Subject"), a("Pct"), "DESC")], actions=True)
    add(m, "Grade Distribution", "Grade distribution", "Bar", rows=[cd("Subject_Code")], cols=[d("Grade")], color=d("Grade"), palette=GRADES, filters=QF3 + [EX], labels=True,
        hide_axes=[cd("Subject_Code")], actions=True)
    add(m, "SGPA by Semester", "SGPA by semester", "Bar", rows=[d("SGPA")], cols=[d("Semester_Label")], filters=QF3, labels=True, mark_color=DARK, hide_axes=[d("SGPA")])
    add(m, "CGPA Progression", "CGPA progression", "Line", rows=[d("CGPA Running")], cols=[d("Semester_Label")], filters=QF3, labels=True, mark_color=DARK)
    add(m, "Assessment Contribution", "How Internal and Exam contribute to the total (out of 100)", "Bar", rows=[d("Subject")], cols=[sm("Weighted Points")], color=d("Assessment Label"),
        palette=ASSESS, filters=QF3 + [IE], labels=True, hide_axes=[sm("Weighted Points")], legend=True)
    add(m, "Timeline Chart", "Academic timeline: assessments in order", "Line", rows=[a("Pct")], cols=[d("Timeline Step")], filters=QF3, labels=True, mark_color=DARK)
    add(m, "Results Table", "Marks by subject and assessment", "Text", rows=[d("Semester_Label"), d("Subject"), d("Grade")], cols=[d("Assessment Label")], text=sm("Marks"), filters=QF4)
    add(m, "ERP Results", "ERP total and result per subject", "Text", rows=[d("Semester_Label"), d("Subject"), d("Result")], text=a("ERP_Total"), filters=QF3 + [EX])
    # what-if, goals
    add(m, "WhatIf Projection", "Projected total if you score the expected exam mark", "Bar", rows=[d("Subject")], cols=[a("Projected Total %")], color=d("Projected Grade"), palette=GRADES,
        filters=[PEND], labels=True, hide_axes=[a("Projected Total %")], legend=True)
    add(m, "Goal Planner", "Exam mark needed for your target grade", "Bar", rows=[d("Subject")], cols=[a("Exam Needed For Goal")], color=d("Goal Status"), palette=GOAL, text=d("Goal Label"),
        filters=[PEND], labels=True, hide_axes=[a("Exam Needed For Goal")], legend=True)
    add(m, "Pass Risk Count", "Subjects by pass-risk level", "Bar", rows=[cd("Subject_Code")], cols=[d("Pass Risk")], color=d("Pass Risk"), palette=RISK, filters=[PEND], labels=True,
        hide_axes=[cd("Subject_Code")])
    add(m, "Exam Needed To Pass", "Minimum exam mark needed to pass", "Bar", rows=[d("Subject")], cols=[a("Exam Needed To Pass")], color=d("Pass Risk"), palette=RISK, filters=[PEND],
        labels=True, hide_axes=[a("Exam Needed To Pass")], legend=True)
    add(m, "Early Warning List", "Subjects needing attention (with the evidence)", "Text", rows=[d("Pass Risk"), d("Subject")], text=d("Warning Text"), filters=[ATTN])
    # attendance
    if has_att:
        add(m, "Attendance by Subject", "Attendance by subject", "Bar", rows=[d("Subject")], cols=[a("Att Pct")], color=d("Att Status"), palette=ATT, filters=[ATTF], labels=True,
            hide_axes=[a("Att Pct")], legend=True, sorts=[(d("Subject"), a("Att Pct"), "ASC")])
        add(m, "Attendance WhatIf", "Attendance if you attend / miss the next classes", "Bar", rows=[d("Subject")], cols=[a("Projected Att %")], filters=[ATTF], labels=True, mark_color=DARK, hide_axes=[a("Projected Att %")])
        add(m, "Attendance Year End", "Expected attendance at semester end", "Bar", rows=[d("Subject")], cols=[a("Year-end Att %")], filters=[ATTF], labels=True, mark_color="#6B6B70", hide_axes=[a("Year-end Att %")])
        add(m, "Bunk Planner", "Classes you can still miss (at your target %)", "Bar", rows=[d("Subject")], cols=[a("Bunk Capacity")], filters=[ATTF], labels=True, mark_color=DARK, hide_axes=[a("Bunk Capacity")])
        add(m, "Attendance Risk", "Subject risk ranking (shortage vs required %)", "Bar", rows=[d("Subject")], cols=[a("Shortage")], filters=[ATTF], labels=True, mark_color=RED,
            hide_axes=[a("Shortage")], sorts=[(d("Subject"), a("Shortage"), "DESC")])
        add(m, "Classes To Recover", "Classes in a row needed to recover", "Bar", rows=[d("Subject")], cols=[a("Classes Needed")], filters=[ATTF], labels=True, mark_color="#6B6B70", hide_axes=[a("Classes Needed")])
        add(m, "Attendance vs Marks", "Attendance vs CAE average (each dot is a subject; correlation is not causation)", "Circle", rows=[a("CAE Avg Subject")], cols=[a("Att Pct")],
            detail=[d("Subject")], text=d("Subject"), filters=[ATTF], labels=True, mark_color=DARK)
    # predictions
    FC = members(pr, "Kind", ["Forecast"]); BT = members(pr, "Kind", ["Backtest"]); PRED = members(pr, "Series", ["Predicted"])
    add(pr, "Forecast", "Predicted exam score (estimate with range)", "Bar", rows=[d("Subject", pr)], cols=[a("Pct", pr)], text=d("Range Label", pr), filters=[FC, PRED], labels=True, mark_color="#6B6B70",
        hide_axes=[a("Pct", pr)])
    add(pr, "Prediction vs Actual", "Back-test: predicted vs actual exam score", "Bar", rows=[d("Subject", pr), d("Series", pr)], cols=[a("Pct", pr)], color=d("Series", pr), palette=SERIES,
        filters=[BT], labels=True, hide_axes=[a("Pct", pr)], legend=True)
    add(pr, "Prediction Error", "Prediction error (actual minus predicted)", "Bar", rows=[d("Subject", pr)], cols=[a("Error", pr)], filters=[BT, PRED], labels=True, mark_color=DARK, hide_axes=[a("Error", pr)])
    add(pr, "KPI MAE", "Average error (back-test)", "Text", text=d("Mean Abs Error", pr), filters=[BT, PRED], labels=True, font=26)
    add(pr, "KPI Tested", "Subjects back-tested", "Text", text=d("Subjects Tested", pr), labels=True, font=26)
    add(pr, "Model Info", "How each forecast was made", "Text", rows=[d("Semester_Label", pr), d("Trained_On", pr)], text=d("Method", pr), filters=[FC, PRED])
    # sync, changes, data quality
    kpi("KPI Last Sync", "Last successful sync", d("Last OK", sy), [], sy, 18)
    kpi("KPI Syncs", "Sync attempts", d("Syncs", sy), [], sy)
    kpi("KPI Failed", "Failed syncs", d("Failed Syncs", sy), [], sy)
    kpi("KPI Changed", "Marks added or changed", d("Records Changed", sy), [], sy)
    add(sy, "Sync History", "Sync history", "Text", rows=[d("Time", sy), d("Status", sy)], text=d("Sync Summary", sy), color=d("Status", sy), palette=SYNC)
    add(ch, "Change History", "Mark change history", "Text", rows=[d("Time", ch), d("Event", ch), d("Subject", ch), d("Assessment", ch)], text=d("Change", ch))
    add(dq, "DQ Checks", "Data quality checks (issues found)", "Bar", rows=[d("Check", dq)], cols=[Pill(dq, "Issues", "sum")], labels=True, mark_color=DARK)
    kpi("KPI Records Checked", "Records checked", d("Records Checked", dq), [], dq)
    kpi("KPI Issue Rate", "Share of records with an issue", d("Issue Rate", dq), [], dq)
    add(m, "DQ Assumed Max", "Marks by maximum-marks source", "Bar", rows=[cd("Subject_Code")], cols=[d("Max Source"), d("Assessment")], labels=True, mark_color="#6B6B70")
    return S

# ------------------------------------------------------------------------------------------------ dashboards
def build_dashboards(S, has_att):
    filt = [(m, "Academic_Year", "Academic year"), (m, "Semester_Label", "Semester"), (m, "Subject", "Subject")]
    filt4 = filt + [(m, "Assessment", "Assessment type")]
    def start(name, title, sub, filters=filt4):
        d = Dash(name); d.header(title, sub, S["KPI Last Sync"])
        if filters: d.filters(filters)
        return d
    def kpis(d, names, h=104):
        d.row([(S[n], 12 // len(names)) for n in names], h)
    D = []
    # 1 Home
    d = start("Home", "SistPerf", "Academic performance overview for SIST")
    kpis(d, ["KPI Current Semester", "KPI Overall Average", "KPI CAE 1", "KPI CAE 2", "KPI Subjects", "KPI Semesters"])
    kpis(d, ["KPI CGPA", "KPI Centums", "KPI CAE Centums", "KPI Exam Centums", "KPI Arrears", "KPI Success Score"])
    d.row([(S["Overall Trend"], 12)], 300)
    d.row([(S["CAE 1 vs CAE 2"], 6), (S["Semester Performance"], 6)], 360)
    d.row([(S["Subject Heatmap"], 12)], 440)
    d.row([(S["CAE Improvement"], 6), (S["Subject Consistency"], 6)], 340)
    d.row([(S["SGPA by Semester"], 4), (S["Grade Distribution"], 4), (S["Forecast"], 4)], 320)
    d.row([(S["Results Table"], 12)], 520)
    D.append(d)
    # 2 Assessment analysis
    d = start("Assessment Analysis", "Assessment analysis", "CAE 1, CAE 2, Internal and Exam")
    kpis(d, ["KPI CAE 1", "KPI CAE 2", "KPI CAE Centums", "KPI Exam Centums"])
    d.row([(S["CAE 1 vs CAE 2"], 6), (S["CAE Improvement"], 6)], 380)
    d.row([(S["Internal vs Exam by Subject"], 6), (S["Assessment Contribution"], 6)], 440)
    d.row([(S["Semester Progression"], 12)], 340)
    D.append(d)
    # 3 Subject analysis
    d = start("Subject Analysis", "Subject analysis", "Strengths, variation and ranking")
    d.row([(S["Subject Heatmap"], 12)], 440)
    d.row([(S["Subject Average"], 4), (S["Subject Consistency"], 4), (S["Subject Range"], 4)], 400)
    if has_att:
        d.row([(S["Attendance vs Marks"], 12)], 380)
    D.append(d)
    # 4 Semester analysis
    d = start("Semester Analysis", "Semester analysis", "Progress, SGPA and CGPA", filt)
    kpis(d, ["KPI CGPA", "KPI Semesters", "KPI Arrears", "KPI Current Semester"])
    d.row([(S["Overall Trend"], 6), (S["Semester Performance"], 6)], 360)
    d.row([(S["SGPA by Semester"], 4), (S["CGPA Progression"], 4), (S["Grade Distribution"], 4)], 340)
    D.append(d)
    # 5 Academic timeline
    d = start("Academic Timeline", "Academic timeline", "Every assessment in order (the ERP gives no exam dates)", filt)
    d.row([(S["Timeline Chart"], 12)], 420)
    d.row([(S["Semester Progression"], 12)], 340)
    D.append(d)
    # 6 Goals and what-if
    d = start("Goals and What-if", "Goals and what-if", "Estimates from your CAE average until the Internal mark is published", None)
    d.params([(T.PARAMS["exam"], "slider"), (T.PARAMS["grade"], "compact")], 64)
    kpis(d, ["KPI Projected SGPA", "KPI CGPA", "KPI Arrears"])
    d.row([(S["WhatIf Projection"], 6), (S["Goal Planner"], 6)], 420)
    d.note("Rules: total = 50% Internal + 50% Exam; RA if the exam is under 30% or the total under 50% (SIST Regulations). Before Internal is published it is estimated by your CAE average.")
    D.append(d)
    # 7 Prediction
    d = Dash("Performance Prediction"); d.header("Performance prediction", "Experimental estimates, back-tested without looking ahead", S["KPI Last Sync"])
    kpis(d, ["KPI MAE", "KPI Tested"])
    d.row([(S["Forecast"], 6), (S["Model Info"], 6)], 380)
    d.row([(S["Prediction vs Actual"], 7), (S["Prediction Error"], 5)], 480)
    d.note("A forecast is an estimate, not a result. Back-tests predict an earlier semester using only the semesters before it, then compare with the actual exam marks.")
    D.append(d)
    # 8 Attendance
    if has_att:
        d = start("Attendance", "Attendance", "Minimum 80% for theory, 100% for practicals", [(m, "Subject", "Subject")])
        d.params([(T.PARAMS["att_target"], "slider"), (T.PARAMS["att_attend"], "slider"), (T.PARAMS["att_miss"], "slider")], 64)
        d.params([(T.PARAMS["att_remaining"], "slider"), (T.PARAMS["att_future"], "slider")], 64)
        kpis(d, ["KPI Attendance", "KPI Below Min"])
        d.row([(S["Attendance by Subject"], 6), (S["Attendance Risk"], 6)], 380)
        d.row([(S["Attendance WhatIf"], 6), (S["Attendance Year End"], 6)], 360)
        d.row([(S["Bunk Planner"], 6), (S["Classes To Recover"], 6)], 360)
        D.append(d)
    # 9 Early warning and success
    d = start("Early Warning", "Early warning and success score", "Evidence behind every flag", [(m, "Subject", "Subject")])
    kpis(d, ["KPI Success Score", "KPI Academic", "KPI Consistency", "KPI Improvement"] + (["KPI Attendance"] if has_att else []))
    d.row([(S["Early Warning List"], 7), (S["Pass Risk Count"], 5)], 420)
    d.row([(S["Exam Needed To Pass"], 12)], 360)
    d.note("Success score (experimental index) = 50% academic average + 20% attendance + 15% consistency + 15% improvement. Flags are for support, not predictions of failure.")
    D.append(d)
    # 10 Live data
    d = Dash("Live Data and Sync"); d.header("Live data and sync", "Is the dashboard up to date?", S["KPI Last Sync"])
    kpis(d, ["KPI Syncs", "KPI Failed", "KPI Changed", "KPI Records Checked", "KPI Issue Rate"])
    d.row([(S["Sync History"], 7), (S["Change History"], 5)], 420)
    d.row([(S["DQ Checks"], 7), (S["DQ Assumed Max"], 5)], 380)
    D.append(d)
    # 11 Detailed marks
    d = start("Detailed Marks", "Detailed marks", "Every mark and the ERP's own result")
    d.row([(S["Results Table"], 8), (S["ERP Results"], 4)], 1000)
    D.append(d)
    return D

def action_pairs(dashes, S):
    out = []
    for d in dashes:
        for n in dict.fromkeys(d.sheets):
            if S.get(n) is not None and S[n].actions:
                out.append((d.name, n))
    return out

def make(out_path, data_dir, student=None):
    import pandas as pd
    csvs = {s.key: os.path.join(data_dir, s.csv) for s in SOURCES}
    marks = pd.read_csv(csvs["marks_long"])
    has_att = bool(marks["Att_Total"].notna().any())
    S = build_sheets(student, has_att)
    dashes = build_dashboards(S, has_att)
    used = {n for d in dashes for n in d.sheets}
    sheets = [s for n, s in S.items() if n in used]
    _rows, fallback = T.package(out_path, SOURCES, csvs, sheets, dashes, action_pairs(dashes, S))
    return out_path, len(sheets), len(dashes), fallback

def report(res):
    path, n_sheets, n_dash, fallback = res
    print("Wrote %s (%d sheets, %d dashboards)" % (path, n_sheets, n_dash))
    if fallback:
        print("  NOTE: the Hyper API could not run on this PC, so the workbook holds EMPTY extracts.\n"
              "  In Tableau open the workbook, then for EACH data source choose Data > (source name) > Extract > Refresh (full) to load your data.\n"
              "  (Windows error 0x11c7 means Windows is blocking the Hyper DLL, usually Smart App Control.)")

def main():
    root = os.getcwd()
    os.makedirs("tableau", exist_ok=True)
    demo = os.path.join(root, "tableau", "sample_data")
    if os.path.exists(os.path.join(demo, "marks_long.csv")):
        report(make("tableau/SistPerf_Demo.twbx", demo, "STU001"))
    live = os.path.join(root, "data", "private", "tableau")
    if os.path.exists(os.path.join(live, "marks_long.csv")):
        report(make("tableau/SistPerf_Live.twbx", live))
    else:
        print("No real data yet. Run: python -m tracker.tracker --adapter browser --export-tableau   then run this script again.")

if __name__ == "__main__":
    main()
