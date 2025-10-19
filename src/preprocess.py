from typing import Tuple
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

def clean_and_smooth(df: pd.DataFrame, window: int=9, poly: int=2) -> pd.DataFrame:
    d = df.copy()
    d = d.dropna(subset=['timestamp','fuel_level_liters']).reset_index(drop=True)
    d['ts'] = pd.to_datetime(d['timestamp'], utc=True)
    d = d.sort_values('ts')
    # Remove impossible values
    d = d[(d['fuel_level_liters'] >= 0) & (d['fuel_level_liters'].notna())]
    # Smooth
    y = d['fuel_level_liters'].to_numpy()
    if len(y) >= window and window % 2 == 1:
        y_s = savgol_filter(y, window_length=window, polyorder=poly, mode="interp")
    else:
        y_s = y.copy()
    d['fuel_smooth'] = y_s
    # time delta minutes
    d['dt_min'] = d['ts'].diff().dt.total_seconds().div(60.0).fillna(0)
    d.loc[d['dt_min'] <= 0, 'dt_min'] = np.nan
    # rate L/min
    d['dfuel'] = d['fuel_smooth'].diff()
    d['rate_lpm'] = d['dfuel'] / d['dt_min']
    # median filter (rolling)
    d['rate_med'] = d['rate_lpm'].rolling(5, center=True, min_periods=1).median()
    return d
