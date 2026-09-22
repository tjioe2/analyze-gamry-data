"""
plot_gamry.py
--------------
Auto-detects the experiment type in a Gamry .DTA file and produces the
appropriate plot:

  - CV                -> Current (mA) vs. Potential (V), one line per cycle
                         (a dialog lets you pick which cycles to include)
  - CHRONOA           -> Current (mA) vs. Time (s)
  - CHRONOP           -> Potential (V) vs. Time (s)
  - REPEATING_CHRONOA -> Current (mA) vs. Time (s), shaded by voltage step,
                         with cycle boundaries marked

A file-browser dialog lets you pick one or more .DTA files (starting in
D:/Gamry data). For each file:
  - A plot is saved in a "Gamry plots" subfolder next to that file.
All extracted data across all selected files is combined into a single .xlsx
file saved in an "Extracted data" subfolder next to the first selected file.
The user is prompted for the xlsx filename before saving.
"""

import sys
import os
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np


# ── 1. Parser ──────────────────────────────────────────────────────────────

def parse_gamry_dta(filepath):
    metadata = {}
    curves = []
    exp_type = "UNKNOWN"

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        parts = line.split("\t")
        tag = parts[0].strip()

        if tag == "TAG" and len(parts) >= 2:
            exp_type = parts[1].strip().upper()

        if re.match(r"^CURVE\d*$", tag) and len(parts) >= 2 and parts[1].strip() == "TABLE":
            i += 1
            col_names = [c.strip() for c in lines[i].rstrip("\r\n").split("\t")[1:]]
            i += 1
            i += 1

            rows = []
            while i < len(lines):
                data_line = lines[i].rstrip("\r\n")
                if not data_line.startswith("\t"):
                    break
                data_parts = data_line.split("\t")[1:]
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

    return exp_type, metadata, curves


# ── 2. Cycle-selection dialog (CV only) ────────────────────────────────────

def ask_cycles(n_total):
    import tkinter as tk

    selected = []

    root = tk.Tk()
    root.title("Select cycles to plot")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    tk.Label(root, text=f"Found {n_total} cycle(s). Select which to plot:",
             font=("Arial", 11)).pack(pady=(12, 4), padx=16)

    vars_ = []
    frame = tk.Frame(root)
    frame.pack(padx=16, pady=4)
    for i in range(1, n_total + 1):
        var = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(frame, text=f"Cycle {i}", variable=var, font=("Arial", 10))
        cb.grid(row=i - 1, column=0, sticky="w")
        vars_.append(var)

    def on_ok():
        chosen = [i + 1 for i, v in enumerate(vars_) if v.get()]
        selected.extend(chosen if chosen else list(range(1, n_total + 1)))
        root.destroy()

    tk.Button(root, text="Plot", command=on_ok, width=10,
              font=("Arial", 10)).pack(pady=(6, 12))
    root.mainloop()

    return selected if selected else list(range(1, n_total + 1))


# ── 3. xlsx filename dialog ────────────────────────────────────────────────

def ask_xlsx_filename():
    """Pop up a small dialog asking for the output xlsx filename."""
    import tkinter as tk

    result = []

    root = tk.Tk()
    root.title("Save extracted data")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    tk.Label(root, text="Enter filename for the extracted data xlsx\n(without extension):",
             font=("Arial", 11)).pack(pady=(12, 4), padx=16)

    entry = tk.Entry(root, font=("Arial", 11), width=36)
    entry.insert(0, "Extracted_data")
    entry.pack(padx=16, pady=4)
    entry.focus()
    entry.select_range(0, tk.END)

    def on_ok():
        name = entry.get().strip()
        if name:
            result.append(name)
        root.destroy()

    root.bind("<Return>", lambda e: on_ok())
    tk.Button(root, text="Save", command=on_ok, width=10,
              font=("Arial", 10)).pack(pady=(6, 12))
    root.mainloop()

    return result[0] if result else "Extracted_data"


# ── 4. Plot functions (return fig, suffix, extracted DataFrame) ────────────

def plot_cv(filepath, metadata, curves, current_unit="mA"):
    scale = {"A": 1.0, "mA": 1e3, "uA": 1e6}.get(current_unit, 1e3)
    fname = os.path.basename(filepath)

    selected_cycles = ask_cycles(len(curves))
    curves_to_plot = [curves[i - 1] for i in selected_cycles if i <= len(curves)]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = cm.tab10(np.linspace(0, 0.9, max(len(curves_to_plot), 1)))

    extracted_frames = []
    for idx, df in enumerate(curves_to_plot):
        if "Vf" not in df.columns or "Im" not in df.columns:
            continue
        cycle_num = selected_cycles[idx]
        voltage = df["Vf"].astype(float)
        current = df["Im"].astype(float) * scale
        ax.plot(voltage, current, color=colors[idx], linewidth=1.5, label=f"Cycle {cycle_num}")

        extracted_frames.append(pd.DataFrame({
            "File name":                      fname,
            "Cycle":                          cycle_num,
            "Potential (V vs. Ref.)":         voltage.values,
            f"Current ({current_unit})":      current.values,
        }))

    scan_rate = metadata.get("SCANRATE", "?")
    title_tag = metadata.get("TITLE", fname)
    date_tag  = metadata.get("DATE", "")

    ax.set_xlabel("Potential (V vs. Ref.)", fontsize=13)
    ax.set_ylabel(f"Current ({current_unit})", fontsize=13)
    ax.set_title(f"Cyclic Voltammetry — {title_tag}\n"
                 f"Scan rate: {scan_rate} mV/s   |   {date_tag}", fontsize=11)
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
    ax.legend(fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()

    suffix = "cycles_" + "_".join(str(c) for c in selected_cycles) + "_CV_plot"
    extracted = pd.concat(extracted_frames, ignore_index=True) if extracted_frames else pd.DataFrame()
    return fig, suffix, extracted


def plot_chronoamp(filepath, metadata, curves, current_unit="mA"):
    df = curves[0]
    scale = {"A": 1.0, "mA": 1e3, "uA": 1e6}.get(current_unit, 1e3)
    fname = os.path.basename(filepath)

    time_s  = df["T"].astype(float)
    current = df["Im"].astype(float) * scale

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(time_s, current, color="tab:red", linewidth=1.2)

    title_tag = metadata.get("TITLE", fname)
    date_tag  = metadata.get("DATE", "")
    vstep2    = metadata.get("VSTEP2", "")

    ax.set_xlabel("Time (s)", fontsize=13)
    ax.set_ylabel(f"Current ({current_unit})", fontsize=13)
    ax.set_title(f"Chronoamperometry — {title_tag}\n"
                 f"Applied potential step: {vstep2} V   |   {date_tag}", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()

    extracted = pd.DataFrame({
        "File name":                 fname,
        "Time (s)":                  time_s.values,
        f"Current ({current_unit})": current.values,
    })
    return fig, "ChronoAmp_plot", extracted


def plot_chronopot(filepath, metadata, curves, voltage_unit="V"):
    df = curves[0]
    scale = {"V": 1.0, "mV": 1e3}.get(voltage_unit, 1.0)
    fname = os.path.basename(filepath)

    time_s  = df["T"].astype(float)
    voltage = df["Vf"].astype(float) * scale

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(time_s, voltage, color="tab:blue", linewidth=1.2)

    title_tag = metadata.get("TITLE", fname)
    date_tag  = metadata.get("DATE", "")
    istep2    = metadata.get("ISTEP2", "")

    ax.set_xlabel("Time (s)", fontsize=13)
    ax.set_ylabel(f"Potential ({voltage_unit} vs. Ref.)", fontsize=13)
    ax.set_title(f"Chronopotentiometry — {title_tag}\n"
                 f"Applied current step: {istep2} A   |   {date_tag}", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()

    extracted = pd.DataFrame({
        "File name":                            fname,
        "Time (s)":                             time_s.values,
        f"Potential ({voltage_unit} vs. Ref.)": voltage.values,
    })
    return fig, "ChronoPot_plot", extracted


def plot_repeating_chronoamp(filepath, metadata, curves, current_unit="mA"):
    df = curves[0]
    scale = {"A": 1.0, "mA": 1e3, "uA": 1e6}.get(current_unit, 1e3)
    fname = os.path.basename(filepath)

    time_s  = df["T"].astype(float).values
    current = df["Im"].astype(float).values * scale

    n_cycles = int(float(metadata.get("CYCLES", 1)))
    tstep1   = float(metadata.get("TSTEP1", 0))
    tstep2   = float(metadata.get("TSTEP2", 0))
    vstep1   = metadata.get("VSTEP1", "")
    vstep2   = metadata.get("VSTEP2", "")
    period   = tstep1 + tstep2

    fig, ax = plt.subplots(figsize=(10, 5))

    for cyc in range(n_cycles):
        t_start = cyc * period
        t_mid   = t_start + tstep1
        t_end   = t_start + period
        ax.axvspan(t_start, t_mid, color="tab:red",  alpha=0.08, linewidth=0)
        ax.axvspan(t_mid,   t_end, color="tab:blue", alpha=0.08, linewidth=0)
        if cyc > 0:
            ax.axvline(t_start, color="gray", linewidth=0.8, linestyle="--")

    ax.plot(time_s, current, color="black", linewidth=0.9)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="tab:red",  alpha=0.3, label=f"Step 1: {vstep1} V"),
        Patch(facecolor="tab:blue", alpha=0.3, label=f"Step 2: {vstep2} V"),
    ]
    ax.legend(handles=legend_elements, fontsize=10)

    title_tag = metadata.get("TITLE", fname)
    date_tag  = metadata.get("DATE", "")

    ax.set_xlabel("Time (s)", fontsize=13)
    ax.set_ylabel(f"Current ({current_unit})", fontsize=13)
    ax.set_title(f"Repeating Chronoamperometry — {title_tag}\n"
                 f"{n_cycles} cycles  |  Step 1: {vstep1} V ({tstep1} s)  "
                 f"Step 2: {vstep2} V ({tstep2} s)  |  {date_tag}", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout()

    cycle_labels, step_labels = [], []
    for t in time_s:
        cyc_idx  = int(t // period)
        t_in_cyc = t % period
        cycle_labels.append(cyc_idx + 1)
        step_labels.append(1 if t_in_cyc < tstep1 else 2)

    extracted = pd.DataFrame({
        "File name":                 fname,
        "Time (s)":                  time_s,
        f"Current ({current_unit})": current,
        "Cycle":                     cycle_labels,
        "Step":                      step_labels,
    })
    return fig, "RepeatChronoAmp_plot", extracted


# ── 5. Dispatcher ────────────────────────────────────────────────────────────

def process_file(filepath):
    """Parse, plot, and return (fig, suffix, extracted_df) for one file."""
    exp_type, metadata, curves = parse_gamry_dta(filepath)

    if not curves:
        raise ValueError(f"No CURVE data found in: {filepath}")

    print(f"  Detected: {exp_type}")

    if exp_type == "CV":
        return plot_cv(filepath, metadata, curves)
    elif exp_type == "CHRONOA":
        return plot_chronoamp(filepath, metadata, curves)
    elif exp_type == "CHRONOP":
        return plot_chronopot(filepath, metadata, curves)
    elif exp_type == "REPEATING_CHRONOA":
        return plot_repeating_chronoamp(filepath, metadata, curves)
    else:
        raise ValueError(f"Unrecognized experiment type: '{exp_type}'.")


# ── 6. Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tkinter as tk
    from tkinter import filedialog, simpledialog

    # ── Select one or more .DTA files ──
    if len(sys.argv) > 1:
        dta_files = sys.argv[1:]
    else:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        dta_files = filedialog.askopenfilenames(
            title="Select one or more Gamry .DTA files",
            initialdir=r"D:\Gamry data",
            filetypes=[("Gamry DTA files", "*.DTA *.dta"), ("All files", "*.*")]
        )
        root.destroy()

        if not dta_files:
            print("No files selected. Exiting.")
            sys.exit(0)

    dta_files = list(dta_files)

    # ── Ask for xlsx output filename ──
    xlsx_name = ask_xlsx_filename()
    if not xlsx_name.lower().endswith(".xlsx"):
        xlsx_name += ".xlsx"

    # ── Process each file ──
    all_extracted = []

    for filepath in dta_files:
        print(f"\nProcessing: {os.path.basename(filepath)}")
        try:
            fig, suffix, extracted = process_file(filepath)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        # Save individual plot
        input_dir = os.path.dirname(os.path.abspath(filepath))
        plots_dir = os.path.join(input_dir, "Gamry plots")
        os.makedirs(plots_dir, exist_ok=True)
        out_png = os.path.join(plots_dir,
                               os.path.splitext(os.path.basename(filepath))[0] + f"_{suffix}.png")
        fig.savefig(out_png, dpi=150)
        print(f"  Plot saved  -> {out_png}")
        plt.close(fig)

        if not extracted.empty:
            all_extracted.append(extracted)

    # ── Save combined xlsx ──
    if all_extracted:
        combined = pd.concat(all_extracted, ignore_index=True)

        # Save next to the first selected file
        first_dir = os.path.dirname(os.path.abspath(dta_files[0]))
        data_dir  = os.path.join(first_dir, "Extracted data")
        os.makedirs(data_dir, exist_ok=True)
        out_xlsx  = os.path.join(data_dir, xlsx_name)

        combined.to_excel(out_xlsx, index=False)
        print(f"\nData saved  -> {out_xlsx}")
    else:
        print("\nNo data extracted — xlsx not saved.")

    print("\nDone.")