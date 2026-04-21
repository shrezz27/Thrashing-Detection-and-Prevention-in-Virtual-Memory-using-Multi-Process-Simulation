"""
=============================================================
  MODULE: algorithms.py  (v2 — Tuple-Aware Algorithms)
=============================================================

WHAT CHANGED FROM v1:
  ─────────────────────────────────────────────────────────
  Optimal.select_victim() now compares frame.page_tuple tuples
  against future_refs that are also tuples (pid, page).

  FIFO and LRU are unchanged in logic (they sort by timestamps,
  not by page content), but they now work correctly because
  frame.page_tuple ensures unique identity.

  Single-process SimulationEngine.run_process() calls
  frame.load_legacy() for backward compatibility — no GUI changes.
─────────────────────────────────────────────────────────────

ALGORITHMS:
  1. FIFO  — evict earliest-loaded frame (by loaded_at timestamp)
  2. LRU   — evict least-recently-used frame (by last_used timestamp)
  3. Optimal — evict frame whose page is used furthest in future
"""

from memory_core import RAM, PageTable, PageFaultStats


# ─────────────────────────────────────────────────────────────
#  BASE CLASS
# ─────────────────────────────────────────────────────────────

class PageReplacementAlgorithm:
    def __init__(self, ram: RAM):
        self.ram = ram

    def select_victim(self, process_id=None, future_refs=None):
        """
        Return frame_id of the frame to evict.
        future_refs: list of (pid, page) tuples for Optimal.
        """
        raise NotImplementedError

    def name(self):
        return self.__class__.__name__

    def reason(self, victim_frame):
        """Human-readable reason why this frame was chosen. Used in step logs."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────
#  1. FIFO
# ─────────────────────────────────────────────────────────────

class FIFO(PageReplacementAlgorithm):
    """
    Evict the frame that has been in RAM the longest.
    Decision key: frame.loaded_at (smallest = oldest = evict)
    """
    def select_victim(self, process_id=None, future_refs=None):
        occupied = self.ram.get_occupied_frames()
        if not occupied:
            raise RuntimeError("No frames to evict!")
        victim = min(occupied, key=lambda f: f.loaded_at)
        return victim.frame_id

    def reason(self, victim_frame):
        pid, pg = victim_frame.page_tuple
        return (f"FIFO: ({pid},{pg}) loaded earliest "
                f"(at tick {victim_frame.loaded_at})")


# ─────────────────────────────────────────────────────────────
#  2. LRU
# ─────────────────────────────────────────────────────────────

class LRU(PageReplacementAlgorithm):
    """
    Evict the frame whose page was least recently accessed.
    Decision key: frame.last_used (smallest = stalest = evict)
    """
    def select_victim(self, process_id=None, future_refs=None):
        occupied = self.ram.get_occupied_frames()
        if not occupied:
            raise RuntimeError("No frames to evict!")
        victim = min(occupied, key=lambda f: f.last_used)
        return victim.frame_id

    def reason(self, victim_frame):
        pid, pg = victim_frame.page_tuple
        return (f"LRU: ({pid},{pg}) last used "
                f"at tick {victim_frame.last_used} (stalest)")


# ─────────────────────────────────────────────────────────────
#  3. Optimal
# ─────────────────────────────────────────────────────────────

class Optimal(PageReplacementAlgorithm):
    """
    Evict the frame whose page will not be used for the longest time.

    v2 change: future_refs is now a list of (pid, page) tuples.
    We match frame.page_tuple against these tuples — so cross-process
    future references are correctly ignored.
    """
    def select_victim(self, process_id=None, future_refs=None):
        occupied = self.ram.get_occupied_frames()
        if not occupied:
            raise RuntimeError("No frames to evict!")

        if future_refs is None:
            # Fallback to FIFO if future unknown
            victim = min(occupied, key=lambda f: f.loaded_at)
            return victim.frame_id

        best_frame = None
        farthest   = -1

        for frame in occupied:
            tup = frame.page_tuple   # e.g. ("P0", 5)
            try:
                # Search future_refs (list of tuples) for this exact tuple
                next_use = future_refs.index(tup)
            except ValueError:
                # Never used again → perfect eviction candidate
                return frame.frame_id

            if next_use > farthest:
                farthest   = next_use
                best_frame = frame

        return best_frame.frame_id

    def reason(self, victim_frame):
        pid, pg = victim_frame.page_tuple
        return f"Optimal: ({pid},{pg}) is used farthest in the future"


# ─────────────────────────────────────────────────────────────
#  SIMULATION ENGINE — single-process (unchanged behavior)
# ─────────────────────────────────────────────────────────────

class SimulationEngine:
    """
    Single-process simulation engine. Unchanged from v1.
    Uses load_legacy() for backward compatibility with tuple-based Frame.
    """

    def __init__(self, ram: RAM, algorithm: PageReplacementAlgorithm):
        self.ram       = ram
        self.algorithm = algorithm

    def run_process(self, process_id, reference_string, frames_allocated=None):
        page_table = PageTable(process_id)
        stats      = PageFaultStats(process_id)
        steps      = []

        for i, page in enumerate(reference_string):
            self.ram.tick_clock()

            frame = self.ram.find_frame_by_page(process_id, page)

            if frame is not None:
                was_fault    = False
                evicted_page = None
                evicted_pid  = None
                loaded_frame = frame.frame_id
            else:
                was_fault    = True
                empty_frames = self.ram.get_empty_frames()

                if frames_allocated is not None:
                    proc_frames = self.ram.get_frames_for_process(process_id)
                    if len(proc_frames) >= frames_allocated:
                        empty_frames = []

                if empty_frames:
                    target_frame = empty_frames[0]
                    evicted_page = None
                    evicted_pid  = None
                else:
                    future_refs = reference_string[i+1:]
                    vid = self.algorithm.select_victim(
                        process_id=process_id,
                        future_refs=future_refs
                    )
                    target_frame = self.ram.frames[vid]
                    evicted_tuple = target_frame.evict()
                    if evicted_tuple:
                        evicted_pid, evicted_page = evicted_tuple
                    else:
                        evicted_pid = evicted_page = None

                target_frame.load_legacy(page, process_id, self.ram.tick)
                page_table.map(page, target_frame.frame_id)
                loaded_frame = target_frame.frame_id

            stats.record_access(was_fault)

            step = {
                "tick"         : self.ram.tick,
                "process_id"   : process_id,
                "page"         : page,
                "fault"        : was_fault,
                "evicted_page" : evicted_page,
                "evicted_pid"  : evicted_pid,
                "loaded_frame" : loaded_frame,
                "fault_count"  : stats.page_faults,
                "fault_rate"   : stats.page_fault_rate(),
                "ram_snapshot" : self.ram.get_snapshot(),
                "algorithm"    : self.algorithm.name(),
            }
            steps.append(step)

        return steps, stats


def compare_algorithms(reference_string, num_frames, process_id=0):
    """
    Run the same reference string through FIFO, LRU, Optimal.
    Returns dict: {algo_name: (steps, stats)}
    """
    results = {}
    for AlgoClass in [FIFO, LRU, Optimal]:
        ram    = RAM(num_frames)
        algo   = AlgoClass(ram)
        engine = SimulationEngine(ram, algo)
        steps, stats = engine.run_process(process_id, reference_string)
        results[algo.name()] = (steps, stats)
    return results
