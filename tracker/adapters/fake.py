"""Fake source for testing the tracker. Each call 'publishes' a bit more, like a real ERP would."""
import os, pandas as pd
from tracker.adapters.base import Adapter

class FakeAdapter(Adapter):
    def __init__(self, student="STU001", state="data/private/.fake_calls"):
        self.student, self.state = student, state

    def fetch(self):
        n = int(open(self.state).read()) if os.path.exists(self.state) else 0
        os.makedirs(os.path.dirname(self.state), exist_ok=True); open(self.state, "w").write(str(n + 1))
        d = pd.read_csv("data/sample/sample_sist.csv"); d = d[d["Student_ID"] == self.student].copy()
        d["Student_ID"] = "ME"
        d = d.reset_index(drop=True)
        cae1 = d[(d["Semester"] == 3) & (d["Assessment"] == "CAE 1")]
        first = cae1.index[0]
        extra = None
        if n >= 1:   # CAE 2 appears
            extra = cae1.copy(); extra["Assessment"] = "CAE 2"; extra["Marks"] = (extra["Marks"] + 3).clip(upper=extra["Maximum_Marks"])
        if n >= 2:   # a CAE 1 mark gets corrected
            d.loc[first, "Marks"] = min(d.loc[first, "Marks"] + 1, d.loc[first, "Maximum_Marks"])
        if extra is not None:
            d = pd.concat([d, extra], ignore_index=True)
        return d.to_dict("records")
