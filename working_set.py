"""
=============================================================
  MODULE: working_set.py
  PURPOSE: Implements the Working Set Model (Peter Denning, 1968)
           and Dynamic Frame Allocation for thrashing prevention.
=============================================================

WORKING SET MODEL:
  The working set W(t, Δ) of a process at time t is the set of
  pages it referenced in the past Δ time units (the window).
  
  If sum of all working sets > total frames → thrashing is inevitable.
  Solution: Reduce multiprogramming degree (suspend a process).
  
  This model is the foundation for understanding thrashing.
  Denning's 1968 paper "The Working Set Model for Program Behavior"
  fundamentally changed OS memory management.
"""

from collections import deque


class WorkingSetTracker:
    """
    Tracks the working set for a single process over a sliding window.
    
    At each memory access, we maintain a window of the last Δ references.
    The working set is the set of UNIQUE pages in that window.
    
    A process needs AT LEAST |W(t, Δ)| frames to avoid thrashing.
    """

    def __init__(self, process_id, window_size=5):
        """
        Args:
            process_id  : ID of the process being tracked
            window_size : Δ — how many past references to consider (Δ)
        """
        self.process_id  = process_id
        self.window_size = window_size
        self.window      = deque(maxlen=window_size)  # Last Δ references
        self.history     = []   # (tick, working_set_size) for graphing

    def access(self, page, tick):
        """
        Record a page access and update the working set.
        
        Args:
            page : Page number accessed
            tick : Current simulation tick
        """
        self.window.append(page)
        ws_size = self.working_set_size()
        self.history.append((tick, ws_size))

    def working_set(self):
        """Return the current working set (set of unique pages in window)."""
        return set(self.window)

    def working_set_size(self):
        """Return |W(t, Δ)| — number of distinct pages in current window."""
        return len(self.working_set())

    def get_history(self):
        """Return list of (tick, working_set_size) for visualization."""
        return self.history

    def __repr__(self):
        return (f"WS(P{self.process_id}, Δ={self.window_size}): "
                f"{self.working_set()} [size={self.working_set_size()}]")


class DynamicFrameAllocator:
    """
    Dynamically allocates frames to processes based on their working sets.
    
    Algorithm:
      1. Compute working set size for each active process
      2. Total demand = sum of all working set sizes
      3. If total demand > available frames → suspend a process
      4. Else allocate frames proportionally to working set sizes
    
    This prevents thrashing by ensuring each process has enough
    frames to hold its working set.
    """

    def __init__(self, total_frames, window_size=5):
        self.total_frames = total_frames
        self.window_size  = window_size
        self.trackers     = {}   # {process_id: WorkingSetTracker}

    def add_process(self, process_id):
        """Register a new process for tracking."""
        self.trackers[process_id] = WorkingSetTracker(
            process_id, self.window_size
        )

    def remove_process(self, process_id):
        """Remove a process (when suspended)."""
        self.trackers.pop(process_id, None)

    def update(self, process_id, page, tick):
        """Record a memory access for a process."""
        if process_id in self.trackers:
            self.trackers[process_id].access(page, tick)

    def compute_allocations(self):
        """
        Compute how many frames each process should receive.
        
        Simple proportional allocation:
          frames_i = round(ws_size_i / total_demand * total_frames)
        
        Ensures every process gets at least 1 frame.
        
        Returns:
            allocations : {process_id: num_frames}
            total_demand: sum of all working set sizes
            is_overloaded: True if demand > total frames
        """
        if not self.trackers:
            return {}, 0, False

        ws_sizes = {
            pid: t.working_set_size()
            for pid, t in self.trackers.items()
        }
        total_demand = sum(ws_sizes.values())
        is_overloaded = total_demand > self.total_frames

        allocations = {}
        if total_demand == 0:
            # Distribute equally if no data yet
            per_proc = self.total_frames // len(self.trackers)
            for pid in self.trackers:
                allocations[pid] = max(1, per_proc)
        else:
            for pid, ws in ws_sizes.items():
                alloc = round(ws / total_demand * self.total_frames)
                allocations[pid] = max(1, alloc)  # Minimum 1 frame

        return allocations, total_demand, is_overloaded

    def should_suspend(self):
        """
        Return True and the PID of the best process to suspend
        if total demand exceeds available frames.
        """
        allocations, total_demand, overloaded = self.compute_allocations()

        if not overloaded:
            return False, None

        # Suspend process with smallest working set
        # (least pages to move back in when resumed)
        if not self.trackers:
            return False, None

        victim = min(
            self.trackers.keys(),
            key=lambda pid: self.trackers[pid].working_set_size()
        )
        return True, victim

    def get_status_report(self, tick):
        """
        Generate a report of working set status for all processes.
        Used for the GUI display.
        """
        allocations, demand, overloaded = self.compute_allocations()
        lines = [
            f"=== Working Set Status @ tick {tick} ===",
            f"Total Frames: {self.total_frames}",
            f"Total Demand: {demand}",
            f"{'OVERLOADED — THRASHING RISK!' if overloaded else 'OK — within capacity'}",
            ""
        ]
        for pid, tracker in self.trackers.items():
            ws = tracker.working_set()
            alloc = allocations.get(pid, 0)
            lines.append(
                f"  P{pid}: WS={sorted(ws)}  |WS|={len(ws)}  "
                f"allocated={alloc} frames"
            )
        return "\n".join(lines)
