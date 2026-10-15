import os
import numpy as np, pandas as pd, plotly.express as px, plotly.graph_objects as go, streamlit as st, yaml
from data_pipeline.extract import load_csv
from data_pipeline.validate import validate
from data_pipeline.transform import normalize
from analytics import metrics as M
from analytics.prediction import evaluate_and_predict

st.set_page_config(page_title="SistPerf", layout="wide")
cfg = yaml.safe_load(open("config.yaml"))
P = lambda v: "-" if pd.isna(v) else f"{v:.1f}%"

# ---------- data ----------
st.sidebar.header("Data")
up = st.sidebar.file_uploader("Upload your marks CSV", type="csv")
if up:
    raw, src = load_csv(up), "uploaded file"
elif os.path.exists("data/private/marks.csv"):
    raw, src = load_csv("data/private/marks.csv"), "data/private/marks.csv"
else:
    raw, src = load_csv("data/sample/sample_sist.csv"), "synthetic sample"
st.sidebar.caption(f"Source: {src}")
clean, issues = validate(raw, cfg)
if clean.empty:
    st.error("No valid rows. See Data quality below."); st.dataframe(issues); st.stop()
df = normalize(clean)

sid = st.sidebar.selectbox("Student", sorted(df["Student_ID"].unique()))
me = df[df["Student_ID"] == sid]
sems = M.sem_order(me)
f_sem = st.sidebar.multiselect("Semester", sems, default=sems)
f_sub = st.sidebar.multiselect("Subject", sorted(me["Subject"].unique()))
f_asm = st.sidebar.multiselect("Assessment", ["CAE 1", "CAE 2", "Internal", "Exam"], default=["CAE 1", "CAE 2", "Internal", "Exam"])
view = me[me["Semester"].isin(f_sem) & me["Assessment"].isin(f_asm)]
if f_sub:
    view = view[view["Subject"].isin(f_sub)]
if view.empty:
    st.warning("Nothing matches these filters."); st.stop()

sub_all = M.subject_table(me, cfg)
sub = M.subject_table(view, cfg)
sgpa, cgpa = M.sgpa_table(sub_all, cfg)
k = M.kpis(view)
metrics_ml, preds = evaluate_and_predict(df)
my_pred = preds[preds["Student_ID"] == sid] if preds is not None else None

st.title("Student Academic Performance")
st.caption(f"{sid} · {src}" + (" · all numbers are synthetic" if src == "synthetic sample" else ""))

tabs = st.tabs(["Overview", "Subjects", "Assessments", "Planner", "Prediction", "Data quality", "Detailed marks"])

# ---------- Overview ----------
with tabs[0]:
    c = st.columns(6)
    for col, (l, v) in zip(c, [("Current semester", P(k["current"])), ("Overall average", P(k["overall"])),
                               ("CAE 1 average", P(k["cae1"])), ("CAE 2 average", P(k["cae2"])),
                               ("Subjects", k["subjects"]), ("Semesters completed", k["sems_done"])]):
        col.metric(l, v)
    c = st.columns(6)
    arrears = int((sub_all["Exam"] < cfg["pass_mark"]).sum())
    best = sub.groupby("Subject")["Average"].mean().idxmax()
    imp = sub.groupby("Subject")["Improvement"].mean().dropna()
    for col, (l, v) in zip(c, [("Total centums", k["centum_total"]), ("CAE centums", k["centum_cae"]),
                               ("Exam centums", k["centum_sem"]), ("90%+ scores", k["n90"]),
                               ("Arrears", arrears), ("Highest mark", k["highest"])]):
        col.metric(l, v)
    c = st.columns(3)
    c[0].metric("Best subject", best)
    c[1].metric("Most improved", f"{imp.idxmax()} ({imp.max():+.1f})" if len(imp) else "-")
    c[2].metric("SGPA / CGPA", f"{sgpa['SGPA'].iloc[-1]:.2f} / {cgpa:.2f}" if len(sgpa) else "-")

    trend = view.groupby("Semester")["Pct"].mean().reindex([s for s in sems if s in f_sem]).reset_index()
    fig = px.line(trend, x="Semester", y="Pct", markers=True, title="Overall performance trend (%)")
    target = st.slider("Target average (%)", 50, 100, 80)
    fig.add_hline(y=target, line_dash="dot", annotation_text="target")
    if my_pred is not None and len(my_pred):
        ps = my_pred["Semester"].iloc[0]
        fig.add_trace(go.Scatter(x=[trend["Semester"].iloc[-1], ps], y=[trend["Pct"].iloc[-1], my_pred["Predicted"].mean()],
                                 mode="lines+markers", line=dict(dash="dash"), name=f"{ps} predicted (exam)"))
    st.plotly_chart(fig, width="stretch")
    if len(sgpa):
        st.plotly_chart(px.bar(sgpa, x="Semester", y="SGPA", text_auto=".2f", title="SGPA by semester"), width="stretch")

# ---------- Subjects ----------
with tabs[1]:
    hm = sub.assign(Label=sub["Semester"] + " · " + sub["Subject"]).set_index("Label")[["CAE 1", "CAE 2", "Internal", "Exam", "Average"]]
    st.plotly_chart(px.imshow(hm, text_auto=".0f", aspect="auto", color_continuous_scale="RdYlGn", zmin=40, zmax=100,
                              title="Subject performance heatmap (%)"), width="stretch")
    a, b = st.columns(2)
    rk = sub.groupby("Subject")["Average"].mean().sort_values().reset_index()
    a.plotly_chart(px.bar(rk, x="Average", y="Subject", orientation="h", title="Subject ranking"), width="stretch")
    b.plotly_chart(px.histogram(view, x="Pct", nbins=10, range_x=[0, 100], title="Marks distribution (%)"), width="stretch")
    st.subheader("Consistency")
    st.dataframe(sub[["Semester", "Subject", "Average", "Std Dev", "Stability"]].round(1), hide_index=True, width="stretch")

# ---------- Assessments ----------
with tabs[2]:
    la = sub.melt(id_vars=["Semester", "Subject"], value_vars=["CAE 1", "CAE 2"], var_name="CAE", value_name="Pct").dropna()
    la["Label"] = la["Semester"] + " · " + la["Subject"]
    st.plotly_chart(px.bar(la, x="Label", y="Pct", color="CAE", barmode="group", title="CAE 1 vs CAE 2 (%)"), width="stretch")
    st.subheader("CAE improvement and CAE → exam gap")
    t = sub[["Semester", "Subject", "Improvement", "Internal→Exam gap", "Alert"]].round(1)
    st.dataframe(t, hide_index=True, width="stretch")
    for _, r in sub[sub["Alert"] != ""].iterrows():
        st.warning(f"{r['Semester']} · {r['Subject']}: {r['Alert']}")

# ---------- Planner ----------
with tabs[3]:
    open_sem = sems[-1]
    cur = sub_all[(sub_all["Semester"] == open_sem) & sub_all["Exam"].isna() & sub_all["Int_eff"].notna()]
    st.caption(f"Weights and grade bands come from config.yaml (placeholders - edit to match your college).")
    if cur.empty:
        st.info("No open semester with both CAEs and a pending exam.")
    else:
        st.subheader(f"What-if · {open_sem}")
        picks = {}
        cols = st.columns(3)
        for i, s in enumerate(cur["Subject"]):
            picks[s] = cols[i % 3].slider(f"{s} exam %", 0, 100, 75, key=f"w{s}")
        st.metric("Projected SGPA", f"{M.project_sgpa(cur, picks, cfg):.2f}")
        rows = []
        for _, r in cur.iterrows():
            f = M.final_pct(r["Int_eff"], picks[r["Subject"]], cfg)
            rows.append({"Subject": r["Subject"], "Final %": round(f, 1), "Grade": M.grade(f, cfg)[0]})
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.subheader("Target planner")
        tg = st.slider("Target SGPA", 5.0, 10.0, 8.5, 0.1)
        need = M.required_uniform_exam(cur, tg, cfg)
        st.success(f"Score at least {need}% in every exam to reach SGPA {tg:.1f}.") if need is not None else st.error("Not reachable with these CAE marks.")
        st.subheader("Exam mark needed per grade")
        wi, we = cfg["weights"]["Internal"], cfg["weights"]["Exam"]; out = []
        for _, r in cur.iterrows():
            row = {"Subject": r["Subject"]}
            for lo, letter, _g in cfg["grade_bands"][:-1]:
                x = (lo * (wi + we) - wi * r["Int_eff"]) / we
                row[letter] = "-" if x > 100 else f"{max(x, 0):.0f}%"
            out.append(row)
        st.dataframe(pd.DataFrame(out), hide_index=True)

# ---------- Prediction ----------
with tabs[4]:
    st.warning("Experimental. Estimates only, not guaranteed results.")
    if metrics_ml is None:
        st.info("Prediction needs many students to train on (this file has too few). Use the synthetic sample to see the method.")
    else:
        c = st.columns(3)
        c[0].metric("Baseline error (MAE)", f"{metrics_ml['mae_baseline']:.2f}")
        c[1].metric("Model error (MAE)", f"{metrics_ml['mae_model']:.2f}")
        c[2].metric("Held-out rows", metrics_ml["n_test"])
        st.caption("Baseline = average of CAE 1 and CAE 2. Evaluated on students not used for training. If the model barely beats the baseline, say so.")
        if my_pred is not None and len(my_pred):
            st.dataframe(my_pred.drop(columns="Student_ID").round(1).rename(columns={"Low": "Low (80%)", "High": "High (80%)"}), hide_index=True)
            st.metric("Predicted exam average", f"{my_pred['Predicted'].mean():.1f}%")
        else:
            st.info("No pending exams to predict for this student.")

# ---------- Data quality ----------
with tabs[5]:
    st.dataframe(issues, hide_index=True, width="stretch")

# ---------- Detailed ----------
with tabs[6]:
    d = sub[["Semester", "Subject_Code", "Subject", "CAE 1", "CAE 2", "Internal", "Exam", "Average", "Improvement", "Final %", "Grade"]].round(1).rename(columns={"Exam": "Exam"})
    st.dataframe(d, hide_index=True, width="stretch")
    st.download_button("Download CSV", d.to_csv(index=False), "marks_summary.csv")
