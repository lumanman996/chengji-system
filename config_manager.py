"""
配置持久化：教师任课、应考人数、上次排名的 JSON 读写。
"""

import json
import os

# 打包后 config 放在 exe 同级目录（可写），开发时放在源码目录
_APP_DIR = os.environ.get("CHENGJI_APP_DIR", os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(_APP_DIR, "config")
os.makedirs(CONFIG_DIR, exist_ok=True)

TEACHERS_FILE = os.path.join(CONFIG_DIR, "teachers.json")
CLASS_COUNTS_FILE = os.path.join(CONFIG_DIR, "class_counts.json")
PREV_RANKINGS_FILE = os.path.join(CONFIG_DIR, "prev_rankings.json")


def _load_json(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def _save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 教师任课 ─────────────────────────────────────────────────────────────────

def load_teachers(grade):
    data = _load_json(TEACHERS_FILE)
    return data.get(grade, [])


def save_teachers(grade, assignments):
    data = _load_json(TEACHERS_FILE)
    data[grade] = assignments
    _save_json(TEACHERS_FILE, data)


# ─── 应考人数 ─────────────────────────────────────────────────────────────────

def load_class_counts(grade):
    data = _load_json(CLASS_COUNTS_FILE)
    return data.get(grade, {})


def save_class_counts(grade, counts):
    data = _load_json(CLASS_COUNTS_FILE)
    data[grade] = counts
    _save_json(CLASS_COUNTS_FILE, data)


# ─── 上次排名 ─────────────────────────────────────────────────────────────────

def load_prev_rankings(grade):
    data = _load_json(PREV_RANKINGS_FILE)
    return data.get(grade, {})


def save_prev_rankings(grade, rankings):
    data = _load_json(PREV_RANKINGS_FILE)
    data[grade] = rankings
    _save_json(PREV_RANKINGS_FILE, data)


# ─── 辅助 ─────────────────────────────────────────────────────────────────────

def has_config(grade):
    teachers = load_teachers(grade)
    return len(teachers) > 0
