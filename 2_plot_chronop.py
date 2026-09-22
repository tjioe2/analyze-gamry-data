"""
plot_chronop.py
----------------
Parse and plot chronopotentiometry (CHRONOP) data from a Gamry .DTA file.
Plots Potential (V) vs. Time (s).

Usage:  python plot_chronop.py "yourfile.DTA"
"""

import sys
import os
import re
import pandas as pd
import matplotlib.pyplot as plt


# ── 1. Parser ──────────────────────────────────────────────────────────────

def parse_gamry_dta(filepath):
    """
    Return (metadata, curves) where:
      - metadata : dict of key -> value pairs from the header
      - curves   : list of DataFrames, one per CURVE/CURVEn TABLE block
    """
    metadata = {}
    curves = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        parts = line.split("\t")
        tag = parts[0].strip()

        # Data tables: "CURVE" (chronopotentiometry/amperometry) or "CURVE1", "CURVE2"... (CV cycles)
        if re.match(r"^CURVE\d*$", tag) and len(parts) >= 2 and parts[1].strip() == "TABLE":
            i += 1  # column-name row
            col_names = [c.strip() for c in lines[i].rstrip("\r\n").split("\t")[1:]]
            i += 1  # units row
            i += 1  # move past units row to first data row

            rows = []
            while i < len(lines):
                data_line = lines[i].rstrip("\r\n")
                if not data_line.startswith("\t"):
                    break  # next section started
                data_parts = data_line.split("\t")[1:]  # drop leading tab
                if len(data_parts) < len(col_names):
                    i += 1
                    continue
                rows.append(data_parts[: len(col_names)])
                i += 1

            df = pd.DataFrame(rows, columns=col_names)
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col])
                except (ValueError, TypeError):
                    pass
            curves.append(df)
            continue

        elif len(parts) >= 3 and parts[1].strip() in ("LABEL", "POTEN", "QUANT", "IQUANT", "SELECTOR", "TOGGLE"):
            metadata[tag] = parts[2].strip()

        i += 1

    return metadata, curves


# ── 2. Plot ────────────────────────────────────────────────────────────────

def plot_chronop(filepath, voltage_unit="V"):
    """
    Parse filepath and plot Potential (V) vs. Time (s).

    Parameters
    ----------
    filepath     : str   path to the .DTA file
    voltage_unit : str   'V' or 'mV' for the y-axis
    """
    metadata, curves = parse_gamry_dta(filepath)

    if not curves:
        raise ValueError("No CURVE data found in the file.")

    df = curves[0]  # chronopotentiometry has a single curve table

    if "T" not in df.columns or "Vf" not in df.columns:
        raise ValueError(f"Expected 'T' and 'Vf' columns, got: {list(df.columns)}")

    time_s = df["T"].astype(float)
    scale = {"V": 1.0, "mV": 1e3}.get(voltage_unit, 1.0)
    voltage = df["Vf"].astype(float) * scale

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(time_s, voltage, color="tab:blue", linewidth=1.2)

    title_tag = metadata.get("TITLE", os.path.basename(filepath))
    date_tag = metadata.get("DATE", "")
    istep2 = metadata.get("ISTEP2", "")

    ax.set_xlabel("Time (s)", fontsize=13)
    ax.set_ylabel(f"Potential ({voltage_unit} vs. Ref.)", fontsize=13)
    ax.set_title(f"Chronopotentiometry — {title_tag}\n"
                 f"Applied current step: {istep2} A   |   {date_tag}", fontsize=11)
    ax.tick_params(labelsize=11)
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()

    # Save into a "Gamry plots" subfolder next to the input file
    input_dir = os.path.dirname(os.path.abspath(filepath))
    out_dir = os.path.join(input_dir, "Gamry plots")
    os.makedirs(out_dir, exist_ok=True)

    out_filename = os.path.splitext(os.path.basename(filepath))[0] + "_ChronoP_plot.png"
    out_png = os.path.join(out_dir, out_filename)
    fig.savefig(out_png, dpi=150)
    print(f"Plot saved -> {out_png}")
    plt.show()


# ── 3. Entry point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Use a command-line argument if given, otherwise open a file browser
    if len(sys.argv) > 1:
        dta_file = sys.argv[1]
    else:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()          # hide the empty main window
        root.attributes("-topmost", True)  # bring dialog to front

        dta_file = filedialog.askopenfilename(
            title="Select your Gamry .DTA file",
            initialdir=r"D:\Gamry data",
            filetypes=[("Gamry DTA files", "*.DTA *.dta"), ("All files", "*.*")]
        )
        root.destroy()

        if not dta_file:
            print("No file selected. Exiting.")
            sys.exit(0)

    plot_chronop(dta_file, voltage_unit="V")