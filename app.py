import os
import pandas as pd
from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError
from typing import List, Optional
from src.preprocess import clean_and_smooth
from src.detect import detect_events
from src.utils import read_env

app = Flask(__name__)

DEFAULTS = dict(
    REFUEL_RATE_MIN=2.5,
    DRAIN_RATE_MIN=2.0,
    MAX_RATE_PLAUSIBLE=12.0,
    MIN_EVENT_MIN=3.0,
    TANK_CAPACITY_L=300.0,
    SAVGOL_WINDOW=9,
    SAVGOL_POLYORDER=2,
    PORT=8000
)

class Point(BaseModel):
    ts: Optional[str] = None
    timestamp: Optional[str] = None
    fuel: float
    fuel_level_liters: Optional[float] = None
    speed: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

class DetectBody(BaseModel):
    device_id: str
    tank_capacity_l: Optional[float] = None
    points: List[Point]

@app.get("/health")
def health():
    return jsonify({"status":"ok","version":"1.0.0"})

@app.post("/detect")
def detect():
    try:
        payload = DetectBody(**request.json)
    except ValidationError as e:
        return jsonify({"error":"invalid payload","details":e.errors()}), 400

    cfg = read_env(DEFAULTS)
    cap = float(payload.tank_capacity_l or cfg["TANK_CAPACITY_L"])

    # Build DataFrame
    rows = []
    for p in payload.points:
        ts = p.ts or p.timestamp
        fuel = p.fuel_level_liters if p.fuel_level_liters is not None else p.fuel
        rows.append(dict(timestamp=ts, fuel_level_liters=fuel, speed_kph=p.speed, lat=p.lat, lon=p.lon))
    df = pd.DataFrame(rows)

    d = clean_and_smooth(df, window=int(cfg["SAVGOL_WINDOW"]), poly=int(cfg["SAVGOL_POLYORDER"]))
    events = detect_events(
        d,
        refuel_min=float(cfg["REFUEL_RATE_MIN"]),
        drain_min=float(cfg["DRAIN_RATE_MIN"]),
        min_event_min=float(cfg["MIN_EVENT_MIN"]),
        max_rate_plausible=float(cfg["MAX_RATE_PLAUSIBLE"]),
        tank_capacity_l=cap,
    )
    summary = dict(
        refuels=sum(1 for e in events if e["type"]=="refuel"),
        drains=sum(1 for e in events if e["type"]=="drain"),
        net_change_l=sum(e["delta_liters"] for e in events),
    )
    return jsonify({"events":events,"summary":summary})

if __name__ == "__main__":
    cfg = read_env(DEFAULTS)
    app.run(host="0.0.0.0", port=int(cfg["PORT"]), debug=False)
