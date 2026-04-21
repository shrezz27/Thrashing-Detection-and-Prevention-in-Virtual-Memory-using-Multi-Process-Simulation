"""
=============================================================
  THRASHING IN VIRTUAL MEMORY - Complete Simulation System
  For: Third Year Engineering - Operating Systems Project
=============================================================

CONCEPT:
  Thrashing occurs when a process spends more time swapping pages
  in and out of memory (paging) than actually executing.
  It happens when there are too many processes competing for
  limited physical memory frames.

MODULE OVERVIEW:
  1. memory_core.py    - RAM frames, page tables, page fault logic
  2. algorithms.py     - FIFO, LRU, Optimal page replacement
  3. process_sim.py    - Process and multi-process scheduler
  4. working_set.py    - Working Set Model for thrashing prevention
  5. visualizer.py     - Matplotlib graphs
  6. gui.py            - Tkinter GUI
  7. main.py           - Entry point (this file)
"""

import tkinter as tk
from gui import ThrashingSimulatorGUI

if __name__ == "__main__":
    root = tk.Tk()
    app = ThrashingSimulatorGUI(root)
    root.mainloop()