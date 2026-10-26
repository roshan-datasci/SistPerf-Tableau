"""Generate the SistPerf Tableau workbook (worksheets, calculated fields, dashboards) from the exported data.

  python scripts/build_tableau_workbook.py            # writes tableau/SistPerf_Demo.twbx (synthetic) and, if present, tableau/SistPerf_Live.twbx (your real marks)

Open the .twb in Tableau Desktop Public Edition. The Live workbook reads data/private/tableau/marks_long.csv, so after
`python -m tracker.tracker --adapter browser --export-tableau` just press F5 in Tableau (Data > Refresh).
All calculations (percentages, grades, SGPA, CGPA) are Tableau calculated fields you can read and edit.
Never publish the Live workbook to Tableau Public: published data can be downloaded."""
import datetime, os, re, sys, uuid, zipfile
from xml.sax.saxutils import escape

DS = "federated.sistperf0marks0long"
COLS = [("Student_ID", "string"), ("Academic_Year", "string"), ("Term", "string"), ("Semester", "integer"), ("Semester_Label", "string"),
        ("Subject_Code", "string"), ("Subject", "string"), ("Assessment", "string"), ("Assessment_Order", "integer"), ("Marks", "real"),
        ("Maximum_Marks", "real"), ("Max_Is_Assumed", "integer"), ("ERP_Total", "real"), ("Result", "string"), ("Credits", "real"), ("Fetched_On", "string")]
BASE = {n: t for n, t in COLS}
DIMS = {"Student_ID", "Academic_Year", "Term", "Semester", "Semester_Label", "Subject_Code", "Subject", "Assessment", "Assessment_Order", "Max_Is_Assumed", "Result", "Fetched_On"}
K = "[Student_ID],[Semester],[Subject_Code]"
FIX = "{FIXED " + K + " : "

# name, datatype, role, type, default-format, formula ({{Name}} = another calculated field)
CALCS = [
    ("Pct", "real", "measure", "quantitative", "p0.0%", "[Marks] / [Maximum_Marks]"),
    ("Is Centum", "integer", "measure", "quantitative", "", "IF [Marks] = [Maximum_Marks] THEN 1 ELSE 0 END"),
    ("Assessment Label", "string", "dimension", "nominal", "", 'STR([Assessment_Order]) + ". " + [Assessment]'),
    ("Max Source", "string", "dimension", "nominal", "", 'IF [Max_Is_Assumed] = 1 THEN "Assumed" ELSE "From curriculum / ERP" END'),
    ("Total Marks", "real", "measure", "quantitative", "", FIX + 'SUM(IF [Assessment] = "Internal" OR [Assessment] = "Exam" THEN [Marks] END)}'),
    ("Total Max", "real", "measure", "quantitative", "", FIX + 'SUM(IF [Assessment] = "Internal" OR [Assessment] = "Exam" THEN [Maximum_Marks] END)}'),
    ("Subject Total %", "real", "measure", "quantitative", "p0.0%", "{{Total Marks}} / {{Total Max}}"),
    ("Exam %", "real", "measure", "quantitative", "p0.0%",
     FIX + 'SUM(IF [Assessment] = "Exam" THEN [Marks] END)} / ' + FIX + 'SUM(IF [Assessment] = "Exam" THEN [Maximum_Marks] END)}'),
    ("Has Exam", "integer", "measure", "quantitative", "", FIX + 'MAX(IF [Assessment] = "Exam" THEN 1 ELSE 0 END)}'),
    ("Grade", "string", "dimension", "nominal", "",
     'IF {{Has Exam}} = 0 THEN "Pending"\nELSEIF {{Exam %}} < 0.3 OR {{Subject Total %}} < 0.5 THEN "RA"\nELSEIF {{Subject Total %}} >= 0.9 THEN "A++"\n'
     'ELSEIF {{Subject Total %}} >= 0.8 THEN "A+"\nELSEIF {{Subject Total %}} >= 0.7 THEN "B++"\nELSEIF {{Subject Total %}} >= 0.6 THEN "B+"\nELSE "C" END'),
    ("Grade Points", "integer", "measure", "quantitative", "",
     'CASE {{Grade}} WHEN "A++" THEN 10 WHEN "A+" THEN 9 WHEN "B++" THEN 8 WHEN "B+" THEN 7 WHEN "C" THEN 6 ELSE 0 END'),
    ("Credit Points", "real", "measure", "quantitative", "",
     'IF [Assessment] = "Exam" AND {{Grade}} <> "RA" AND {{Grade}} <> "Pending" THEN {{Grade Points}} * [Credits] END'),
    ("Credits Cleared", "real", "measure", "quantitative", "",
     'IF [Assessment] = "Exam" AND {{Grade}} <> "RA" AND {{Grade}} <> "Pending" THEN [Credits] END'),
    ("SGPA", "real", "measure", "quantitative", "0.00", "SUM({{Credit Points}}) / SUM({{Credits Cleared}})"),
    ("CGPA", "real", "measure", "quantitative", "0.00",
     "{FIXED [Student_ID] : SUM({{Credit Points}})} / {FIXED [Student_ID] : SUM({{Credits Cleared}})}"),
    ("Arrear", "integer", "measure", "quantitative", "", 'IF [Assessment] = "Exam" AND {{Grade}} = "RA" THEN 1 ELSE 0 END'),
    ("CAE 1 Pct", "real", "measure", "quantitative", "p0.0%", 'IF [Assessment] = "CAE 1" THEN {{Pct}} END'),
    ("CAE 2 Pct", "real", "measure", "quantitative", "p0.0%", 'IF [Assessment] = "CAE 2" THEN {{Pct}} END'),
    ("CAE Improvement", "real", "measure", "quantitative", "p0.0%", "AVG({{CAE 2 Pct}}) - AVG({{CAE 1 Pct}})"),
    ("Semesters Completed", "integer", "measure", "quantitative", "", 'COUNTD(IF [Assessment] = "Exam" THEN [Semester] END)'),
]
AGG_CALCS = {"SGPA", "CAE Improvement", "Semesters Completed"}        # aggregate calculations are used as-is (derivation User)
CID = {n: f"Calculation_{1000000000000 + i * 7919}" for i, (n, *_r) in enumerate(CALCS)}
CALC = {c[0]: c for c in CALCS}

def sid():
    return "<simple-id uuid='{" + str(uuid.uuid4()).upper() + "}' />"

def q(s):
    return escape(s, {"'": "&apos;", '"': "&quot;"})

def formula(name):
    f = CALC[name][5]
    return re.sub(r"\{\{(.+?)\}\}", lambda m: f"[{CID[m.group(1)]}]", f)

def deps_of(name, seen=None):
    seen = seen if seen is not None else []
    for m in re.findall(r"\{\{(.+?)\}\}", CALC[name][5]):
        if m not in seen:
            seen.append(m); deps_of(m, seen)
    return seen

def base_refs(name):
    return {m for m in re.findall(r"\[([A-Za-z_]+)\]", CALC[name][5]) if m in BASE}

# ---- pills -------------------------------------------------------------------------------------------------------
DER = {"none": "None", "sum": "Sum", "avg": "Avg", "cntd": "CountD", "cnt": "Count", "stdev": "Stdev", "usr": "User"}

class Pill:
    def __init__(self, field, fn="none"):
        self.field, self.fn = field, fn
        self.calc = field in CALC
        if self.calc and fn == "none" and field in AGG_CALCS:
            self.fn = "usr"
        if fn == "none" and not self.calc and BASE.get(field) == "integer" and field in DIMS:
            self.kind = "ok"
        elif self.fn in ("none",):
            self.kind = "nk"
        else:
            self.kind = "qk"
        self.col = CID[field] if self.calc else field

    @property
    def inst(self):
        return f"{self.fn}:{self.col}:{self.kind}"

    @property
    def ref(self):
        return f"[{DS}].[{self.inst}]"

    def inst_xml(self):
        t = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}[self.kind]
        return f"<column-instance column='[{self.col}]' derivation='{DER[self.fn]}' name='[{self.inst}]' pivot='key' type='{t}' />"

def D(f): return Pill(f, "none")
def S(f): return Pill(f, "sum")
def A(f): return Pill(f, "avg")
def CD(f): return Pill(f, "cntd")
def SD(f): return Pill(f, "stdev")

def members_filter(field, values):
    p = D(field)
    mem = "".join(f"<groupfilter function='member' level='[{p.inst}]' member='&quot;{q(v)}&quot;' />" for v in values)
    inner = mem if len(values) == 1 else f"<groupfilter function='union' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate'>{mem}</groupfilter>"
    if len(values) == 1:
        inner = inner.replace("<groupfilter function='member'", "<groupfilter function='member' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate'")
    return p, f"<filter class='categorical' column='[{DS}].[{p.inst}]'>{inner}</filter>"

# ---- worksheet ----------------------------------------------------------------------------------------------------
def shelf(pills):
    if not pills:
        return ""
    r = " / ".join(p.ref for p in pills)
    return r if len(pills) == 1 else f"({r})"

def sheet(name, title, mark, rows=(), cols=(), color=None, text=None, filters=(), labels=False, student=None, size=None):
    rows, cols = list(rows), list(cols)
    pills = rows + cols + ([color] if color else []) + ([text] if text else [])
    flt = list(filters)
    if student:
        p, x = members_filter("Student_ID", [student]); flt.append((p, x))
    pills += [p for p, _ in flt]
    used_calc, used_base = [], set()
    def add_calc(n):
        for d in reversed(deps_of(n)):
            if d not in used_calc: used_calc.append(d)
        if n not in used_calc: used_calc.append(n)
        used_base.update(base_refs(n))
        for d in deps_of(n): used_base.update(base_refs(d))
    insts = {}
    for p in pills:
        insts[p.inst] = p
        if p.calc: add_calc(p.field)
        else: used_base.add(p.field)
    cols_xml = []
    for b in sorted(used_base):
        role = "dimension" if b in DIMS else "measure"
        typ = "nominal" if BASE[b] == "string" else ("ordinal" if b in DIMS else "quantitative")
        cols_xml.append(f"<column datatype='{BASE[b]}' name='[{b}]' role='{role}' type='{typ}' />")
    for n in used_calc:
        _, dt, role, typ, fmt, _f = CALC[n]
        cols_xml.append(f"<column caption='{q(n)}' datatype='{dt}' name='[{CID[n]}]' role='{role}' type='{typ}'"
                        + (f" default-format='{fmt}'" if fmt else "") + f"><calculation class='tableau' formula='{q(formula(n))}' /></column>")
    enc = ""
    if color: enc += f"<color column='{color.ref}' />"
    if text: enc += f"<text column='{text.ref}' />"
    style = "<style><style-rule element='mark'><format attr='mark-labels-show' value='true' /><format attr='mark-labels-cull' value='true' /></style-rule></style>" if labels else ""
    return f"""<worksheet name='{q(name)}'>
      <layout-options><title><formatted-text><run>{q(title)}</run></formatted-text></title></layout-options>
      <table>
        <view>
          <datasources><datasource caption='marks_long' name='{DS}' /></datasources>
          <datasource-dependencies datasource='{DS}'>
            {''.join(cols_xml)}
            {''.join(p.inst_xml() for p in insts.values())}
          </datasource-dependencies>
          {''.join(x for _, x in flt)}
          <aggregation value='true' />
        </view>
        <style />
        <panes><pane selection-relaxation-option='selection-relaxation-allow'>
          <view><breakdown value='auto' /></view>
          <mark class='{mark}' />
          {'<encodings>' + enc + '</encodings>' if enc else ''}
          {style}
        </pane></panes>
        <rows>{shelf(rows)}</rows>
        <cols>{shelf(cols)}</cols>
      </table>
      {sid()}
    </worksheet>"""

def window_ws(name):
    return f"""<window class='worksheet' name='{q(name)}'><cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge>
      <edge name='top'><strip size='2147483647'><card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip><strip size='30'><card type='title' /></strip></edge></cards>{sid()}</window>"""

# ---- dashboards ---------------------------------------------------------------------------------------------------
class Dash:
    def __init__(self, name, w=1400, h=1000):
        self.name, self.w, self.h, self.zones, self.n = name, w, h, [], 10

    def _pos(self, x, y, w, h):
        return f"x='{round(x / self.w * 100000)}' y='{round(y / self.h * 100000)}' w='{round(w / self.w * 100000)}' h='{round(h / self.h * 100000)}'"

    def sheet(self, name, x, y, w, h):
        self.n += 1
        self.zones.append(f"<zone id='{self.n}' name='{q(name)}' {self._pos(x, y, w, h)}><zone-style><format attr='border-style' value='none' /><format attr='margin' value='4' /></zone-style></zone>")
        return self

    def text(self, txt, x, y, w, h, size=14, bold=False, color="#1F1F1F"):
        self.n += 1
        self.zones.append(f"<zone id='{self.n}' type-v2='text' {self._pos(x, y, w, h)}><formatted-text><run{' bold=' + chr(39) + 'true' + chr(39) if bold else ''} fontcolor='{color}' fontsize='{size}'>{q(txt)}</run></formatted-text>"
                          f"<zone-style><format attr='border-style' value='none' /><format attr='margin' value='4' /></zone-style></zone>")
        return self

    def xml(self):
        return f"""<dashboard name='{q(self.name)}'>
      <style><style-rule element='dashboard'><format attr='background-color' value='#F2F2F3' /></style-rule></style>
      <size maxheight='{self.h}' maxwidth='{self.w}' minheight='{self.h}' minwidth='{self.w}' />
      <zones><zone id='4' type-v2='layout-basic' x='0' y='0' w='100000' h='100000'>{''.join(self.zones)}
        <zone-style><format attr='border-style' value='none' /><format attr='margin' value='8' /></zone-style></zone></zones>
      {sid()}
    </dashboard>"""

    def window(self):
        names = re.findall(r"name='([^']+)' x=", "".join(self.zones))
        vps = "".join(f"<viewpoint name='{n}' />" for n in names)
        return f"<window class='dashboard' name='{q(self.name)}'><viewpoints>{vps}</viewpoints><active id='-1' />{sid()}</window>"

# ---- the workbook ---------------------------------------------------------------------------------------------------
def build(csv_path, out_path, student=None, extract_path="Data/Extracts/marks_long.hyper", n_rows=0):
    directory, filename = os.path.dirname(csv_path).replace("\\", "/"), os.path.basename(csv_path)
    F = lambda **k: dict(student=student, **k)
    ce = members_filter("Assessment", ["CAE 1", "CAE 2"]); ie = members_filter("Assessment", ["Internal", "Exam"]); ex = members_filter("Assessment", ["Exam"])
    sheets = [
        sheet("KPI Overall Average", "Overall average", "Text", text=A("Pct"), labels=True, **F()),
        sheet("KPI CGPA", "CGPA", "Text", text=A("CGPA"), labels=True, **F()),
        sheet("KPI Centums", "Centums", "Text", text=S("Is Centum"), labels=True, **F()),
        sheet("KPI Arrears", "Arrears (RA)", "Text", text=S("Arrear"), labels=True, **F()),
        sheet("KPI Subjects", "Subjects", "Text", text=CD("Subject_Code"), labels=True, **F()),
        sheet("KPI Semesters", "Semesters completed", "Text", text=D("Semesters Completed"), labels=True, **F()),
        sheet("Score Progress", "Score progress by semester", "Line", rows=[A("Pct")], cols=[D("Semester_Label")], color=D("Assessment Label"), **F()),
        sheet("CAE 1 vs CAE 2", "CAE 1 vs CAE 2 by subject", "Bar", rows=[A("Pct")], cols=[D("Subject")], color=D("Assessment Label"), filters=[ce], labels=True, **F()),
        sheet("Semester Performance", "Internal vs Exam by semester", "Bar", rows=[A("Pct")], cols=[D("Semester_Label")], color=D("Assessment Label"), filters=[ie], labels=True, **F()),
        sheet("Subject Heatmap", "Subject performance heatmap", "Square", rows=[D("Subject")], cols=[D("Assessment Label")], color=A("Pct"), text=A("Pct"), labels=True, **F()),
        sheet("Internal vs Exam by Subject", "Internal vs Exam by subject", "Bar", rows=[D("Subject")], cols=[A("Pct")], color=D("Assessment Label"), filters=[ie], labels=True, **F()),
        sheet("Grade Distribution", "Grade distribution", "Bar", rows=[CD("Subject_Code")], cols=[D("Grade")], filters=[ex], labels=True, **F()),
        sheet("SGPA by Semester", "SGPA by semester", "Bar", rows=[D("SGPA")], cols=[D("Semester_Label")], labels=True, **F()),
        sheet("CAE Improvement", "CAE improvement (CAE 2 - CAE 1)", "Bar", rows=[D("Subject")], cols=[D("CAE Improvement")], filters=[ce], labels=True, **F()),
        sheet("Subject Consistency", "Subject consistency (std. deviation of %)", "Bar", rows=[D("Subject")], cols=[SD("Pct")], labels=True, **F()),
        sheet("Results Table", "Marks by subject and assessment", "Text", rows=[D("Semester_Label"), D("Subject"), D("Grade")], cols=[D("Assessment Label")], text=S("Marks"), **F()),
        sheet("ERP Results", "ERP result per subject", "Text", rows=[D("Semester_Label"), D("Subject"), D("Result")], text=A("ERP_Total"), filters=[ex], **F()),
        sheet("DQ Assumed Max", "Maximum marks: assumed vs from curriculum / ERP", "Bar", rows=[CD("Subject_Code")], cols=[D("Max Source"), D("Assessment")], **F()),
    ]
    dashes = []
    h = Dash("Home", 1400, 1180).text("SistPerf - Academic performance", 20, 12, 800, 44, 24, True)
    for i, k in enumerate(["KPI Overall Average", "KPI CGPA", "KPI Centums", "KPI Arrears", "KPI Subjects", "KPI Semesters"]):
        h.sheet(k, 20 + i * 228, 64, 220, 110)
    h.sheet("Score Progress", 20, 190, 680, 330).sheet("CAE 1 vs CAE 2", 710, 190, 670, 330)
    h.sheet("Subject Heatmap", 20, 535, 680, 620).sheet("Semester Performance", 710, 535, 670, 300).sheet("Grade Distribution", 710, 850, 670, 305)
    dashes.append(h)
    dashes.append(Dash("Assessment Analysis", 1400, 900).text("Assessment analysis", 20, 12, 800, 44, 24, True)
                  .sheet("CAE 1 vs CAE 2", 20, 64, 680, 400).sheet("CAE Improvement", 710, 64, 670, 400)
                  .sheet("Internal vs Exam by Subject", 20, 480, 680, 400).sheet("Score Progress", 710, 480, 670, 400))
    dashes.append(Dash("Subject Analysis", 1400, 900).text("Subject analysis", 20, 12, 800, 44, 24, True)
                  .sheet("Subject Heatmap", 20, 64, 680, 816).sheet("Subject Consistency", 710, 64, 670, 400).sheet("Internal vs Exam by Subject", 710, 480, 670, 400))
    dashes.append(Dash("Semester Analysis", 1400, 800).text("Semester analysis", 20, 12, 800, 44, 24, True)
                  .sheet("SGPA by Semester", 20, 64, 680, 350).sheet("Semester Performance", 710, 64, 670, 350)
                  .sheet("Score Progress", 20, 430, 680, 350).sheet("Grade Distribution", 710, 430, 670, 350))
    dashes.append(Dash("Detailed Marks", 1400, 1100).text("Detailed marks", 20, 12, 800, 44, 24, True)
                  .sheet("Results Table", 20, 64, 900, 1020).sheet("ERP Results", 930, 64, 450, 1020))
    dashes.append(Dash("Data Quality", 1400, 500).text("Data quality: how many marks use an assumed maximum", 20, 12, 1200, 44, 20, True)
                  .sheet("DQ Assumed Max", 20, 64, 1360, 420))
    cols_rel = "".join(f"<column datatype='{t}' name='{n}' ordinal='{i}' />" for i, (n, t) in enumerate(COLS))
    rt = {"string": "129", "integer": "20", "real": "5"}
    meta = "".join(f"<metadata-record class='column'><remote-name>{n}</remote-name><remote-type>{rt[t]}</remote-type><local-name>[{n}]</local-name>"
                   f"<parent-name>[{filename}]</parent-name><remote-alias>{n}</remote-alias><ordinal>{i}</ordinal><local-type>{t}</local-type>"
                   f"<aggregation>{'Sum' if t != 'string' else 'Count'}</aggregation><contains-null>true</contains-null></metadata-record>" for i, (n, t) in enumerate(COLS))
    base_cols = "".join(f"<column datatype='{t}' name='[{n}]' role='{'dimension' if n in DIMS else 'measure'}' type='{'nominal' if t == 'string' else ('ordinal' if n in DIMS else 'quantitative')}' />" for n, t in COLS)
    calc_cols = "".join(f"<column caption='{q(n)}' datatype='{dt}' name='[{CID[n]}]' role='{role}' type='{typ}'" + (f" default-format='{fmt}'" if fmt else "")
                        + f"><calculation class='tableau' formula='{q(formula(n))}' /></column>" for n, dt, role, typ, fmt, _f in CALCS)
    stamp = datetime.datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
    ex_meta = "".join(f"<metadata-record class='column'><remote-name>{n}</remote-name><remote-type>{rt[t]}</remote-type><local-name>[{n}]</local-name>"
                      f"<parent-name>[Extract]</parent-name><remote-alias>{n}</remote-alias><ordinal>{i}</ordinal><local-type>{t}</local-type>"
                      f"<aggregation>{'Sum' if t != 'string' else 'Count'}</aggregation><contains-null>true</contains-null>"
                      + ("<collation flag='1' name='LEN_RUS_S2' />" if t == "string" else "") + "</metadata-record>" for i, (n, t) in enumerate(COLS))
    stamp_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000")
    extract = (f"<extract count='-1' enabled='true' units='records'><connection access_mode='readonly' authentication='auth-none' author-locale='en_US' "
               f"class='hyper' dbname='{q(extract_path)}' default-settings='yes' schema='Extract' sslmode='' tablename='Extract' update-time='{stamp}' username='tableau_internal_user'>"
               f"<relation name='Extract' table='[Extract].[Extract]' type='table' />"
               f"<refresh increment-key='' incremental-updates='false'><refresh-event add-from-file-path='{q(filename)}' increment-value='%null%' refresh-type='create' "
               f"rows-inserted='{n_rows}' timestamp-start='{stamp_iso}' /></refresh>"
               f"<metadata-records>{ex_meta}</metadata-records></connection></extract>")
    xml = f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook original-version='18.1' source-build='2023.1.0 (20231.23.0309.1450)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest><SheetIdentifierTracking /><WindowsPersistSimpleIdentifiers /></document-format-change-manifest>
  <preferences><preference name='ui.encoding.shelf.height' value='24' /><preference name='ui.shelf.height' value='26' /></preferences>
  <datasources>
    <datasource caption='marks_long' inline='true' name='{DS}' version='18.1'>
      <connection class='federated'>
        <named-connections><named-connection caption='{q(directory)}' name='textscan.sistperf0marks0long'>
          <connection class='textscan' directory='{q(directory)}' filename='{q(filename)}' password='' server='' />
        </named-connection></named-connections>
        <relation connection='textscan.sistperf0marks0long' name='{q(filename)}' table='[{q(filename.replace('.', '#'))}]' type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>{cols_rel}</columns>
        </relation>
        <metadata-records>{meta}</metadata-records>
      </connection>
      <aliases enabled='yes' />
      {base_cols}{calc_cols}
      {extract}
    </datasource>
  </datasources>
  <worksheets>{''.join(sheets)}</worksheets>
  <dashboards>{''.join(d.xml() for d in dashes)}</dashboards>
  <windows source-height='30'>{''.join(d.window() for d in dashes)}{''.join(window_ws(re.search(r"name='([^']+)'", s).group(1)) for s in sheets)}</windows>
</workbook>"""
    open(out_path, "w", encoding="utf-8").write(xml)
    return out_path

def make_hyper(csv_path, hyper_path):
    import pandas as pd
    from tableauhyperapi import HyperProcess, Telemetry, Connection, CreateMode, TableDefinition, SqlType, TableName, Inserter
    df = pd.read_csv(csv_path)
    sql = {"string": SqlType.text(), "integer": SqlType.big_int(), "real": SqlType.double()}
    table = TableDefinition(TableName("Extract", "Extract"), [TableDefinition.Column(n, sql[t]) for n, t in COLS])
    def val(v, t):
        if pd.isna(v): return None
        return str(v) if t == "string" else (int(v) if t == "integer" else float(v))
    rows = [[val(r[n], t) for n, t in COLS] for r in df.to_dict("records")]
    if os.path.exists(hyper_path): os.remove(hyper_path)
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with Connection(hp.endpoint, hyper_path, CreateMode.CREATE_AND_REPLACE) as con:
            con.catalog.create_schema("Extract"); con.catalog.create_table(table)
            with Inserter(con, table) as ins:
                ins.add_rows(rows); ins.execute()
    return len(rows)

def package(csv_path, twbx_path, student=None):
    """Tableau Public only accepts workbooks that use extracts, so ship the .twb with its .hyper extract inside a .twbx."""
    tmp_dir = os.path.join(os.path.dirname(twbx_path) or ".", ".build"); os.makedirs(tmp_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(twbx_path))[0]
    twb, hyper = os.path.join(tmp_dir, base + ".twb"), os.path.join(tmp_dir, "marks_long.hyper")
    n = make_hyper(csv_path, hyper)
    build(csv_path, twb, student=student, extract_path="Data/Extracts/marks_long.hyper", n_rows=n)
    with zipfile.ZipFile(twbx_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(twb, base + ".twb"); z.write(hyper, "Data/Extracts/marks_long.hyper")
    for f in (twb, hyper): os.remove(f)
    os.rmdir(tmp_dir)
    return twbx_path, n

def main():
    root = os.getcwd()
    demo = os.path.join(root, "tableau", "sample_data", "marks_long.csv")
    os.makedirs("tableau", exist_ok=True)
    if os.path.exists(demo):
        print("Wrote %s (%d rows in the extract)" % package(demo, "tableau/SistPerf_Demo.twbx", student="STU001"))
    live = os.path.join(root, "data", "private", "tableau", "marks_long.csv")
    if os.path.exists(live):
        print("Wrote %s (%d rows in the extract)" % package(live, "tableau/SistPerf_Live.twbx"))
    else:
        print("No real data yet. Run: python -m tracker.tracker --adapter browser --export-tableau   then run this script again.")

if __name__ == "__main__":
    main()
