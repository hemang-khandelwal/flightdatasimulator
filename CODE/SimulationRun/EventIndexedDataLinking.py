from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from SimulationRun.SSVHashing import SSVHash


SSV_CSV_HEADER = ["Time", "u", "w", "q", "theta", "x", "z", "elevator", "thrust", "stall"]
INDEX_CSV_HEADER = [
    "segmentId",
    "startTime",
    "endTime",
    "rowStart",
    "rowEnd",
    "hash",
    "stallCount",
    "maxAirspeed",
]


def _format_row_for_hash(row: Dict[str, object]) -> str:
    time_s = float(row["Time"])
    state = np.array([row["u"], row["w"], row["q"], row["theta"], row["x"], row["z"]], dtype=float).flatten()
    elevator = float(row.get("elevator", 0.0))
    thrust = float(row.get("thrust", 0.0))
    stalled = bool(row.get("stall", False))
    # Keep a stable format so the same data produces the same hash.
    return f"{time_s:.6f}," + ",".join(f"{v:.6f}" for v in state) + f",{elevator:.6f},{thrust:.1f},{stalled}"


def _segment_hash(rows: Iterable[Dict[str, object]]) -> str:
    # Hash the concatenation of canonical per-row strings. This is not cryptographically secure,
    # but it is consistent and fast for integrity checking within this project.
    return SSVHash.hash_string("\n".join(_format_row_for_hash(r) for r in rows))


@dataclass(frozen=True)
class SegmentIndexEntry:
    segment_id: int
    start_time: float
    end_time: float
    row_start: int  # 1-based data row index (excluding header)
    row_end: int  # inclusive, 1-based data row index (excluding header)
    hash_hex: str
    stall_count: int
    max_airspeed: float


class SegmentIndexer:
    """
    Builds an event index over a CSV time history by splitting into fixed-duration segments.

    - Stores segment metadata: start/end time + row start/end (data-row indices).
    - Stores a per-segment hash for later integrity validation.
    """

    def __init__(self, segment_seconds: float) -> None:
        if segment_seconds <= 0:
            raise ValueError("segment_seconds must be > 0")
        self.segment_seconds = float(segment_seconds)

    def build_index(self, ssv_csv_path: Path, index_csv_path: Path) -> List[SegmentIndexEntry]:
        ssv_csv_path = Path(ssv_csv_path)
        index_csv_path = Path(index_csv_path)
        entries: List[SegmentIndexEntry] = []

        with ssv_csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError("SSV CSV has no header")

            data_row_idx = 0
            segment_id = 0
            current_rows: List[Dict[str, object]] = []
            segment_start_time: Optional[float] = None
            segment_row_start: Optional[int] = None

            stall_count = 0
            max_airspeed = 0.0

            def flush_segment(final_time: float, final_row_idx: int) -> None:
                nonlocal segment_id, current_rows, segment_start_time, segment_row_start, stall_count, max_airspeed
                if not current_rows or segment_start_time is None or segment_row_start is None:
                    return
                seg_hash = _segment_hash(current_rows)
                entries.append(
                    SegmentIndexEntry(
                        segment_id=segment_id,
                        start_time=float(segment_start_time),
                        end_time=float(final_time),
                        row_start=int(segment_row_start),
                        row_end=int(final_row_idx),
                        hash_hex=seg_hash,
                        stall_count=int(stall_count),
                        max_airspeed=float(max_airspeed),
                    )
                )
                segment_id += 1
                current_rows = []
                segment_start_time = None
                segment_row_start = None
                stall_count = 0
                max_airspeed = 0.0

            for row in reader:
                data_row_idx += 1
                time_s = float(row["Time"])
                parsed = {
                    "Time": time_s,
                    "u": float(row.get("u") or 0.0),
                    "w": float(row.get("w") or 0.0),
                    "q": float(row.get("q") or 0.0),
                    "theta": float(row.get("theta") or 0.0),
                    "x": float(row.get("x") or 0.0),
                    "z": float(row.get("z") or 0.0),
                    "elevator": float(row.get("elevator") or 0.0),
                    "thrust": float(row.get("thrust") or 0.0),
                    "stall": str(row.get("stall") or "").strip().lower() in ("1", "true", "yes", "y"),
                }

                if segment_start_time is None:
                    segment_start_time = time_s
                    segment_row_start = data_row_idx

                # Update segment stats
                if bool(parsed["stall"]):
                    stall_count += 1
                airspeed = math.sqrt(float(parsed["u"]) ** 2 + float(parsed["w"]) ** 2)
                max_airspeed = max(max_airspeed, airspeed)

                current_rows.append(parsed)

                # Close the segment on duration boundary
                if time_s - float(segment_start_time) >= self.segment_seconds:
                    flush_segment(final_time=time_s, final_row_idx=data_row_idx)

            # Flush last partial segment
            if current_rows and segment_start_time is not None and segment_row_start is not None:
                flush_segment(final_time=float(current_rows[-1]["Time"]), final_row_idx=data_row_idx)

        index_csv_path.parent.mkdir(parents=True, exist_ok=True)
        with index_csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(INDEX_CSV_HEADER)
            for e in entries:
                writer.writerow(
                    [
                        e.segment_id,
                        f"{e.start_time:.6f}",
                        f"{e.end_time:.6f}",
                        e.row_start,
                        e.row_end,
                        e.hash_hex,
                        e.stall_count,
                        f"{e.max_airspeed:.6f}",
                    ]
                )

        return entries

    @staticmethod
    def load_index(index_csv_path: Path) -> List[SegmentIndexEntry]:
        index_csv_path = Path(index_csv_path)
        entries: List[SegmentIndexEntry] = []
        with index_csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(
                    SegmentIndexEntry(
                        segment_id=int(row["segmentId"]),
                        start_time=float(row["startTime"]),
                        end_time=float(row["endTime"]),
                        row_start=int(row["rowStart"]),
                        row_end=int(row["rowEnd"]),
                        hash_hex=str(row["hash"]),
                        stall_count=int(float(row.get("stallCount") or 0)),
                        max_airspeed=float(row.get("maxAirspeed") or 0.0),
                    )
                )
        return entries


class EventLookup:
    """
    Lookup an SSV row by time using the segment index, then validate the segment hash.
    """

    @staticmethod
    def find_segment(entries: List[SegmentIndexEntry], t: float) -> Optional[SegmentIndexEntry]:
        if not entries:
            return None
        lo, hi = 0, len(entries) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            e = entries[mid]
            if t < e.start_time:
                hi = mid - 1
            elif t > e.end_time:
                lo = mid + 1
            else:
                return e
        # Not inside any segment; pick the nearest segment by time if slightly out of range.
        if lo <= 0:
            return entries[0]
        if lo >= len(entries):
            return entries[-1]
        before = entries[lo - 1]
        after = entries[lo]
        return before if abs(t - before.end_time) <= abs(after.start_time - t) else after

    @staticmethod
    def read_rows_by_range(ssv_csv_path: Path, row_start: int, row_end: int) -> List[Dict[str, object]]:
        if row_start < 1 or row_end < row_start:
            return []
        rows: List[Dict[str, object]] = []
        with Path(ssv_csv_path).open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            idx = 0
            for r in reader:
                idx += 1
                if idx < row_start:
                    continue
                if idx > row_end:
                    break
                rows.append(
                    {
                        "Time": float(r["Time"]),
                        "u": float(r.get("u") or 0.0),
                        "w": float(r.get("w") or 0.0),
                        "q": float(r.get("q") or 0.0),
                        "theta": float(r.get("theta") or 0.0),
                        "x": float(r.get("x") or 0.0),
                        "z": float(r.get("z") or 0.0),
                        "elevator": float(r.get("elevator") or 0.0),
                        "thrust": float(r.get("thrust") or 0.0),
                        "stall": str(r.get("stall") or "").strip().lower() in ("1", "true", "yes", "y"),
                    }
                )
        return rows

    @staticmethod
    def find_row_at_time(rows: List[Dict[str, object]], t: float) -> Optional[Dict[str, object]]:
        if not rows:
            return None
        # rows are time-ordered; choose nearest.
        best = rows[0]
        best_err = abs(float(best["Time"]) - t)
        for r in rows[1:]:
            err = abs(float(r["Time"]) - t)
            if err < best_err:
                best, best_err = r, err
        return best

    @staticmethod
    def lookup_and_validate(
        ssv_csv_path: Path, index_csv_path: Path, t: float
    ) -> Tuple[Optional[Dict[str, object]], bool, Optional[SegmentIndexEntry]]:
        entries = SegmentIndexer.load_index(index_csv_path)
        seg = EventLookup.find_segment(entries, float(t))
        if seg is None:
            return (None, False, None)
        rows = EventLookup.read_rows_by_range(ssv_csv_path, seg.row_start, seg.row_end)
        if not rows:
            return (None, False, seg)
        computed_hash = _segment_hash(rows)
        valid = computed_hash == seg.hash_hex
        return (EventLookup.find_row_at_time(rows, float(t)), valid, seg)

