from typing import List, Dict
import pandas as pd

def detect_events(
    d: pd.DataFrame,
    refuel_min: float = 2.5,
    drain_min: float = 2.0,
    min_event_min: float = 3.0,
    max_rate_plausible: float = 12.0,
    tank_capacity_l: float = 300.0,
) -> List[Dict]:
    events: List[Dict] = []
    # Clamp impossible rates
    dr = d.copy()
    dr = dr[(dr['rate_med'].abs() <= max_rate_plausible) | (dr['rate_med'].isna())]

    def segment(mask, label):
        in_seg = False; start_idx = None
        for i, ok in enumerate(mask):
            if ok and not in_seg:
                in_seg = True; start_idx = i
            if (not ok or i == len(mask)-1) and in_seg:
                end_idx = i if not ok else i
                seg = dr.iloc[start_idx:end_idx+1]
                dur = seg['dt_min'].sum()
                delta = (seg['fuel_smooth'].iloc[-1] - seg['fuel_smooth'].iloc[0])
                if dur >= min_event_min and delta != 0:
                    # sanity: tank bounds
                    if 0 <= seg['fuel_smooth'].max() <= tank_capacity_l:
                        conf = score_confidence(label, dur, delta, max_rate_plausible)
                        events.append({
                            "type": label,
                            "start_ts": seg['ts'].iloc[0].isoformat(),
                            "end_ts": seg['ts'].iloc[-1].isoformat(),
                            "duration_min": float(dur),
                            "delta_liters": float(delta),
                            "confidence": conf
                        })
                in_seg = False

    # Sustained positive & negative
    mask_refuel = dr['rate_med'].fillna(0) > refuel_min
    mask_drain  = dr['rate_med'].fillna(0) < -drain_min

    segment(mask_refuel.tolist(), "refuel")
    segment(mask_drain.tolist(),  "drain")

    # Merge nearby events of same type (simple pass)
    events = merge_adjacent(events, gap_min=3)
    return events

def score_confidence(label: str, dur: float, delta: float, max_rate_plausible: float) -> float:
    score = 0.0
    if dur >= 3: score += 0.25
    if abs(delta)/max(dur,1) <= max_rate_plausible: score += 0.25
    if (label == "refuel" and delta > 0) or (label == "drain" and delta < 0): score += 0.25
    if abs(delta) >= 5: score += 0.25  # magnitude
    return min(1.0, score)

def merge_adjacent(events, gap_min=3):
    if not events: return events
    events = sorted(events, key=lambda e: e['start_ts'])
    out = [events[0]]
    from datetime import datetime
    import pandas as pd
    for e in events[1:]:
        prev = out[-1]
        if e['type']==prev['type']:
            tprev = pd.to_datetime(prev['end_ts'])
            tcurS = pd.to_datetime(e['start_ts'])
            gap = (tcurS - tprev).total_seconds()/60.0
            if gap <= gap_min:
                # merge
                prev['end_ts'] = e['end_ts']
                prev['duration_min'] += e['duration_min']
                prev['delta_liters'] += e['delta_liters']
                prev['confidence'] = max(prev['confidence'], e['confidence'])
                continue
        out.append(e)
    return out
