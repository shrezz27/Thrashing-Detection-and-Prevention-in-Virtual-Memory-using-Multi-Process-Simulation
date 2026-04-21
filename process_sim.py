"""
=============================================================
  MODULE: process_sim.py  (v2 — Tuple Pages + Detailed Logging)
=============================================================

WHAT CHANGED FROM v1:
  ─────────────────────────────────────────────────────────
  PART 1 — Tuple-based pages
    All page accesses use (process_id, page_number) tuples.
    find_frame_by_page() checks the full tuple — no cross-process hits.
    future_refs passed to Optimal are also tuples.

  PART 2 — Detailed round logging (like single-process)
    run_round_robin() now returns a third value: `round_logs`
    Each round's log is a list of human-readable strings:
      - Header: "════ ROUND N ════"
      - One line per step: who accessed what, HIT or FAULT
      - Frame state after every step
      - Eviction reason (FIFO: oldest / LRU: stalest / Optimal: farthest)

  PART 3 — Round summary with formula display
    Each round summary dict now includes a pre-formatted
    `display` string showing:
      Accesses = N
      Faults   = M
      Fault Rate = M/N = X%
      CPU = max(0, 1 - (X × 1.5)) = Y%
      → THRASHING / OK

  PART 4 — Suspension explanation
    _suspend_process() now returns a rich dict with:
      - which process was suspended
      - its fault rate at suspension time
      - how many frames were freed

  PART 5 — Enhanced process summary table
    get_summary_table() includes formula string for fault rate.
─────────────────────────────────────────────────────────────
"""

import random
from memory_core import RAM, PageFaultStats
from algorithms import FIFO, LRU, Optimal, SimulationEngine


# ─────────────────────────────────────────────────────────────
#  PROCESS CLASS
# ─────────────────────────────────────────────────────────────

class Process:
    """
    One process: a name, an ID, and a list of page references.
    v2: reference_string contains plain ints (page numbers).
        The tuple (process_id, page) is constructed at scheduling time.
    """
    def __init__(self, process_id, reference_string, name=None):
        self.process_id       = process_id
        self.reference_string = reference_string   # list of int page numbers
        self.name             = name or f"P{process_id}"
        self.stats            = PageFaultStats(process_id)
        self.steps            = []
        self.active           = True

    def working_set_size(self, window=5):
        recent = self.reference_string[-window:]
        return len(set(recent))

    @staticmethod
    def generate_random(process_id, num_pages=10, length=20, locality=True):
        pages        = list(range(num_pages))
        refs         = []
        recent_pages = random.sample(pages, min(3, len(pages)))
        for _ in range(length):
            if locality and recent_pages and random.random() < 0.7:
                page = random.choice(recent_pages)
            else:
                page = random.choice(pages)
                if page not in recent_pages:
                    recent_pages.append(page)
                    if len(recent_pages) > 5:
                        recent_pages.pop(0)
            refs.append(page)
        return Process(process_id, refs)

    def __repr__(self):
        return (f"Process({self.name}, "
                f"refs={len(self.reference_string)}, "
                f"active={self.active})")


# ─────────────────────────────────────────────────────────────
#  MULTI-PROCESS SCHEDULER  (v2)
# ─────────────────────────────────────────────────────────────

class MultiProcessScheduler:
    """
    Round-robin multi-process scheduler on shared RAM.

    v2 additions:
      - Tuple-based page identity (Part 1)
      - Per-step detailed log lines (Part 2)
      - Formatted round summary with formulas (Part 3)
      - Rich suspension explanation (Part 4)
    """

    THRASHING_THRESHOLD = 0.6

    def __init__(self, ram: RAM, algorithm_name="LRU",
                 thrashing_threshold=None, prevent_thrashing=False):
        self.ram                 = ram
        self.algorithm_name      = algorithm_name
        self.thrashing_threshold = thrashing_threshold or self.THRASHING_THRESHOLD
        self.prevent_thrashing   = prevent_thrashing

        self.algorithm = self._build_algorithm(algorithm_name, ram)
        self.processes     = []
        self.all_steps     = []
        self.round_summary = []
        self.round_logs    = []   # NEW: list of lists of log strings per round

    def _build_algorithm(self, name, ram):
        algos = {"FIFO": FIFO, "LRU": LRU, "Optimal": Optimal}
        if name not in algos:
            raise ValueError(f"Unknown algorithm: {name}")
        return algos[name](ram)

    def add_process(self, process: Process):
        self.processes.append(process)

    # ─────────────────────────────────────────────────────────
    #  MAIN SIMULATION LOOP
    # ─────────────────────────────────────────────────────────

    def run_round_robin(self, accesses_per_turn=3):
        """
        Run all processes in round-robin order.

        Returns:
            all_steps    : flat list of step dicts
            round_summary: list of per-round metric dicts (with display string)
            round_logs   : list of per-round log-line lists (for GUI display)
        """
        ref_indices = {p.process_id: 0 for p in self.processes}
        max_len     = max(len(p.reference_string) for p in self.processes)
        num_rounds  = (max_len + accesses_per_turn - 1) // accesses_per_turn

        for round_num in range(num_rounds):
            round_faults   = 0
            round_accesses = 0
            round_step_num = 0       # step counter within this round
            log_lines      = []      # log lines for this round

            # ── Round header ──────────────────────────────────
            log_lines.append(f"{'═'*52}")
            log_lines.append(f"  ROUND {round_num}")
            log_lines.append(f"{'═'*52}")

            for process in self.processes:
                if not process.active:
                    log_lines.append(
                        f"  [{process.name} is SUSPENDED — skipped]"
                    )
                    continue

                pid   = process.process_id
                pname = process.name
                start = ref_indices[pid]
                end   = start + accesses_per_turn
                chunk = process.reference_string[start:end]

                if not chunk:
                    log_lines.append(f"  [{pname} finished its reference string]")
                    continue

                ref_indices[pid] = end

                # ── Per-access loop ───────────────────────────
                for i, page_num in enumerate(chunk):
                    self.ram.tick_clock()
                    round_step_num += 1

                    # The UNIQUE page identity in v2
                    page_tuple = (pname, page_num)

                    # ── Check hit / fault ─────────────────────
                    frame = self.ram.find_frame_by_page(pname, page_num)
                    was_fault = frame is None

                    evicted_tuple = None
                    eviction_reason = ""

                    if was_fault:
                        empty = self.ram.get_empty_frames()
                        if empty:
                            target       = empty[0]
                            evicted_tuple = None
                        else:
                            # Build future_refs as TUPLES for Optimal
                            future_page_nums = process.reference_string[
                                ref_indices[pid] - len(chunk) + i + 1 :
                            ]
                            future_refs = [(pname, pg) for pg in future_page_nums]

                            vid    = self.algorithm.select_victim(
                                process_id=pname, future_refs=future_refs
                            )
                            target = self.ram.frames[vid]
                            # Capture reason BEFORE evict() clears page_tuple
                            if target.page_tuple:
                                epid_pre, epg_pre = target.page_tuple
                                eviction_reason = self._eviction_reason(
                                    epid_pre, epg_pre, target
                                )
                            else:
                                eviction_reason = ""
                            evicted_tuple = target.evict()   # now clear frame

                        target.load(page_tuple, self.ram.tick)
                        loaded_frame = target.frame_id
                    else:
                        loaded_frame  = frame.frame_id

                    process.stats.record_access(was_fault)
                    round_faults   += int(was_fault)
                    round_accesses += 1

                    # ── Build log line (Part 2) ───────────────
                    status = "FAULT" if was_fault else "HIT  "
                    line1  = (
                        f"  Step {round_step_num:2d}: {pname} accesses "
                        f"({pname},{page_num}) → {status} "
                        f"→ Frame {loaded_frame}"
                    )
                    log_lines.append(line1)

                    if was_fault and evicted_tuple:
                        ep, epg = evicted_tuple
                        log_lines.append(
                            f"          Evicted ({ep},{epg}) "
                            f"← {self._eviction_reason_str(target, ep, epg)}"
                        )

                    frame_state = self.ram.get_snapshot_inline()
                    log_lines.append(
                        f"          Frames: {frame_state}  "
                        f"[{pname} faults so far: "
                        f"{process.stats.page_faults}]"
                    )

                    # ── Step dict for graphs ──────────────────
                    step = {
                        "tick"          : self.ram.tick,
                        "round"         : round_num,
                        "process_id"    : pid,
                        "process_name"  : pname,
                        "page"          : page_num,
                        "page_tuple"    : page_tuple,
                        "fault"         : was_fault,
                        "evicted_tuple" : evicted_tuple,
                        "loaded_frame"  : loaded_frame,
                        "fault_count"   : process.stats.page_faults,
                        "fault_rate"    : process.stats.page_fault_rate(),
                        "ram_snapshot"  : self.ram.get_snapshot(),
                        "algorithm"     : self.algorithm_name,
                        "active_procs"  : [p.process_id for p in self.processes
                                           if p.active],
                    }
                    process.steps.append(step)
                    self.all_steps.append(step)

                log_lines.append("")  # blank line between processes

            # ── End of round: metrics (Part 3) ────────────────
            system_fault_rate = (round_faults / round_accesses
                                 if round_accesses > 0 else 0.0)
            cpu_raw  = 1.0 - system_fault_rate * 1.5
            cpu_util = max(0.0, cpu_raw)
            is_thrashing = system_fault_rate >= self.thrashing_threshold

            # Formatted round summary with explicit formula
            rate_pct = system_fault_rate * 100
            cpu_pct  = cpu_util * 100
            summary_lines = [
                f"",
                f"  ── Round {round_num} Summary ──",
                f"  Accesses   = {round_accesses}",
                f"  Faults     = {round_faults}",
                f"  Fault Rate = {round_faults}/{round_accesses} "
                f"= {rate_pct:.1f}%",
                f"  CPU        = max(0, 1 − ({rate_pct:.1f}% × 1.5)) "
                f"= {cpu_pct:.1f}%",
            ]

            if is_thrashing:
                summary_lines.append(
                    f"  → ⚠  THRASHING (rate {rate_pct:.1f}% "
                    f"≥ threshold {self.thrashing_threshold*100:.0f}%)"
                )
            else:
                summary_lines.append(
                    f"  → ✅ OK (rate {rate_pct:.1f}% "
                    f"< threshold {self.thrashing_threshold*100:.0f}%)"
                )

            # ── Suspension (Part 4) ───────────────────────────
            suspension_info = None
            if is_thrashing and self.prevent_thrashing:
                suspension_info = self._suspend_process()
                if suspension_info:
                    summary_lines.append(
                        f"  → Suspending {suspension_info['name']} "
                        f"because it has the highest fault rate "
                        f"({suspension_info['fault_rate_pct']:.1f}%)."
                    )
                    summary_lines.append(
                        f"     Freed {suspension_info['frames_freed']} frames "
                        f"back to the pool."
                    )

            log_lines.extend(summary_lines)
            self.round_logs.append(log_lines)

            summary = {
                "round"             : round_num,
                "active_processes"  : sum(1 for p in self.processes if p.active),
                "round_faults"      : round_faults,
                "round_accesses"    : round_accesses,
                "system_fault_rate" : system_fault_rate,
                "cpu_utilization"   : cpu_util,
                "is_thrashing"      : is_thrashing,
                "suspended"         : suspension_info["pid"] if suspension_info else None,
                "suspension_info"   : suspension_info,
                "process_fault_rates": {
                    p.process_id: p.stats.page_fault_rate()
                    for p in self.processes
                },
                "log_lines"         : log_lines,   # embed for easy retrieval
            }
            self.round_summary.append(summary)

        return self.all_steps, self.round_summary, self.round_logs

    # ─────────────────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────────────────

    def _eviction_reason(self, evicted_pid, evicted_pg, frame):
        """Generate reason string BEFORE the frame is overwritten."""
        algo = self.algorithm_name
        if algo == "FIFO":
            return (f"FIFO — ({evicted_pid},{evicted_pg}) "
                    f"loaded earliest (tick {frame.loaded_at})")
        elif algo == "LRU":
            return (f"LRU — ({evicted_pid},{evicted_pg}) "
                    f"last used at tick {frame.last_used} (stalest)")
        else:
            return f"Optimal — ({evicted_pid},{evicted_pg}) used farthest in future"

    def _eviction_reason_str(self, frame, evicted_pid, evicted_pg):
        """
        Reason string after eviction (frame now holds new page).
        We use stored tick info still available on the frame object.
        """
        algo = self.algorithm_name
        if algo == "FIFO":
            return f"FIFO (was loaded at tick {frame.loaded_at}, oldest)"
        elif algo == "LRU":
            return f"LRU (last used tick {frame.last_used}, stalest)"
        else:
            return "Optimal (used farthest in future)"

    def _suspend_process(self):
        """
        Suspend the process with the highest fault rate.
        Returns a rich info dict (Part 4).
        """
        active = [p for p in self.processes if p.active]
        if len(active) <= 1:
            return None

        worst = max(active, key=lambda p: p.stats.page_fault_rate())
        worst.active = False

        frames_freed = 0
        for frame in self.ram.frames:
            if frame.page_tuple and frame.page_tuple[0] == worst.name:
                frame.evict()
                frames_freed += 1

        return {
            "pid"            : worst.process_id,
            "name"           : worst.name,
            "fault_rate_pct" : worst.stats.page_fault_rate() * 100,
            "frames_freed"   : frames_freed,
        }

    # ─────────────────────────────────────────────────────────
    #  SUMMARY TABLE (Part 5 — Enhanced)
    # ─────────────────────────────────────────────────────────

    def get_summary_table(self):
        """
        Per-process summary. Now includes formula string for fault rate.
        """
        rows = []
        for p in self.processes:
            f   = p.stats.page_faults
            a   = p.stats.total_accesses
            r   = p.stats.page_fault_rate()
            rows.append({
                "Process"     : p.name,
                "Accesses"    : a,
                "Page Faults" : f,
                "Fault Rate"  : f"{f}/{a} = {r*100:.1f}%",
                "Active"      : "Active" if p.active else "SUSPENDED",
            })
        return rows


# ─────────────────────────────────────────────────────────────
#  THRASHING EXPERIMENT — unchanged API, internal tuple fix
# ─────────────────────────────────────────────────────────────

def run_thrashing_experiment(num_frames, max_processes=8,
                             pages_per_process=10,
                             refs_per_process=30,
                             algorithm_name="LRU"):
    """
    Vary number of processes 1→max on fixed RAM.
    Returns list of {num_processes, total_faults, fault_rate, cpu_util, thrashing}.
    """
    results = []

    for n in range(1, max_processes + 1):
        ram   = RAM(num_frames)
        sched = MultiProcessScheduler(ram, algorithm_name,
                                      prevent_thrashing=False)
        for pid in range(n):
            proc = Process.generate_random(
                pid, num_pages=pages_per_process,
                length=refs_per_process, locality=True
            )
            sched.add_process(proc)

        _, round_summary, _ = sched.run_round_robin(accesses_per_turn=3)

        total_faults   = sum(r["round_faults"]    for r in round_summary)
        total_accesses = sum(r["round_accesses"]   for r in round_summary)
        avg_cpu        = (sum(r["cpu_utilization"] for r in round_summary)
                          / max(len(round_summary), 1))
        fault_rate     = total_faults / max(total_accesses, 1)
        is_thrashing   = fault_rate >= MultiProcessScheduler.THRASHING_THRESHOLD

        results.append({
            "num_processes" : n,
            "total_faults"  : total_faults,
            "fault_rate"    : fault_rate,
            "cpu_util"      : avg_cpu,
            "thrashing"     : is_thrashing,
        })

    return results
