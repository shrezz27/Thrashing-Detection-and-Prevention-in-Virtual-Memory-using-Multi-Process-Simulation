"""
=============================================================
  MODULE: visualizer.py
  PURPOSE: Generates matplotlib graphs to visualize thrashing:
    1. Page Faults vs Number of Processes
    2. CPU Utilization vs Number of Processes (classic Denning curve)
    3. Per-process page fault rate over time
    4. Algorithm comparison bar chart
=============================================================
"""

import matplotlib
matplotlib.use("TkAgg")   # Use Tkinter backend for embedding in GUI
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np


# ─── Color Palette ──────────────────────────────────────────
COLORS = {
    "normal"     : "#2ecc71",   # Green — normal operation
    "warning"    : "#f39c12",   # Orange — approaching thrashing
    "thrashing"  : "#e74c3c",   # Red — thrashing detected
    "fifo"       : "#3498db",   # Blue
    "lru"        : "#9b59b6",   # Purple
    "optimal"    : "#27ae60",   # Dark green
    "cpu"        : "#1abc9c",   # Teal
    "bg"         : "#1a1a2e",   # Dark background
    "fg"         : "#eaeaea",   # Light text
    "grid"       : "#2d2d4e",   # Grid lines
}

FONT = {"family": "monospace", "size": 10}


def _style_ax(ax, title="", xlabel="", ylabel=""):
    """Apply consistent dark-theme styling to a matplotlib axis."""
    ax.set_facecolor(COLORS["bg"])
    ax.tick_params(colors=COLORS["fg"], labelsize=9)
    ax.xaxis.label.set_color(COLORS["fg"])
    ax.yaxis.label.set_color(COLORS["fg"])
    ax.title.set_color(COLORS["fg"])
    ax.spines['bottom'].set_color(COLORS["grid"])
    ax.spines['top'].set_color(COLORS["grid"])
    ax.spines['left'].set_color(COLORS["grid"])
    ax.spines['right'].set_color(COLORS["grid"])
    ax.grid(True, color=COLORS["grid"], linestyle="--", alpha=0.6)
    if title:  ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    if xlabel: ax.set_xlabel(xlabel)
    if ylabel: ax.set_ylabel(ylabel)


def create_thrashing_graph(experiment_results, parent_frame=None):
    """
    Plot two classic thrashing curves:
      LEFT:  Page Faults vs Number of Processes
      RIGHT: CPU Utilization vs Number of Processes
    
    The right graph is Peter Denning's famous thrashing curve —
    CPU utilization first rises as more processes are added,
    then collapses when thrashing begins.
    
    Args:
        experiment_results: Output of run_thrashing_experiment()
        parent_frame: If provided, embed in this Tkinter frame
    
    Returns:
        canvas (FigureCanvasTkAgg) if embedded, else None
    """
    xs      = [r["num_processes"] for r in experiment_results]
    faults  = [r["total_faults"]  for r in experiment_results]
    cpu     = [r["cpu_util"]      for r in experiment_results]
    thresh  = [r["thrashing"]     for r in experiment_results]

    fig = Figure(figsize=(12, 5), facecolor=COLORS["bg"])
    gs  = gridspec.GridSpec(1, 2, figure=fig, wspace=0.35)

    # ── LEFT: Page Faults vs Processes ──
    ax1 = fig.add_subplot(gs[0])
    _style_ax(ax1,
              title="Page Faults vs Number of Processes",
              xlabel="Number of Processes",
              ylabel="Total Page Faults")

    for i, (x, y, is_t) in enumerate(zip(xs, faults, thresh)):
        color = COLORS["thrashing"] if is_t else COLORS["normal"]
        ax1.bar(x, y, color=color, alpha=0.85, width=0.6, zorder=3)

    ax1.plot(xs, faults, color=COLORS["warning"],
             linewidth=2, linestyle="--", marker="o",
             markersize=5, zorder=4, label="Trend")

    # Mark thrashing onset
    for i, (x, is_t) in enumerate(zip(xs, thresh)):
        if is_t:
            ax1.axvline(x=x, color=COLORS["thrashing"],
                        linewidth=1.5, linestyle=":", alpha=0.7)
            ax1.text(x, max(faults) * 0.9, "⚠ THRASH",
                     color=COLORS["thrashing"], fontsize=8,
                     ha="center", rotation=90)
            break

    ax1.legend(facecolor=COLORS["bg"], labelcolor=COLORS["fg"])

    # ── RIGHT: CPU Utilization vs Processes ──
    ax2 = fig.add_subplot(gs[1])
    _style_ax(ax2,
              title="CPU Utilization vs Number of Processes\n(Denning's Thrashing Curve)",
              xlabel="Number of Processes",
              ylabel="CPU Utilization (%)")

    cpu_pct = [c * 100 for c in cpu]

    # Color segments: green (normal) → red (thrashing)
    for i in range(len(xs) - 1):
        c = COLORS["thrashing"] if thresh[i] else COLORS["cpu"]
        ax2.plot(xs[i:i+2], cpu_pct[i:i+2], color=c,
                 linewidth=2.5, zorder=3)

    ax2.scatter(xs, cpu_pct,
                color=[COLORS["thrashing"] if t else COLORS["cpu"] for t in thresh],
                s=60, zorder=5)

    # Fill under curve
    ax2.fill_between(xs, cpu_pct, alpha=0.15, color=COLORS["cpu"])

    # Thrashing zone annotation
    thrash_start = next((x for x, t in zip(xs, thresh) if t), None)
    if thrash_start:
        ax2.axvspan(thrash_start, max(xs), alpha=0.1,
                    color=COLORS["thrashing"], label="Thrashing Zone")
        ax2.legend(facecolor=COLORS["bg"], labelcolor=COLORS["fg"])

    ax2.set_ylim(0, 110)
    ax2.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:.0f}%")
    )

    if parent_frame:
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        return canvas
    else:
        plt.show()
        return None


def create_algorithm_comparison(comparison_results, parent_frame=None):
    """
    Bar chart comparing FIFO, LRU, and Optimal page faults
    for the same reference string.
    
    Args:
        comparison_results: Output of compare_algorithms()
        parent_frame: Tkinter frame to embed into
    """
    algos  = list(comparison_results.keys())
    faults = [comparison_results[a][1].page_faults for a in algos]
    rates  = [comparison_results[a][1].page_fault_rate() * 100 for a in algos]
    colors = [COLORS["fifo"], COLORS["lru"], COLORS["optimal"]]

    fig = Figure(figsize=(8, 4), facecolor=COLORS["bg"])
    ax  = fig.add_subplot(111)
    _style_ax(ax,
              title="Algorithm Comparison — Page Faults",
              xlabel="Algorithm",
              ylabel="Total Page Faults")

    bars = ax.bar(algos, faults, color=colors, alpha=0.85,
                  width=0.5, zorder=3)

    # Annotate bars with fault count and rate
    for bar, f, r in zip(bars, faults, rates):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.2,
                f"{f} faults\n({r:.1f}%)",
                ha="center", va="bottom",
                color=COLORS["fg"], fontsize=9, fontweight="bold")

    # Reference lines
    if faults:
        ax.set_ylim(0, max(faults) * 1.3)

    if parent_frame:
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        return canvas
    else:
        plt.show()
        return None


def create_fault_rate_timeline(processes_data, parent_frame=None):
    """
    Line graph: page fault rate over time for each process.
    Shows how fault rate evolves as the simulation progresses.
    
    Args:
        processes_data: List of Process objects with .steps data
        parent_frame: Tkinter frame to embed into
    """
    proc_colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12",
                   "#9b59b6", "#1abc9c", "#e67e22", "#95a5a6"]

    fig = Figure(figsize=(10, 4), facecolor=COLORS["bg"])
    ax  = fig.add_subplot(111)
    _style_ax(ax,
              title="Page Fault Rate Over Time (per process)",
              xlabel="Memory Access #",
              ylabel="Cumulative Fault Rate")

    for i, proc in enumerate(processes_data):
        if not proc.stats.fault_history:
            continue
        rates = proc.stats.fault_history
        xs    = list(range(1, len(rates) + 1))
        color = proc_colors[i % len(proc_colors)]
        ax.plot(xs, rates, color=color, linewidth=2,
                label=proc.name, alpha=0.9)

    # Thrashing threshold line
    from process_sim import MultiProcessScheduler
    thresh = MultiProcessScheduler.THRASHING_THRESHOLD
    ax.axhline(y=thresh, color=COLORS["thrashing"],
               linewidth=1.5, linestyle="--",
               label=f"Thrashing Threshold ({thresh*100:.0f}%)")

    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda y, _: f"{y*100:.0f}%")
    )
    ax.legend(facecolor=COLORS["bg"], labelcolor=COLORS["fg"],
              fontsize=8, loc="upper right")

    if parent_frame:
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        return canvas
    else:
        plt.show()
        return None


def create_working_set_graph(ws_trackers, parent_frame=None):
    """
    Visualize working set sizes over time for each process.
    
    Shows how the working set grows and shrinks as processes
    move through different phases of execution.
    
    Args:
        ws_trackers: List of WorkingSetTracker objects
        parent_frame: Tkinter frame to embed into
    """
    proc_colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12",
                   "#9b59b6", "#1abc9c"]

    fig = Figure(figsize=(10, 4), facecolor=COLORS["bg"])
    ax  = fig.add_subplot(111)
    _style_ax(ax,
              title="Working Set Size Over Time (Δ window)",
              xlabel="Simulation Tick",
              ylabel="|W(t, Δ)| — Working Set Size")

    for i, tracker in enumerate(ws_trackers):
        if not tracker.history:
            continue
        ticks    = [h[0] for h in tracker.history]
        ws_sizes = [h[1] for h in tracker.history]
        color    = proc_colors[i % len(proc_colors)]
        ax.plot(ticks, ws_sizes, color=color, linewidth=2,
                label=f"P{tracker.process_id}", alpha=0.9)

    ax.legend(facecolor=COLORS["bg"], labelcolor=COLORS["fg"],
              fontsize=8)

    if parent_frame:
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        return canvas
    else:
        plt.show()
        return None
