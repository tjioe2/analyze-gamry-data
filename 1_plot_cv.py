# -*- coding: utf-8 -*-
"""
Created on Tue Jun  2 09:37:27 2026

@author: MarcoTjioe
"""

"""
plot_cv.py
----------
Parse and plot cyclic voltammetry (CV) data from a Gamry .DTA file.
Usage:  python plot_cv.py 59_CV_5mM_NaCl_K5.DTA
"""

import sys
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np


# ── 1. Parser ──────────────────────────────────────────────────────────────

def parse_gamry_dta(filepath):
    """
    Return a dict with:
      - 'metadata'  : dict of key → value pairs from the header
      - 'curves'    : list of DataFrames, one per CURVEn TABLE block
    """
    metadata = {}
    curves = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        parts = line.split("\t")

        # -- metadata (non-table rows) --
        tag = parts[0].strip()

        # CV curve tables: CURVE1, CURVE2, …
        if re.match(r"^CURVE\d+$", tag) and len(parts) >= 2 and parts[1].strip() == "TABLE":
            i += 1  # column-name row
            col_names = [c.strip() for c in lines[i].rstrip("\r\n").split("\t")[1:]]
            i += 1  # units row
            i += 1  # skip units row

            rows = []
            while i < len(lines):
                data_line = lines[i].rstrip("\r\n")
                if not data_line.startswith("\t"):
                    break          # next section started
                data_parts = data_line.split("\t")[1:]  # drop leading tab
                if len(data_parts) < len(col_names):
                    i += 1
                    continue
                rows.append(data_parts[: len(col_names)])
                i += 1

            df = pd.DataFrame(rows, columns=col_names)
            # Convert numeric columns
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col])
                except (ValueError, TypeError):
                    pass
            curves.append(df)
            continue  # don't increment i again

        # Simple metadata key=value
        elif len(parts) >= 3 and parts[1].strip() in ("LABEL", "POTEN", "QUANT", "IQUANT", "SELECTOR", "TOGGLE"):
            metadata[tag] = parts[2].strip()

        i += 1

    return metadata, curves


# ── 2. Plot ────────────────────────────────────────────────────────────────

def plot_cv(filepath, current_unit="mA", area_cm2=None, cycles=None):
    """
    Parse filepath and produce a publication-style CV plot.

    Parameters
    ----------
    filepath    : str   path to the .DTA file
    current_unit: str   'A', 'mA', or 'µA'  — y-axis unit
    area_cm2    : float if given, normalise current → mA cm⁻²
    """
    metadata, curves = parse_gamry_dta(filepath)

    if not curves:
        raise ValueError("No CURVE data found in the file.")
        
    if cycles is not None:
        curves = [curves[i-1] for i in cycles if i <= len(curves)]

    # Unit scale factors
    scale = {"A": 1.0, "mA": 1e3, "µA": 1e6, "uA": 1e6}
    factor = scale.get(current_unit, 1e3)

    # ── plot ──
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = cm.tab10(np.linspace(0, 0.9, len(curves)))
        
    for idx, df in enumerate(curves):
        if "Vf" not in df.columns or "Im" not in df.columns:
            print(f"  Skipping curve {idx+1}: missing Vf or Im columns.")
            continue

        voltage = df["Vf"].astype(float)
        current = df["Im"].astype(float) * factor

        if area_cm2:
            current /= area_cm2
            ylabel = f"Current density (mA cm⁻²)"
        else:
            ylabel = f"Current ({current_unit})"

        ax.plot(voltage, current, color=colors[idx],
                linewidth=1.5, label=f"Cycle {idx + 1}")

    # Labels & formatting
    scan_rate = metadata.get("SCANRATE", "?")
    title_tag = metadata.get("TITLE", filepath)
    date_tag  = metadata.get("DATE", "")

    ax.set_xlabel("Potential (V vs. Ref.)", fontsize=13)
    ax.set_ylabel(ylabel, fontsize=13)
    ax.set_title(f"Cyclic Voltammetry — {title_tag}\n"
                 f"Scan rate: {scan_rate} mV/s   |   {date_tag}", fontsize=11)
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
    ax.legend(fontsize=10)
    ax.tick_params(labelsize=11)
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()

    import os
    out_png = os.path.splitext(os.path.basename(filepath))[0] + "_CV_plot.png"
    fig.savefig(out_png, dpi=150)
    print(f"Plot saved → {out_png}")
    plt.show()


# ── 3. Entry point ─────────────────────────────────────────────────────────


if __name__ == "__main__":
    dta_file = r"D:\\Gamry data\59.CV_5mM NaCl_K5.DTA"
    plot_cv(dta_file, current_unit="uA", area_cm2=None, cycles=[1])