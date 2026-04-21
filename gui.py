"""
=============================================================
  MODULE: gui.py
  PURPOSE: Tkinter GUI for the Thrashing Simulator.
           Four tabs:
             1. Single Process  — step-by-step page replacement
             2. Multi Process   — round-robin, thrashing detection
             3. Algorithm Compare — FIFO vs LRU vs Optimal
             4. Graphs          — Denning curve, fault timelines
=============================================================
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading

from memory_core import RAM
from algorithms  import FIFO, LRU, Optimal, SimulationEngine, compare_algorithms
from process_sim import Process, MultiProcessScheduler, run_thrashing_experiment
from working_set import WorkingSetTracker, DynamicFrameAllocator
from visualizer  import (create_thrashing_graph, create_algorithm_comparison,
                         create_fault_rate_timeline, create_working_set_graph)


# ─────────────────────────────────────────────────────────────
#  STYLE CONSTANTS
# ─────────────────────────────────────────────────────────────

BG       = "#0f0f1a"       # Main background
BG2      = "#1a1a2e"       # Secondary background
BG3      = "#16213e"       # Card background
ACCENT   = "#00d4ff"       # Cyan accent
ACCENT2  = "#7c3aed"       # Purple accent
SUCCESS  = "#22c55e"       # Green
WARNING  = "#f59e0b"       # Orange
DANGER   = "#ef4444"       # Red
FG       = "#e2e8f0"       # Main text
FG2      = "#94a3b8"       # Secondary text
MONO     = ("Courier New", 10)
MONO_SM  = ("Courier New", 9)
HEADING  = ("Helvetica", 13, "bold")
LABEL    = ("Helvetica", 10)


def make_label(parent, text, font=LABEL, fg=FG, bg=BG2, **kw):
    return tk.Label(parent, text=text, font=font,
                    fg=fg, bg=bg, **kw)

def make_entry(parent, width=8, default=""):
    e = tk.Entry(parent, width=width, bg=BG3, fg=ACCENT,
                 insertbackground=ACCENT,
                 font=MONO, relief="flat",
                 highlightthickness=1, highlightcolor=ACCENT2,
                 highlightbackground=BG3)
    e.insert(0, default)
    return e

def make_button(parent, text, command, color=ACCENT2, fg=FG):
    return tk.Button(parent, text=text, command=command,
                     bg=color, fg=fg, font=("Helvetica", 10, "bold"),
                     relief="flat", cursor="hand2",
                     activebackground=ACCENT, activeforeground=BG,
                     padx=14, pady=6)

def make_log(parent, height=18, width=80):
    st = scrolledtext.ScrolledText(
        parent, height=height, width=width,
        bg=BG3, fg=FG, font=MONO_SM,
        insertbackground=FG, relief="flat",
        wrap=tk.WORD
    )
    st.tag_config("fault",  foreground=DANGER)
    st.tag_config("hit",    foreground=SUCCESS)
    st.tag_config("warn",   foreground=WARNING)
    st.tag_config("info",   foreground=ACCENT)
    st.tag_config("header", foreground=ACCENT, font=("Courier New", 10, "bold"))
    return st

def log_write(widget, text, tag=None):
    widget.config(state="normal")
    if tag:
        widget.insert(tk.END, text + "\n", tag)
    else:
        widget.insert(tk.END, text + "\n")
    widget.see(tk.END)
    widget.config(state="disabled")

def log_clear(widget):
    widget.config(state="normal")
    widget.delete(1.0, tk.END)
    widget.config(state="disabled")


# ─────────────────────────────────────────────────────────────
#  MAIN GUI CLASS
# ─────────────────────────────────────────────────────────────

class ThrashingSimulatorGUI:
    """
    Main application window with four tabbed panels.
    Each tab is a self-contained simulation interface.
    """

    def __init__(self, root):
        self.root = root
        root.title("Thrashing in Virtual Memory — OS Simulator")
        root.configure(bg=BG)
        root.geometry("1200x780")
        root.resizable(True, True)

        self._build_header()
        self._build_notebook()

    def _build_header(self):
        """Top banner with title."""
        hdr = tk.Frame(self.root, bg=ACCENT2, height=50)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        tk.Label(hdr,
                 text="⚡ THRASHING IN VIRTUAL MEMORY — OS Simulation",
                 font=("Helvetica", 14, "bold"),
                 bg=ACCENT2, fg=FG).pack(side="left", padx=20, pady=12)

        tk.Label(hdr,
                 text="FIFO · LRU · Optimal · Working Set · Thrashing Detection",
                 font=("Helvetica", 9),
                 bg=ACCENT2, fg=FG2).pack(side="right", padx=20, pady=12)

    def _build_notebook(self):
        """Create the tabbed notebook."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",
                         background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                         background=BG2, foreground=FG2,
                         padding=[14, 6], font=("Helvetica", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT2)],
                  foreground=[("selected", FG)])

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1 — Single Process
        t1 = tk.Frame(nb, bg=BG2)
        nb.add(t1, text="  Single Process  ")
        SingleProcessTab(t1)

        # Tab 2 — Multi Process
        t2 = tk.Frame(nb, bg=BG2)
        nb.add(t2, text="  Multi Process  ")
        MultiProcessTab(t2)

        # Tab 3 — Algorithm Comparison
        t3 = tk.Frame(nb, bg=BG2)
        nb.add(t3, text="  Algorithm Compare  ")
        AlgoCompareTab(t3)

        # Tab 4 — Graphs
        t4 = tk.Frame(nb, bg=BG2)
        nb.add(t4, text="  Graphs & Analysis  ")
        GraphsTab(t4)


# ─────────────────────────────────────────────────────────────
#  TAB 1 — SINGLE PROCESS SIMULATION
# ─────────────────────────────────────────────────────────────

class SingleProcessTab:
    """
    Single-process step-by-step simulation.
    User enters: number of frames, page reference string, algorithm.
    Output: step-by-step log showing each memory access, hits, faults,
            RAM state, and running statistics.
    """

    SAMPLE_INPUTS = {
        "Classic (Silberschatz)": ("3", "7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1"),
        "Belady's Anomaly":       ("3", "1 2 3 4 1 2 5 1 2 3 4 5"),
        "High Locality":          ("4", "1 2 3 1 2 3 1 2 3 4 4 4 1 2 3"),
        "Worst Case":             ("2", "1 2 3 4 5 6 7 8 1 2 3 4 5 6 7 8"),
    }

    def __init__(self, parent):
        self.parent = parent
        self._build()

    def _build(self):
        # ── Controls ──────────────────────────────────────────
        ctrl = tk.Frame(self.parent, bg=BG2)
        ctrl.pack(fill="x", padx=12, pady=8)

        make_label(ctrl, "Frames:").grid(row=0, column=0, padx=6, sticky="w")
        self.e_frames = make_entry(ctrl, width=5, default="3")
        self.e_frames.grid(row=0, column=1, padx=4)

        make_label(ctrl, "Algorithm:").grid(row=0, column=2, padx=6, sticky="w")
        self.algo_var = tk.StringVar(value="LRU")
        for i, a in enumerate(["FIFO", "LRU", "Optimal"]):
            tk.Radiobutton(ctrl, text=a, variable=self.algo_var, value=a,
                           bg=BG2, fg=FG, selectcolor=ACCENT2,
                           activebackground=BG2,
                           font=("Helvetica", 10)).grid(row=0, column=3+i, padx=4)

        make_label(ctrl, "Reference String (space-separated):").grid(
            row=1, column=0, columnspan=2, padx=6, sticky="w", pady=(8,2))
        self.e_refs = tk.Entry(ctrl, width=55, bg=BG3, fg=ACCENT,
                               insertbackground=ACCENT, font=MONO,
                               relief="flat", highlightthickness=1,
                               highlightcolor=ACCENT2, highlightbackground=BG3)
        self.e_refs.insert(0, "7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1")
        self.e_refs.grid(row=1, column=2, columnspan=6, padx=4, sticky="ew")

        # Sample input buttons
        sample_frame = tk.Frame(self.parent, bg=BG2)
        sample_frame.pack(fill="x", padx=12, pady=(0, 4))
        make_label(sample_frame, "Samples:", bg=BG2).pack(side="left", padx=4)
        for name, (frames, refs) in self.SAMPLE_INPUTS.items():
            def load(f=frames, r=refs):
                self.e_frames.delete(0, tk.END); self.e_frames.insert(0, f)
                self.e_refs.delete(0, tk.END);   self.e_refs.insert(0, r)
            tk.Button(sample_frame, text=name, command=load,
                      bg=BG3, fg=FG2, font=("Helvetica", 8),
                      relief="flat", cursor="hand2",
                      padx=6, pady=2).pack(side="left", padx=2)

        # Buttons
        btn_frame = tk.Frame(self.parent, bg=BG2)
        btn_frame.pack(fill="x", padx=12, pady=4)
        make_button(btn_frame, "▶  Run Simulation",
                    self._run).pack(side="left", padx=4)
        make_button(btn_frame, "⟳  Step by Step",
                    self._step_mode, color=BG3).pack(side="left", padx=4)
        make_button(btn_frame, "✕  Clear",
                    lambda: log_clear(self.log), color="#374151").pack(side="left", padx=4)

        # Log output
        self.log = make_log(self.parent, height=24, width=90)
        self.log.pack(fill="both", expand=True, padx=12, pady=8)
        self.log.config(state="disabled")

        # Step-mode state
        self._steps  = []
        self._step_i = 0

    def _parse_inputs(self):
        try:
            frames = int(self.e_frames.get())
            refs   = [int(x) for x in self.e_refs.get().split()]
            if frames < 1:
                raise ValueError("Need ≥ 1 frame")
            if not refs:
                raise ValueError("Reference string is empty")
            return frames, refs
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return None, None

    def _run(self):
        """Run the full simulation and display all steps."""
        frames, refs = self._parse_inputs()
        if frames is None:
            return

        log_clear(self.log)
        algo_name = self.algo_var.get()
        ram  = RAM(frames)
        algos = {"FIFO": FIFO, "LRU": LRU, "Optimal": Optimal}
        algo  = algos[algo_name](ram)
        engine = SimulationEngine(ram, algo)

        steps, stats = engine.run_process(0, refs)
        self._display_all_steps(steps, stats, algo_name, frames, refs)

    def _display_all_steps(self, steps, stats, algo_name, frames, refs):
        log_write(self.log,
                  f"╔══════════════════════════════════════════════╗", "header")
        log_write(self.log,
                  f"  Algorithm: {algo_name}  |  Frames: {frames}  |  "
                  f"References: {len(refs)}", "header")
        log_write(self.log,
                  f"╚══════════════════════════════════════════════╝\n", "header")

        for s in steps:
            tick   = s["tick"]
            page   = s["page"]
            fault  = s["fault"]
            evict  = s["evicted_page"]
            rate   = s["fault_rate"]
            fcount = s["fault_count"]

            tag = "fault" if fault else "hit"
            status = "❌ PAGE FAULT" if fault else "✅ PAGE HIT "
            evict_str = (f"  → Evicted page {evict}"
                         if evict is not None else "")

            log_write(self.log,
                      f"[T{tick:3d}] Access: page {page:3d}  "
                      f"{status}{evict_str}", tag)
            log_write(self.log,
                      f"        Faults: {fcount:3d}  Rate: {rate*100:5.1f}%  "
                      f"Frame: {s['loaded_frame']}",
                      "warn" if rate > 0.6 else None)

        log_write(self.log, "\n─── FINAL SUMMARY ───────────────────────────", "header")
        log_write(self.log, f"Total Accesses : {stats.total_accesses}")
        log_write(self.log, f"Total Faults   : {stats.page_faults}")
        log_write(self.log,
                  f"Fault Rate     : {stats.page_fault_rate()*100:.1f}%",
                  "fault" if stats.page_fault_rate() > 0.6 else "hit")
        log_write(self.log,
                  "⚠  THRASHING DETECTED" if stats.page_fault_rate() > 0.6
                  else "✅  No Thrashing", 
                  "fault" if stats.page_fault_rate() > 0.6 else "hit")

    def _step_mode(self):
        """Load steps for manual stepping."""
        frames, refs = self._parse_inputs()
        if frames is None:
            return

        log_clear(self.log)
        algo_name = self.algo_var.get()
        ram   = RAM(frames)
        algos = {"FIFO": FIFO, "LRU": LRU, "Optimal": Optimal}
        algo  = algos[algo_name](ram)
        engine = SimulationEngine(ram, algo)
        steps, stats = engine.run_process(0, refs)
        self._steps  = steps
        self._stats  = stats
        self._step_i = 0

        log_write(self.log,
                  f"Step mode: {len(steps)} steps loaded. "
                  "Click [Step by Step] to advance.", "info")
        # Repurpose button for stepping
        self._step_and_show()

    def _step_and_show(self):
        if self._step_i >= len(self._steps):
            log_write(self.log, "\n✅ All steps complete.", "hit")
            return
        s    = self._steps[self._step_i]
        fault = s["fault"]
        tag   = "fault" if fault else "hit"
        log_write(self.log,
                  f"[Step {self._step_i+1:3d}] Page {s['page']:3d}  "
                  f"{'❌ FAULT' if fault else '✅ HIT  '}"
                  f"  Rate={s['fault_rate']*100:.1f}%", tag)
        log_write(self.log, s["ram_snapshot"], None)
        log_write(self.log, "")
        self._step_i += 1


# ─────────────────────────────────────────────────────────────
#  TAB 2 — MULTI PROCESS SIMULATION
# ─────────────────────────────────────────────────────────────

class MultiProcessTab:
    """
    Multi-process round-robin simulation with thrashing detection.
    User can configure 2–6 processes, each with their own reference string,
    or use auto-generated random strings.
    """

    def __init__(self, parent):
        self.parent = parent
        self._build()

    def _build(self):
        # ── Top controls ──
        ctrl = tk.Frame(self.parent, bg=BG2)
        ctrl.pack(fill="x", padx=12, pady=8)

        make_label(ctrl, "Total RAM Frames:").grid(row=0, column=0, padx=6, sticky="w")
        self.e_frames = make_entry(ctrl, width=5, default="6")
        self.e_frames.grid(row=0, column=1)

        make_label(ctrl, "Algorithm:").grid(row=0, column=2, padx=8)
        self.algo_var = tk.StringVar(value="LRU")
        for i, a in enumerate(["FIFO", "LRU", "Optimal"]):
            tk.Radiobutton(ctrl, text=a, variable=self.algo_var, value=a,
                           bg=BG2, fg=FG, selectcolor=ACCENT2,
                           activebackground=BG2,
                           font=("Helvetica", 10)).grid(row=0, column=3+i, padx=4)

        self.prevent_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ctrl, text="Enable Thrashing Prevention",
                       variable=self.prevent_var,
                       bg=BG2, fg=FG, selectcolor=ACCENT2,
                       activebackground=BG2,
                       font=("Helvetica", 10)).grid(row=0, column=6, padx=12)

        # Process config rows
        self.proc_frame = tk.Frame(self.parent, bg=BG2)
        self.proc_frame.pack(fill="x", padx=12, pady=4)

        self.proc_entries = []   # List of (name_entry, refs_entry)
        default_refs = [
            "1 2 3 4 1 2 5 1 2 3",
            "2 3 4 5 6 2 3 4 5 6",
            "7 8 1 2 7 8 3 7 8 9",
            "5 6 7 8 5 6 7 8 5 6",
        ]
        make_label(self.proc_frame, "Process", bg=BG2).grid(row=0, column=0, padx=4)
        make_label(self.proc_frame, "Reference String", bg=BG2).grid(row=0, column=1, padx=4)

        for i in range(4):
            name_e = make_entry(self.proc_frame, width=6, default=f"P{i}")
            name_e.grid(row=i+1, column=0, padx=4, pady=2)
            refs_e = make_entry(self.proc_frame, width=45, default=default_refs[i])
            refs_e.grid(row=i+1, column=1, padx=4, pady=2)
            self.proc_entries.append((name_e, refs_e))

        # Buttons
        btn_frame = tk.Frame(self.parent, bg=BG2)
        btn_frame.pack(fill="x", padx=12, pady=4)
        make_button(btn_frame, "▶  Run Multi-Process Simulation",
                    self._run).pack(side="left", padx=4)
        make_button(btn_frame, "⟳  Randomize All Processes",
                    self._randomize, color=BG3).pack(side="left", padx=4)
        make_button(btn_frame, "✕  Clear",
                    lambda: log_clear(self.log), color="#374151").pack(side="left", padx=4)

        # Log
        self.log = make_log(self.parent, height=20, width=90)
        self.log.pack(fill="both", expand=True, padx=12, pady=8)
        self.log.config(state="disabled")

    def _randomize(self):
        import random
        for i, (ne, re) in enumerate(self.proc_entries):
            proc = Process.generate_random(i, num_pages=10, length=20)
            re.delete(0, tk.END)
            re.insert(0, " ".join(map(str, proc.reference_string)))

    def _run(self):
        try:
            frames = int(self.e_frames.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid frame count")
            return

        processes = []
        for i, (ne, re) in enumerate(self.proc_entries):
            ref_text = re.get().strip()
            if not ref_text:
                continue
            try:
                refs = [int(x) for x in ref_text.split()]
                proc = Process(i, refs, name=ne.get() or f"P{i}")
                processes.append(proc)
            except ValueError:
                messagebox.showerror("Error", f"Invalid refs for process {i}")
                return

        if not processes:
            messagebox.showerror("Error", "No processes configured")
            return

        log_clear(self.log)
        ram   = RAM(frames)
        sched = MultiProcessScheduler(
            ram,
            algorithm_name    = self.algo_var.get(),
            prevent_thrashing = self.prevent_var.get()
        )
        for p in processes:
            sched.add_process(p)

        _, round_summary, round_logs = sched.run_round_robin(accesses_per_turn=3)
        self._display_results(sched, round_summary, round_logs, frames)

    def _display_results(self, sched, rounds, round_logs, frames):
        """
        Display detailed multi-process simulation output.

        Structure:
          ┌─ Banner
          ├─ For each round:
          │    ├─ Detailed step log (interleaved P0→P1→P2→P3)
          │    │    ├─ "Step N: Px accesses (Px,pg) → HIT/FAULT → Frame F"
          │    │    ├─ "  Evicted (Py,pg) ← FIFO/LRU reason"  (if eviction)
          │    │    └─ "  Frames: [(P0,2),(P1,3),_,_]  [Px faults: N]"
          │    └─ Round summary with explicit formulas
          └─ Process summary table
        """
        log_write(self.log,
                  f"╔══ Multi-Process Simulation ══╗  "
                  f"Frames={frames}  Algo={sched.algorithm_name}  "
                  f"Processes={len([p for p in sched.processes])}", "header")
        log_write(self.log,
                  f"  Tuple-based pages: each page is (ProcessName, PageNumber)", "info")
        log_write(self.log,
                  f"  Cross-process page hits: IMPOSSIBLE (by design)\n", "info")

        # ── Per-round detailed log ─────────────────────────────────
        for r, log_lines in zip(rounds, round_logs):
            for line in log_lines:
                # Pick tag based on content
                if "FAULT" in line and "Summary" not in line and "Fault Rate" not in line:
                    tag = "fault"
                elif "HIT" in line:
                    tag = "hit"
                elif ("THRASHING" in line or "Suspend" in line
                      or "Freed" in line):
                    tag = "fault"
                elif ("Summary" in line or "═" in line):
                    tag = "header"
                elif ("CPU" in line or "Accesses" in line
                      or "Fault Rate" in line or "OK" in line):
                    tag = "warn"
                elif "info" in line.lower() or "Tuple" in line:
                    tag = "info"
                else:
                    tag = None
                log_write(self.log, line, tag)

        # ── Process summary (Part 5) ───────────────────────────────
        log_write(self.log,
                  "\n══ PROCESS SUMMARY ══════════════════════════════════", "header")
        log_write(self.log,
                  f"  {'Process':<8} {'Accesses':>9} {'Faults':>7} "
                  f"{'Fault Rate':>20}  Status", "header")
        log_write(self.log, "  " + "─" * 56, "header")

        for row in sched.get_summary_table():
            is_susp = row["Active"] == "SUSPENDED"
            tag     = "fault" if is_susp else "hit"
            status  = "⚠ SUSPENDED" if is_susp else "✅ Active"
            log_write(self.log,
                      f"  {row['Process']:<8} {row['Accesses']:>9} "
                      f"{row['Page Faults']:>7} "
                      f"{row['Fault Rate']:>20}  {status}", tag)


# ─────────────────────────────────────────────────────────────
#  TAB 3 — ALGORITHM COMPARISON
# ─────────────────────────────────────────────────────────────

class AlgoCompareTab:
    """
    Run the same reference string through FIFO, LRU, and Optimal.
    Show a side-by-side fault count table and embed a bar chart.
    """

    def __init__(self, parent):
        self.parent = parent
        self._build()

    def _build(self):
        ctrl = tk.Frame(self.parent, bg=BG2)
        ctrl.pack(fill="x", padx=12, pady=8)

        make_label(ctrl, "Frames:").grid(row=0, column=0, padx=6, sticky="w")
        self.e_frames = make_entry(ctrl, width=5, default="3")
        self.e_frames.grid(row=0, column=1)

        make_label(ctrl, "Reference String:").grid(row=0, column=2, padx=6)
        self.e_refs = tk.Entry(ctrl, width=50, bg=BG3, fg=ACCENT,
                               insertbackground=ACCENT, font=MONO,
                               relief="flat", highlightthickness=1,
                               highlightcolor=ACCENT2, highlightbackground=BG3)
        self.e_refs.insert(0, "1 2 3 4 1 2 5 1 2 3 4 5")
        self.e_refs.grid(row=0, column=3, padx=4)

        btn_frame = tk.Frame(self.parent, bg=BG2)
        btn_frame.pack(fill="x", padx=12, pady=4)
        make_button(btn_frame, "▶  Compare All Algorithms",
                    self._run).pack(side="left", padx=4)

        # Results table
        self.table_frame = tk.Frame(self.parent, bg=BG2)
        self.table_frame.pack(fill="x", padx=12, pady=6)

        self.log = make_log(self.parent, height=8, width=90)
        self.log.pack(fill="x", padx=12, pady=4)
        self.log.config(state="disabled")

        # Chart area
        self.chart_frame = tk.Frame(self.parent, bg=BG)
        self.chart_frame.pack(fill="both", expand=True, padx=12, pady=8)

        self._canvas = None

    def _run(self):
        try:
            frames = int(self.e_frames.get())
            refs   = [int(x) for x in self.e_refs.get().split()]
        except ValueError:
            messagebox.showerror("Error", "Invalid input")
            return

        results = compare_algorithms(refs, frames)

        log_clear(self.log)
        log_write(self.log,
                  f"Reference String: {refs}", "info")
        log_write(self.log,
                  f"{'Algorithm':<10} {'Faults':>8} {'Hits':>8} {'Fault Rate':>12}", "header")
        log_write(self.log, "─" * 44, "header")

        for name, (steps, stats) in results.items():
            hits = stats.total_accesses - stats.page_faults
            log_write(self.log,
                      f"{name:<10} {stats.page_faults:>8} {hits:>8} "
                      f"{stats.page_fault_rate()*100:>11.1f}%",
                      "fault" if name == "FIFO" else
                      "warn"  if name == "LRU"  else "hit")

        optimal_faults = results["Optimal"][1].page_faults
        log_write(self.log,
                  f"\n  Optimal is the theoretical minimum: {optimal_faults} faults",
                  "info")

        # Render chart
        if self._canvas:
            self._canvas.get_tk_widget().destroy()

        self._canvas = create_algorithm_comparison(results, self.chart_frame)
        if self._canvas:
            self._canvas.get_tk_widget().pack(fill="both", expand=True)


# ─────────────────────────────────────────────────────────────
#  TAB 4 — GRAPHS & ANALYSIS
# ─────────────────────────────────────────────────────────────

class GraphsTab:
    """
    Generates the Denning thrashing curve and fault rate timelines.
    Runs the thrashing experiment (vary #processes from 1 to max)
    and plots results.
    """

    def __init__(self, parent):
        self.parent = parent
        self._build()
        self._canvases = []

    def _build(self):
        ctrl = tk.Frame(self.parent, bg=BG2)
        ctrl.pack(fill="x", padx=12, pady=8)

        make_label(ctrl, "RAM Frames:").grid(row=0, column=0, padx=6)
        self.e_frames = make_entry(ctrl, width=5, default="8")
        self.e_frames.grid(row=0, column=1)

        make_label(ctrl, "Max Processes:").grid(row=0, column=2, padx=6)
        self.e_max = make_entry(ctrl, width=5, default="8")
        self.e_max.grid(row=0, column=3)

        make_label(ctrl, "Algorithm:").grid(row=0, column=4, padx=6)
        self.algo_var = tk.StringVar(value="LRU")
        for i, a in enumerate(["FIFO", "LRU", "Optimal"]):
            tk.Radiobutton(ctrl, text=a, variable=self.algo_var, value=a,
                           bg=BG2, fg=FG, selectcolor=ACCENT2,
                           activebackground=BG2,
                           font=("Helvetica", 10)).grid(row=0, column=5+i, padx=4)

        btn_frame = tk.Frame(self.parent, bg=BG2)
        btn_frame.pack(fill="x", padx=12, pady=4)
        make_button(btn_frame, "📊  Generate Thrashing Curves",
                    self._run).pack(side="left", padx=4)

        self.status = make_label(self.parent,
                                 "Configure and click Generate to see graphs.",
                                 fg=FG2)
        self.status.pack(pady=4)

        self.chart_frame = tk.Frame(self.parent, bg=BG)
        self.chart_frame.pack(fill="both", expand=True, padx=12, pady=8)

    def _run(self):
        try:
            frames      = int(self.e_frames.get())
            max_procs   = int(self.e_max.get())
            algo_name   = self.algo_var.get()
        except ValueError:
            messagebox.showerror("Error", "Invalid input")
            return

        self.status.config(text="⏳ Running experiment… please wait")
        self.parent.update()

        # Run in thread to keep GUI responsive
        def do_run():
            results = run_thrashing_experiment(
                num_frames=frames,
                max_processes=max_procs,
                algorithm_name=algo_name
            )
            self.parent.after(0, lambda: self._show_graphs(results))

        threading.Thread(target=do_run, daemon=True).start()

    def _show_graphs(self, results):
        # Clear old charts
        for w in self.chart_frame.winfo_children():
            w.destroy()

        canvas = create_thrashing_graph(results, self.chart_frame)
        if canvas:
            canvas.get_tk_widget().pack(fill="both", expand=True)

        thrash_count = sum(1 for r in results if r["thrashing"])
        self.status.config(
            text=f"✅ Done. Thrashing detected in {thrash_count} of "
                 f"{len(results)} configurations."
        )
