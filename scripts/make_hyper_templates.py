"""Maintainer script: writes empty extract templates (scripts/hyper_templates/*.hyper) for PCs where the Hyper API cannot run.
Needs a working tableauhyperapi. Re-run whenever the columns of a data source change."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_tableau_workbook as B, twb_lib as T
os.makedirs(T.TEMPLATES, exist_ok=True)
meta = {}
for s in B.SOURCES:
    T.make_hyper(None, os.path.join(T.TEMPLATES, f"{s.key}.hyper"), s.cols, empty=True)
    meta[s.key] = [list(c) for c in s.cols]
json.dump(meta, open(os.path.join(T.TEMPLATES, "schema.json"), "w"), indent=1)
print("templates written:", sorted(os.listdir(T.TEMPLATES)))
