import os

def read_env(defaults: dict):
    out = {}
    for k,v in defaults.items():
        out[k] = type(v)(os.getenv(k, v))
    return out
