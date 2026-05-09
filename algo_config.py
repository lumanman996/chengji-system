"""
算法参数配置：结构分权重、进线比例、增值系数等。
提供默认值，支持用户自定义覆盖。
"""

import copy
import json
import os

_APP_DIR = os.environ.get("CHENGJI_APP_DIR", os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(_APP_DIR, "config")
ALGO_FILE = os.path.join(CONFIG_DIR, "algorithm.json")

DEFAULT_PARAMS = {
    "weights": {
        "avg_score": 0.5,
        "pass_rate": 0.2,
        "excellent_rate": 0.2,
        "advance_rate": 0.15,
        "attend_rate": 0.05,
        "top_n_each": 0.2,
    },
    "advance_ratio": 0.75,
    "top_n": 10,
    "value_added": {
        "base_start": 5.1,
        "base_step": 0.1,
        "progress_step": 0.05,
    },
    "teacher_weights": {
        "avg_score": 0.5,
        "pass_rate": 0.25,
        "excellent_rate": 0.25,
    },
    "score_lines": {
        "pass_ratio": 0.6,
        "excellent_ratio": 0.8,
    },
}


def load_algo_params():
    if not os.path.exists(ALGO_FILE):
        return copy.deepcopy(DEFAULT_PARAMS)
    with open(ALGO_FILE, encoding="utf-8") as f:
        saved = json.load(f)
    merged = _deep_merge(copy.deepcopy(DEFAULT_PARAMS), saved)
    return merged


def save_algo_params(params):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(ALGO_FILE, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)


def reset_algo_params():
    if os.path.exists(ALGO_FILE):
        os.remove(ALGO_FILE)


def _deep_merge(base, override):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            base[k] = _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
