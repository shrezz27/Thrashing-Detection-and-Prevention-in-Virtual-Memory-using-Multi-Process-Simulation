"""
=============================================================
  MODULE: memory_core.py  (v2 — Tuple-Based Page Identity)
=============================================================

WHAT CHANGED FROM v1:
  ─────────────────────────────────────────────────────────
  PROBLEM IN v1:
    Pages were stored as bare integers (e.g., page=5).
    The process_id was stored separately in frame.process_id.
    `find_frame_by_page` checked both fields manually — fragile.
    Algorithms saw only page numbers, risking cross-process confusion.

  FIX IN v2:
    Each page is now stored as a TUPLE: (process_id, page_number)
    Example: ("P0", 5) means page 5 belonging to process P0.

    Benefits:
      1. A page is UNIQUELY identified by its tuple.
         (P0, 5) ≠ (P1, 5) — no cross-process hits ever possible.
      2. Algorithms compare FULL TUPLES — one field, one check.
      3. RAM snapshots show ("P0", 5) directly — cleaner display.
      4. Eviction is simpler: store/compare one field.

  BACKWARD COMPATIBILITY:
    frame.page and frame.process_id properties still work.
    Single-process SimulationEngine uses load_legacy() wrapper.
─────────────────────────────────────────────────────────────
"""


class Frame:
    """
    Represents one physical RAM frame slot.

    v2: `page_tuple` = (process_id, page_number) or None if empty.
    Example: frame.page_tuple = ("P0", 3)

    Backward-compat properties `frame.page` and `frame.process_id`
    are kept so the single-process engine still works unchanged.
    """

    def __init__(self, frame_id):
        self.frame_id   = frame_id
        self.page_tuple = None    # (process_id, page_number) or None
        self.loaded_at  = 0      # Tick when page was loaded  → FIFO key
        self.last_used  = 0      # Tick of most recent access → LRU key

    # ── backward-compat properties ──────────────────────────────
    @property
    def page(self):
        return self.page_tuple[1] if self.page_tuple else None

    @property
    def process_id(self):
        return self.page_tuple[0] if self.page_tuple else None

    def is_empty(self):
        return self.page_tuple is None

    def load(self, page_tuple, tick):
        """
        Load a (process_id, page_number) tuple into this frame.
        This is the primary v2 load method used by multi-process scheduler.
        """
        self.page_tuple = page_tuple
        self.loaded_at  = tick
        self.last_used  = tick

    def load_legacy(self, page, process_id, tick):
        """
        Backward-compat: converts (process_id, page) args to tuple.
        Used by single-process SimulationEngine in algorithms.py.
        """
        self.load((process_id, page), tick)

    def touch(self, tick):
        """Update LRU timestamp on a page hit without reloading the frame."""
        self.last_used = tick

    def evict(self):
        """
        Remove current page from frame. Returns the evicted tuple.
        Caller unpacks: evicted_tuple = frame.evict()
        Then: pid, pg = evicted_tuple
        """
        evicted         = self.page_tuple
        self.page_tuple = None
        return evicted

    def __repr__(self):
        if self.is_empty():
            return f"Frame({self.frame_id}: EMPTY)"
        pid, pg = self.page_tuple
        return f"Frame({self.frame_id}: ({pid}, pg{pg}))"


class RAM:
    """
    Physical RAM: a fixed pool of Frame objects.

    v2 key changes:
      - find_frame_by_page() matches on the FULL TUPLE (pid, page)
      - get_snapshot_inline() returns compact one-liner for step logs
      - load_page_tuple() is the primary load method for multi-process
    """

    def __init__(self, total_frames):
        if total_frames < 1:
            raise ValueError("RAM must have at least 1 frame")
        self.total_frames = total_frames
        self.frames       = [Frame(i) for i in range(total_frames)]
        self.tick         = 0

    # ── Frame queries ───────────────────────────────────────────

    def get_occupied_frames(self):
        return [f for f in self.frames if not f.is_empty()]

    def get_empty_frames(self):
        return [f for f in self.frames if f.is_empty()]

    def is_full(self):
        return len(self.get_empty_frames()) == 0

    def get_frames_for_process(self, process_id):
        """All frames whose page_tuple[0] == process_id."""
        return [f for f in self.frames
                if f.page_tuple and f.page_tuple[0] == process_id]

    # ── Page lookup ─────────────────────────────────────────────

    def find_frame_by_page(self, process_id, page):
        """
        PAGE HIT CHECK — v2.

        Searches for frame whose page_tuple == (process_id, page).
        BOTH fields must match exactly. A page from P1 will NEVER
        count as a hit for P0, even if page numbers are identical.

        On a hit, updates last_used for LRU correctness.
        Returns Frame on hit, None on fault.
        """
        target = (process_id, page)
        for f in self.frames:
            if f.page_tuple == target:
                f.touch(self.tick)
                return f
        return None

    # ── Page load ───────────────────────────────────────────────

    def load_page_tuple(self, page_tuple, frame_id):
        """Load a (pid, page) tuple into a specific frame. Primary v2 method."""
        self.frames[frame_id].load(page_tuple, self.tick)

    # Backward compat for single-process SimulationEngine
    def load_page(self, process_id, page, frame_id):
        self.frames[frame_id].load_legacy(page, process_id, self.tick)

    # ── Snapshots ───────────────────────────────────────────────

    def get_snapshot(self):
        """
        Multi-line detailed snapshot (single-process step mode).
        Frame  0: [(P0, pg  3)]  loaded@4  lastUsed@7
        """
        lines = []
        for f in self.frames:
            if f.is_empty():
                lines.append(f"Frame {f.frame_id:2d}: [   EMPTY   ]")
            else:
                pid, pg = f.page_tuple
                lines.append(
                    f"Frame {f.frame_id:2d}: [({pid}, pg{pg:3d})]"
                    f"  loaded@{f.loaded_at}  lastUsed@{f.last_used}"
                )
        return "\n".join(lines)

    def get_snapshot_inline(self):
        """
        Compact one-line frame state for multi-process step logs.
        Example:  [(P0,2), (P1,3), _, _, _, _]
        """
        parts = []
        for f in self.frames:
            if f.is_empty():
                parts.append("_")
            else:
                pid, pg = f.page_tuple
                parts.append(f"({pid},{pg})")
        return "[" + ", ".join(parts) + "]"

    # ── Clock ───────────────────────────────────────────────────

    def tick_clock(self):
        self.tick += 1


# ─────────────────────────────────────────────────────────────
#  PageTable — unchanged from v1
# ─────────────────────────────────────────────────────────────

class PageTable:
    """
    Virtual page → physical frame mapping for one process.
    Key is bare page number (int); process identity is in the RAM frame.
    """
    def __init__(self, process_id):
        self.process_id = process_id
        self.table      = {}

    def map(self, page, frame_id):
        self.table[page] = frame_id

    def unmap(self, page):
        self.table.pop(page, None)

    def lookup(self, page):
        return self.table.get(page, None)

    def get_resident_pages(self):
        return list(self.table.keys())


# ─────────────────────────────────────────────────────────────
#  PageFaultStats — unchanged from v1
# ─────────────────────────────────────────────────────────────

class PageFaultStats:
    """
    Per-process fault statistics.
    Fault Rate = page_faults / total_accesses
    """
    def __init__(self, process_id):
        self.process_id     = process_id
        self.total_accesses = 0
        self.page_faults    = 0
        self.fault_history  = []

    def record_access(self, was_fault):
        self.total_accesses += 1
        if was_fault:
            self.page_faults += 1
        self.fault_history.append(self.page_fault_rate())

    def page_fault_rate(self):
        if self.total_accesses == 0:
            return 0.0
        return self.page_faults / self.total_accesses

    def __repr__(self):
        return (f"Process {self.process_id}: "
                f"{self.page_faults}/{self.total_accesses} faults "
                f"({self.page_fault_rate()*100:.1f}%)")
