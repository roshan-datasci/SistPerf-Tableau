import pandas as pd

def load_csv(src):
    """src: path or file-like. ERP adapters can be added here later."""
    return pd.read_csv(src)
