"""
=============================================================
  SAMPLE INPUTS AND OUTPUTS
  Thrashing in Virtual Memory — OS Simulation
=============================================================

─────────────────────────────────────────────────────────────
SAMPLE 1: Classic Silberschatz Example (from OS textbook)
─────────────────────────────────────────────────────────────
Input:
  Frames          : 3
  Algorithm       : All three
  Reference String: 7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1

Expected Output:
  FIFO   : 15 faults / 20 accesses (75.0%)
  LRU    : 12 faults / 20 accesses (60.0%)
  Optimal:  9 faults / 20 accesses (45.0%)

Why Optimal wins: It always evicts the page used furthest in the future,
which is mathematically the minimum possible faults for any algorithm.


─────────────────────────────────────────────────────────────
SAMPLE 2: Belady's Anomaly Demonstration (FIFO only)
─────────────────────────────────────────────────────────────
Reference String: 1 2 3 4 1 2 5 1 2 3 4 5

With 3 frames (FIFO): 9 page faults
With 4 frames (FIFO): 10 page faults  ← MORE faults with MORE frames!

This counterintuitive result is Belady's Anomaly.
LRU and Optimal do NOT suffer from this anomaly (they are "stack algorithms").


─────────────────────────────────────────────────────────────
SAMPLE 3: Working Set Model Trace
─────────────────────────────────────────────────────────────
Process P0, Window Δ=5, Reference String: 1 2 3 1 2 4 5 1 2

Tick  Page  Working Set         |WS|
   0     1  {1}                    1
   1     2  {1, 2}                 2
   2     3  {1, 2, 3}              3
   3     1  {1, 2, 3}              3   ← already in window
   4     2  {1, 2, 3}              3
   5     4  {1, 2, 3, 4}           4
   6     5  {1, 2, 3, 4, 5}        5
   7     1  {1, 2, 4, 5}           4   ← page 3 fell out of window
   8     2  {1, 2, 4, 5}           4

Interpretation:
  At tick 7, the working set is {1, 2, 4, 5}.
  Process P0 needs at least 4 frames to avoid thrashing at that point.


─────────────────────────────────────────────────────────────
SAMPLE 4: Multi-Process Thrashing Experiment
─────────────────────────────────────────────────────────────
Configuration: 8 RAM frames, LRU algorithm

Num Procs  Total Faults  Fault Rate  CPU Util   Status
─────────────────────────────────────────────────────
    1            13        21.7%       67.5%     OK
    2            45        75.0%        0.0%   ⚠ THRASHING
    3            70        77.8%        1.7%   ⚠ THRASHING
    4            97        80.8%        0.0%   ⚠ THRASHING
    5           122        81.3%        1.0%   ⚠ THRASHING
    6           151        83.9%        0.0%   ⚠ THRASHING

Key Insight (Denning's Curve):
  - With 1 process: CPU utilization is ~67% — room to add more processes
  - With 2 processes: Sudden collapse to 0% — THRASHING begins
  - This is the classic "knee of the curve" in virtual memory theory


─────────────────────────────────────────────────────────────
SAMPLE 5: Thrashing Prevention (Process Suspension)
─────────────────────────────────────────────────────────────
Setup: 4 processes, 6 frames, thrashing prevention ENABLED

Round  0: Faults=12  Rate=80.0%  CPU= 0.0%  ⚠ THRASHING → Suspend P3
Round  1: Faults= 8  Rate=72.7%  CPU= 9.1%  ⚠ THRASHING → Suspend P2
Round  2: Faults= 5  Rate=55.6%  CPU=16.7%  ✅ Stabilized
Round  3: Faults= 3  Rate=42.9%  CPU=35.7%  ✅ Normal
Round  4: Faults= 2  Rate=33.3%  CPU=50.0%  ✅ Normal

After prevention: P0 and P1 continue executing with acceptable fault rates.
P2 and P3 are swapped out (medium-term scheduler) until more frames free up.


─────────────────────────────────────────────────────────────
THEORY REFERENCE: Why Thrashing Happens
─────────────────────────────────────────────────────────────

1. OS sees low CPU utilization → adds more processes
2. More processes compete for same frames → more page faults
3. Processes spend time waiting for pages (I/O) → CPU idle
4. OS sees low CPU utilization again → adds EVEN MORE processes
5. Cycle worsens → CPU utilization collapses: THRASHING

Solution (Peter Denning, 1968 — Working Set Model):
  Monitor each process's working set W(t, Δ).
  Only allow a process to run if there are enough free frames for its working set.
  If  Σ|W(t, Δ)| > total_frames  →  suspend a process.

This breaks the thrashing cycle by reducing multiprogramming degree.
"""
