"""Small library that writes Tableau workbook XML (.twb) and packages it with its data extracts (.twbx).
Structures follow real Tableau-written files (manifest flags, extract, filters, parameters, legends, entire-view fit)."""
import datetime, json, os, re, shutil, uuid, zipfile
from xml.sax.saxutils import escape

RT = {"string": "129", "integer": "20", "real": "5"}
DER = {"none": "None", "sum": "Sum", "avg": "Avg", "cntd": "CountD", "cnt": "Count", "stdev": "Stdev", "min": "Min", "max": "Max", "usr": "User"}
PARAMS = {}
_CALC_N = [0]

def q(s):
    return escape(str(s), {"'": "&apos;", '"': "&quot;"})

def sid():
    return "<simple-id uuid='{" + str(uuid.uuid4()).upper() + "}' />"

# ------------------------------------------------------------------------------------------------ parameters
class Param:
    def __init__(self, key, caption, dt, value, lo=None, hi=None, step=1, members=None):
        self.key, self.caption, self.dt, self.value, self.lo, self.hi, self.step, self.members = key, caption, dt, value, lo, hi, step, members
        self.name = f"Parameter {len(PARAMS) + 1}"
        PARAMS[key] = self

    @property
    def ref(self):
        return f"[Parameters].[{self.name}]"

    def lit(self, v):
        return f'"{v}"' if self.dt == "string" else str(v)

    def xml(self):
        v = self.lit(self.value)
        if self.members:
            body = '<members>' + ''.join(f"<member value='{q(self.lit(m))}' />" for m in self.members) + '</members>'
            return (f"<column caption='{q(self.caption)}' datatype='{self.dt}' name='[{self.name}]' param-domain-type='list' role='measure' type='nominal' "
                    f"value='{q(v)}'><calculation class='tableau' formula='{q(v)}' />{body}</column>")
        return (f"<column caption='{q(self.caption)}' datatype='{self.dt}' name='[{self.name}]' param-domain-type='range' role='measure' type='quantitative' "
                f"value='{v}'><calculation class='tableau' formula='{v}' /><range granularity='{self.step}' max='{self.hi}' min='{self.lo}' /></column>")

# ------------------------------------------------------------------------------------------------ data sources
class Calc:
    def __init__(self, name, dt, role, typ, fmt, formula, agg=False, tc=False):
        self.name, self.dt, self.role, self.typ, self.fmt, self.formula, self.agg, self.tc = name, dt, role, typ, fmt, formula, agg, tc
        _CALC_N[0] += 1
        self.cid = f"Calculation_{1000000000000 + _CALC_N[0] * 7919}"

class Source:
    def __init__(self, key, csv_name, cols, dims):
        self.key, self.csv, self.cols, self.dims = key, csv_name, cols, set(dims)
        self.types = dict(cols)
        self.ds = f"federated.sistperf0{key}"
        self.conn = f"textscan.sistperf0{key}"
        self.calcs = {}

    def calc(self, name, dt, role, typ, fmt, formula, agg=False, tc=False):
        self.calcs[name] = Calc(name, dt, role, typ, fmt, formula, agg, tc)

    def dim(self, name, dt, formula):                 # discrete dimension
        self.calc(name, dt, "dimension", "ordinal" if dt == "integer" else "nominal", "", formula)

    def row(self, name, dt, formula, fmt=""):         # row-level or LOD measure
        self.calc(name, dt, "measure", "quantitative", fmt, formula)

    def agg(self, name, dt, formula, fmt="", tc=False):
        self.calc(name, dt, "measure", "quantitative", fmt, formula, agg=True, tc=tc)

    def formula(self, name):
        def sub(m):
            t = m.group(1)
            return PARAMS[t[2:]].ref if t.startswith("P:") else f"[{self.calcs[t].cid}]"
        return re.sub(r"\{\{(.+?)\}\}", sub, self.calcs[name].formula)

    def deps(self, name, seen=None):
        seen = seen if seen is not None else []
        for m in re.findall(r"\{\{(?!P:)(.+?)\}\}", self.calcs[name].formula):
            if m not in seen:
                seen.append(m); self.deps(m, seen)
        return seen

    def base_refs(self, name):
        return {m for m in re.findall(r"\[([A-Za-z_0-9]+)\]", self.calcs[name].formula) if m in self.types}

    def param_refs(self, name):
        return {m[2:] for n in [name] + self.deps(name) for m in re.findall(r"\{\{(P:.+?)\}\}", self.calcs[n].formula)}

    def base_col(self, n):
        t = self.types[n]
        role = "dimension" if n in self.dims else "measure"
        typ = "nominal" if t == "string" else ("ordinal" if n in self.dims else "quantitative")
        return f"<column datatype='{t}' name='[{n}]' role='{role}' type='{typ}' />"

    def calc_col(self, n):
        c = self.calcs[n]
        return (f"<column caption='{q(n)}' datatype='{c.dt}'" + (f" default-format='{c.fmt}'" if c.fmt else "") +
                f" name='[{c.cid}]' role='{c.role}' type='{c.typ}'><calculation class='tableau' formula='{q(self.formula(n))}' /></column>")

    def xml(self, csv_path, extract_path, n_rows):
        directory, filename = os.path.dirname(csv_path).replace("\\", "/"), os.path.basename(csv_path)
        rel = "".join(f"<column datatype='{t}' name='{n}' ordinal='{i}' />" for i, (n, t) in enumerate(self.cols))
        agg = lambda t: "Sum" if t != "string" else "Count"
        meta = "".join(f"<metadata-record class='column'><remote-name>{n}</remote-name><remote-type>{RT[t]}</remote-type><local-name>[{n}]</local-name>"
                       f"<parent-name>[{filename}]</parent-name><remote-alias>{n}</remote-alias><ordinal>{i}</ordinal><local-type>{t}</local-type>"
                       f"<aggregation>{agg(t)}</aggregation><contains-null>true</contains-null></metadata-record>" for i, (n, t) in enumerate(self.cols))
        emeta = "".join(f"<metadata-record class='column'><remote-name>{n}</remote-name><remote-type>{RT[t]}</remote-type><local-name>[{n}]</local-name>"
                        f"<parent-name>[Extract]</parent-name><remote-alias>{n}</remote-alias><ordinal>{i}</ordinal><local-type>{t}</local-type>"
                        f"<aggregation>{agg(t)}</aggregation><contains-null>true</contains-null>"
                        + ("<collation flag='1' name='LEN_RUS_S2' />" if t == "string" else "") + "</metadata-record>" for i, (n, t) in enumerate(self.cols))
        now = datetime.datetime.now()
        extract = (f"<extract count='-1' enabled='true' units='records'><connection access_mode='readonly' authentication='auth-none' author-locale='en_US' "
                   f"class='hyper' dbname='{q(extract_path)}' default-settings='yes' schema='Extract' sslmode='' tablename='Extract' "
                   f"update-time='{now.strftime('%m/%d/%Y %I:%M:%S %p')}' username='tableau_internal_user'><relation name='Extract' table='[Extract].[Extract]' type='table' />"
                   f"<refresh increment-key='' incremental-updates='false'><refresh-event add-from-file-path='{q(filename)}' increment-value='%null%' refresh-type='create' "
                   f"rows-inserted='{n_rows}' timestamp-start='{now.strftime('%Y-%m-%d %H:%M:%S.000')}' /></refresh>"
                   f"<metadata-records>{emeta}</metadata-records></connection></extract>")
        return f"""<datasource caption='{q(self.key)}' inline='true' name='{self.ds}' version='18.1'>
      <connection class='federated'>
        <named-connections><named-connection caption='{q(directory)}' name='{self.conn}'>
          <connection class='textscan' directory='{q(directory)}' filename='{q(filename)}' password='' server='' />
        </named-connection></named-connections>
        <relation connection='{self.conn}' name='{q(filename)}' table='[{q(filename.replace('.', '#'))}]' type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>{rel}</columns>
        </relation>
        <metadata-records>{meta}</metadata-records>
      </connection>
      <aliases enabled='yes' />
      {''.join(self.base_col(n) for n, _t in self.cols)}{''.join(self.calc_col(n) for n in self.calcs)}
      {extract}
    </datasource>"""

# ------------------------------------------------------------------------------------------------ pills / filters / sorts
class Pill:
    def __init__(self, src, field, fn="none", kind=None):
        self.src, self.field, self.fn = src, field, fn
        self.calc = src.calcs.get(field)
        if self.calc is not None:
            if self.calc.agg and fn == "none":
                self.fn = "usr"
            elif self.calc.role == "dimension":
                self.fn = "none"
        self.col = self.calc.cid if self.calc else field
        dt = self.calc.dt if self.calc else src.types[field]
        discrete_dim = (self.calc.role == "dimension") if self.calc else (field in src.dims)
        if kind:
            self.kind = kind
        elif self.fn == "none" and (discrete_dim or dt == "string"):
            self.kind = "ok" if dt == "integer" else "nk"
        elif self.fn == "usr" and dt == "string":
            self.kind = "nk"
        else:
            self.kind = "qk"
        self.tc = bool(self.calc and self.calc.tc)

    @property
    def inst(self):
        return f"{self.fn}:{self.col}:{self.kind}"

    @property
    def ref(self):
        return f"[{self.src.ds}].[{self.inst}]"

    def inst_xml(self):
        t = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}[self.kind]
        head = f"<column-instance column='[{self.col}]' derivation='{DER[self.fn]}' name='[{self.inst}]' pivot='key' type='{t}'"
        return head + (">" + "<table-calc ordering-type='Columns' />" + "</column-instance>" if self.tc else " />")

def members(src, field, values, group=None):
    p = Pill(src, field)
    def lit(v):
        return f"&quot;{q(v)}&quot;" if isinstance(v, str) else str(v)
    mem = "".join(f"<groupfilter function='member' level='[{p.inst}]' member='{lit(v)}' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />" if len(values) == 1
                  else f"<groupfilter function='member' level='[{p.inst}]' member='{lit(v)}' />" for v in values)
    inner = mem if len(values) == 1 else f"<groupfilter function='union' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate'>{mem}</groupfilter>"
    return p, f"<filter class='categorical' column='[{src.ds}].[{p.inst}]'>{inner}</filter>"

def all_values(src, field, group):
    p = Pill(src, field)
    return p, (f"<filter class='categorical' column='[{src.ds}].[{p.inst}]' filter-group='{group}'><groupfilter function='level-members' level='[{p.inst}]' "
               f"user:ui-enumeration='all' user:ui-marker='enumerate' /></filter>")

# ------------------------------------------------------------------------------------------------ worksheets
TITLE_COLOR = "#1F1F1F"

class Sheet:
    def __init__(self, src, name, title, mark, rows=(), cols=(), color=None, text=None, detail=(), filters=(), sorts=(), labels=False, mark_color=None,
                 palette=None, hide_axes=(), font=10, grid=False, student=None, actions=False, legend=False):
        self.src, self.name, self.title, self.mark = src, name, title, mark
        self.rows, self.cols, self.color, self.text, self.detail = list(rows), list(cols), color, text, list(detail)
        self.filters, self.sorts, self.labels, self.mark_color, self.palette = list(filters), list(sorts), labels, mark_color, palette
        self.hide_axes, self.font, self.grid, self.actions, self.legend = list(hide_axes), font, grid, actions, legend
        if student:
            self.filters.append(members(src, "Student_ID", [student]))

    def xml(self):
        s = self.src
        pills = self.rows + self.cols + self.detail + [p for p in (self.color, self.text) if p] + [f[0] for f in self.filters] + [x[0] for x in self.sorts] + [x[1] for x in self.sorts]
        used, base, params = [], set(), set()
        insts = {}
        for p in pills:
            insts[p.inst] = p
            if p.calc is not None:
                for d in reversed(s.deps(p.field)):
                    if d not in used: used.append(d)
                if p.field not in used: used.append(p.field)
            else:
                base.add(p.field)
        for n in used:
            base |= s.base_refs(n); params |= s.param_refs(n)
        cols_xml = "".join(s.base_col(b) for b in sorted(base)) + "".join(s.calc_col(n) for n in used)
        dep = f"<datasource-dependencies datasource='{s.ds}'>{cols_xml}{''.join(p.inst_xml() for p in insts.values())}</datasource-dependencies>"
        ds_list = f"<datasource caption='{q(s.key)}' name='{s.ds}' />"
        if params:
            ds_list = "<datasource name='Parameters' />" + ds_list
            dep = "<datasource-dependencies datasource='Parameters'>" + "".join(PARAMS[k].xml() for k in sorted(params)) + "</datasource-dependencies>" + dep
        enc = "".join([f"<color column='{self.color.ref}' />" if self.color else "", f"<text column='{self.text.ref}' />" if self.text else "",
                       "".join(f"<lod column='{d.ref}' />" for d in self.detail)])
        sorts = "".join(f"<computed-sort column='{d.ref}' direction='{dr}' using='{u.ref}' />" for d, u, dr in self.sorts)
        # pane style: marks (palette encoding first, then formats, as in real files)
        enc_rule = ""
        if self.palette:
            buckets = "".join(f"<map to='{c}'><bucket>&quot;{q(v)}&quot;</bucket></map>" for v, c in self.palette)
            enc_rule = f"<encoding attr='color' field='[{self.color.inst}]' type='palette'>{buckets}</encoding>"
        mrule = enc_rule + f"<format attr='mark-labels-cull' value='true' /><format attr='mark-labels-show' value='{'true' if self.labels else 'false'}' />"
        if self.mark_color:
            mrule += f"<format attr='mark-color' value='{self.mark_color}' />"
        pane_style = f"<style><style-rule element='mark'>{mrule}</style-rule></style>"
        # sheet style
        axes = "".join(f"<format attr='display' class='0' field='{p.ref}' scope='{'cols' if any(p.inst == c.inst for c in self.cols) else 'rows'}' value='false' />" for p in self.hide_axes)
        sheet_style = (f"<style><style-rule element='worksheet'><format attr='display-field-labels' scope='cols' value='false' /><format attr='display-field-labels' scope='rows' value='false' />"
                       f"<format attr='font-size' value='{self.font}' /><format attr='color' value='{TITLE_COLOR}' /></style-rule>"
                       + ("" if self.grid else "<style-rule element='table-div'><format attr='line-visibility' scope='cols' value='off' /><format attr='line-visibility' scope='rows' value='off' /></style-rule>")
                       + (f"<style-rule element='axis'>{axes}</style-rule>" if axes else "") + "</style>")
        flt = "".join(f[1] for f in self.filters)
        shelf = lambda ps: "" if not ps else (ps[0].ref if len(ps) == 1 else "(" + " / ".join(p.ref for p in ps) + ")")
        return f"""<worksheet name='{q(self.name)}'>
      <layout-options><title><formatted-text><run bold='true' fontcolor='{TITLE_COLOR}' fontsize='11'>{q(self.title)}</run></formatted-text></title></layout-options>
      <table>
        <view>
          <datasources>{ds_list}</datasources>
          {dep}
          {flt}
          {sorts}
          <aggregation value='true' />
        </view>
        {sheet_style}
        <panes><pane selection-relaxation-option='selection-relaxation-allow'>
          <view><breakdown value='auto' /></view>
          <mark class='{self.mark}' />
          {'<encodings>' + enc + '</encodings>' if enc else ''}
          {pane_style}
        </pane></panes>
        <rows>{shelf(self.rows)}</rows>
        <cols>{shelf(self.cols)}</cols>
      </table>
      {sid()}
    </worksheet>"""

    def window(self):
        legend = f"<edge name='right'><strip size='160'><card pane-specification-id='0' param='{self.color.ref}' type='color' /></strip></edge>" if self.color is not None and self.legend else ""
        return (f"<window class='worksheet' name='{q(self.name)}'><cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge>"
                f"<edge name='top'><strip size='2147483647'><card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip><strip size='31'><card type='title' /></strip></edge>"
                f"{legend}</cards><viewpoint><zoom type='entire-view' /></viewpoint>{sid()}</window>")

# ------------------------------------------------------------------------------------------------ dashboards
W, M, G = 1600, 24, 16
CARD = ("<zone-style><format attr='border-color' value='#DDDDE0' /><format attr='border-style' value='solid' /><format attr='border-width' value='1' />"
        "<format attr='background-color' value='#FFFFFF' /><format attr='margin' value='4' /></zone-style>")

class Dash:
    def __init__(self, name):
        self.name, self.y, self.z, self.sheets, self.n = name, M, [], [], 10

    def _id(self):
        self.n += 1
        return self.n

    def span(self, spans):
        """(x, width) for each item; items span n of 12 columns (12 columns, 11 gaps)."""
        cw = (W - 2 * M - 11 * G) / 12
        out, col = [], 0
        for s in spans:
            out.append((round(M + col * (cw + G)), round(s * cw + (s - 1) * G))); col += s
        return out

    def text(self, txt_runs, x, y, w, h, bg=None):
        runs = "".join(f"<run{' bold=' + chr(39) + 'true' + chr(39) if b else ''} fontcolor='{c}' fontsize='{s}'>{q(t)}</run>" for t, s, c, b in txt_runs)
        style = f"<zone-style><format attr='border-style' value='none' />" + (f"<format attr='background-color' value='{bg}' />" if bg else "") + "<format attr='margin' value='12' /></zone-style>"
        self.z.append(("text", dict(id=self._id(), x=x, y=y, w=w, h=h), f"<formatted-text>{runs}</formatted-text>{style}"))

    def header(self, title, subtitle, last_sync=None):
        w_all = W - 2 * M
        right = 380 if last_sync else 0
        self.text([(title, 22, "#FFFFFF", True), ("   " + subtitle, 12, "#B5B5B9", False)], M, self.y, w_all - (right + G if right else 0), 64, bg="#262626")
        if last_sync:
            self.sheet(last_sync, W - M - right, self.y, right, 64)
        self.y += 64 + G

    def note(self, txt):
        self.text([(txt, 10, "#7C7C80", False)], M, self.y, W - 2 * M, 28)
        self.y += 28 + G

    def filters(self, items):
        """items: (src, field, caption)  -> one row of quick filters"""
        for (x, w), (src, field, cap) in zip(self.span([12 // len(items)] * len(items)), items):
            p = Pill(src, field)
            self.z.append(("filter", dict(id=self._id(), x=x, y=self.y, w=w, h=56), (cap, p.ref)))
        self.y += 56 + G

    def params(self, items, h=56):
        """items: (Param, mode)"""
        for (x, w), (prm, mode) in zip(self.span([12 // len(items)] * len(items)), items):
            self.z.append(("param", dict(id=self._id(), x=x, y=self.y, w=w, h=h), (prm.ref, mode)))
        self.y += h + G

    def sheet(self, sheet, x, y, w, h):
        name = sheet if isinstance(sheet, str) else sheet.name
        self.sheets.append(name)
        self.z.append(("sheet", dict(id=self._id(), x=x, y=y, w=w, h=h), (name, None)))
        if not isinstance(sheet, str) and sheet.color is not None and sheet.legend:
            self.z.append(("legend", dict(id=self._id(), x=x + w - 330, y=y + 6, w=320, h=24), (name, sheet.color.ref)))

    def row(self, items, h):
        """items: list of (Sheet, span) spanning 12 columns."""
        for (x, w), (sh, _s) in zip(self.span([s for _sh, s in items]), items):
            self.sheet(sh, x, self.y, w, h)
        self.y += h + G

    def xml(self):
        H = self.y - G + M
        pos = lambda d: f"h='{round(d['h'] / H * 100000)}' w='{round(d['w'] / W * 100000)}' x='{round(d['x'] / W * 100000)}' y='{round(d['y'] / H * 100000)}'"
        out = []
        for kind, d, p in self.z:
            if kind == "sheet":
                out.append(f"<zone id='{d['id']}' name='{q(p[0])}' {pos(d)}>{CARD}</zone>")
            elif kind == "text":
                out.append(f"<zone id='{d['id']}' type-v2='text' {pos(d)}>{p}</zone>")
            elif kind == "filter":
                out.append(f"<zone id='{d['id']}' mode='checkdropdown' name='{q(p[0])}' param='{p[1]}' type-v2='filter' values='relevant' {pos(d)}>{CARD}</zone>")
            elif kind == "param":
                out.append(f"<zone id='{d['id']}' mode='{p[1]}' param='{p[0]}' type-v2='paramctrl' {pos(d)}>{CARD}</zone>")
            elif kind == "legend":
                out.append(f"<zone id='{d['id']}' leg-item-layout='grid' name='{q(p[0])}' pane-specification-id='0' param='{p[1]}' show-title='false' type-v2='color' {pos(d)} />")
        return f"""<dashboard name='{q(self.name)}'>
      <style><style-rule element='dashboard'><format attr='background-color' value='#F2F2F3' /></style-rule></style>
      <size maxheight='{H}' maxwidth='{W}' minheight='{H}' minwidth='{W}' />
      <zones><zone id='4' type-v2='layout-basic' x='0' y='0' w='100000' h='100000'>{''.join(out)}
        <zone-style><format attr='border-style' value='none' /><format attr='margin' value='0' /></zone-style></zone></zones>
      {sid()}
    </dashboard>"""

    def window(self):
        vps = "".join(f"<viewpoint name='{q(n)}'><zoom type='entire-view' /></viewpoint>" for n in dict.fromkeys(self.sheets))
        return f"<window class='dashboard' name='{q(self.name)}'><viewpoints>{vps}</viewpoints><active id='-1' />{sid()}</window>"

# ------------------------------------------------------------------------------------------------ workbook + packaging
def actions_xml(dashes, sources_for_actions):
    out = []
    for i, (d, sheet) in enumerate(sources_for_actions, 1):
        out.append(f"<action caption='Filter {i} (generated)' name='[Action{i}]'><activation auto-clear='true' type='on-select' /><source dashboard='{q(d)}' type='sheet' worksheet='{q(sheet)}' />"
                   f"<command command='tsc:tsl-filter'><param name='special-fields' value='all' /><param name='target' value='{q(d)}' /></command></action>")
    return f"<actions>{''.join(out)}</actions>" if out else ""

def workbook_xml(sources, csvs, rows, sheets, dashes, action_pairs):
    ds = "".join(s.xml(csvs[s.key], f"Data/Extracts/{s.key}.hyper", rows[s.key]) for s in sources)
    pds = ""
    if PARAMS:
        pds = ("<datasource hasconnection='false' inline='true' name='Parameters' version='18.1'><aliases enabled='yes' />"
               + "".join(p.xml() for p in PARAMS.values()) + "</datasource>")
    return f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook original-version='18.1' source-build='2023.1.0 (20231.23.0309.1450)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest><SheetIdentifierTracking /><WindowsPersistSimpleIdentifiers /></document-format-change-manifest>
  <preferences><preference name='ui.encoding.shelf.height' value='24' /><preference name='ui.shelf.height' value='26' /></preferences>
  <datasources>{pds}{ds}</datasources>
  {actions_xml(dashes, action_pairs)}
  <worksheets>{''.join(s.xml() for s in sheets)}</worksheets>
  <dashboards>{''.join(d.xml() for d in dashes)}</dashboards>
  <windows source-height='30'>{''.join(d.window() for d in dashes)}{''.join(s.window() for s in sheets)}</windows>
</workbook>"""

def make_hyper(csv_path, hyper_path, cols, empty=False):
    if os.environ.get("SISTPERF_FORCE_TEMPLATES"):
        raise OSError("Hyper API disabled by SISTPERF_FORCE_TEMPLATES")
    import pandas as pd
    from tableauhyperapi import HyperProcess, Telemetry, Connection, CreateMode, TableDefinition, SqlType, TableName, Inserter
    df = pd.DataFrame() if empty else pd.read_csv(csv_path)
    sql = {"string": SqlType.text(), "integer": SqlType.big_int(), "real": SqlType.double()}
    table = TableDefinition(TableName("Extract", "Extract"), [TableDefinition.Column(n, sql[t]) for n, t in cols])
    def val(v, t):
        if pd.isna(v): return None
        return str(v) if t == "string" else (int(v) if t == "integer" else float(v))
    rows = [[val(r.get(n), t) for n, t in cols] for r in df.to_dict("records")]
    if os.path.exists(hyper_path): os.remove(hyper_path)
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with Connection(hp.endpoint, hyper_path, CreateMode.CREATE_AND_REPLACE) as con:
            con.catalog.create_schema("Extract"); con.catalog.create_table(table)
            with Inserter(con, table) as ins:
                ins.add_rows(rows); ins.execute()
    return len(rows)

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hyper_templates")

def _template(src, dest):
    """Empty extract with the right columns, used when the Hyper API cannot run (e.g. Windows blocks its DLL).
    Tableau fills it from the CSV when you choose Data > (source) > Refresh Extract."""
    meta = os.path.join(TEMPLATES, "schema.json")
    tpl = os.path.join(TEMPLATES, f"{src.key}.hyper")
    if not (os.path.exists(tpl) and os.path.exists(meta)):
        raise RuntimeError("The Hyper API cannot load and no extract templates were found in scripts/hyper_templates.")
    if json.load(open(meta)).get(src.key) != [list(c) for c in src.cols]:
        raise RuntimeError(f"The extract template for {src.key} is out of date (columns changed). Fix the Hyper API or ask for new templates.")
    shutil.copy(tpl, dest)

def package(twbx_path, sources, csvs, sheets, dashes, action_pairs):
    tmp = os.path.join(os.path.dirname(twbx_path) or ".", ".build"); os.makedirs(tmp, exist_ok=True)
    base = os.path.splitext(os.path.basename(twbx_path))[0]
    rows, hypers, fallback = {}, {}, []
    for s in sources:
        hypers[s.key] = os.path.join(tmp, f"{s.key}.hyper")
        try:
            rows[s.key] = make_hyper(csvs[s.key], hypers[s.key], s.cols)
        except Exception:                       # Hyper API unusable on this PC
            _template(s, hypers[s.key]); rows[s.key] = 0; fallback.append(s.key)
    twb = os.path.join(tmp, base + ".twb")
    open(twb, "w", encoding="utf-8").write(workbook_xml(sources, csvs, rows, sheets, dashes, action_pairs))
    with zipfile.ZipFile(twbx_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(twb, base + ".twb")
        for k, h in hypers.items():
            z.write(h, f"Data/Extracts/{k}.hyper")
    for f in [twb] + list(hypers.values()): os.remove(f)
    os.rmdir(tmp)
    return rows, fallback
