"""
年级预设配置：科目、满分、及格线、优秀线。
支持内置年级 + 用户自定义年级。
"""

import json
import os

_APP_DIR = os.environ.get("CHENGJI_APP_DIR", os.path.dirname(os.path.abspath(__file__)))
_CUSTOM_GRADES_FILE = os.path.join(_APP_DIR, "config", "grades.json")


def _load_custom_grades():
    """加载用户自定义年级配置。"""
    if not os.path.exists(_CUSTOM_GRADES_FILE):
        return {}
    try:
        with open(_CUSTOM_GRADES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_custom_grades(grades):
    """保存用户自定义年级配置。"""
    os.makedirs(os.path.dirname(_CUSTOM_GRADES_FILE), exist_ok=True)
    with open(_CUSTOM_GRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(grades, f, ensure_ascii=False, indent=2)


def get_all_grades():
    """获取所有年级名称列表（内置 + 自定义）。"""
    custom = _load_custom_grades()
    all_grades = list(GRADE_PRESETS.keys())
    for g in custom:
        if g not in all_grades:
            all_grades.append(g)
    return all_grades


def add_custom_grade(name, subjects, n_active_subjects, class_pattern):
    """添加自定义年级。"""
    custom = _load_custom_grades()
    custom[name] = {
        "subjects": subjects,
        "n_active_subjects": n_active_subjects,
        "class_pattern": class_pattern,
    }
    _save_custom_grades(custom)


def delete_custom_grade(name):
    """删除自定义年级（内置年级不可删除）。"""
    if name in GRADE_PRESETS:
        return False, "内置年级不能删除"
    custom = _load_custom_grades()
    if name not in custom:
        return False, "该年级不存在"
    del custom[name]
    _save_custom_grades(custom)
    return True, "已删除"


def is_builtin_grade(name):
    """是否为内置年级。"""
    return name in GRADE_PRESETS


GRADE_PRESETS = {
    "七年级": {
        "subjects": [
            {"name": "语文", "full_score": 120, "pass_score": 72, "exc_score": 96, "qualify": True},
            {"name": "数学", "full_score": 120, "pass_score": 72, "exc_score": 96, "qualify": True},
            {"name": "英语", "full_score": 140, "pass_score": 84, "exc_score": 112, "qualify": True},
            {"name": "道法", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": True},
            {"name": "历史", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": True},
            {"name": "地理", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": False},
            {"name": "生物", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": True},
        ],
        "n_active_subjects": 8,
        "class_pattern": "七（{n}）",
    },
    "八年级": {
        "subjects": [
            {"name": "语文", "full_score": 120, "pass_score": 72, "exc_score": 96, "qualify": True},
            {"name": "数学", "full_score": 120, "pass_score": 72, "exc_score": 96, "qualify": True},
            {"name": "英语", "full_score": 140, "pass_score": 84, "exc_score": 112, "qualify": True},
            {"name": "物理", "full_score": 70, "pass_score": 42, "exc_score": 56, "qualify": True},
            {"name": "道法", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": True},
            {"name": "历史", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": True},
            {"name": "地理", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": False},
            {"name": "生物", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": False},
        ],
        "n_active_subjects": 8,
        "class_pattern": "八（{n}）",
    },
    "九年级": {
        "subjects": [
            {"name": "语文", "full_score": 120, "pass_score": 72, "exc_score": 96, "qualify": True},
            {"name": "数学", "full_score": 120, "pass_score": 72, "exc_score": 96, "qualify": True},
            {"name": "英语", "full_score": 140, "pass_score": 84, "exc_score": 112, "qualify": True},
            {"name": "道法", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": True},
            {"name": "历史", "full_score": 50, "pass_score": 30, "exc_score": 40, "qualify": True},
            {"name": "物理", "full_score": 70, "pass_score": 42, "exc_score": 56, "qualify": True},
            {"name": "化学", "full_score": 60, "pass_score": 36, "exc_score": 48, "qualify": True},
        ],
        "n_active_subjects": 8,
        "class_pattern": "九（{n}）",
    },
}

KNOWN_SUBJECTS = {"语文", "数学", "英语", "物理", "化学", "道法", "历史", "地理", "生物", "体育", "音乐", "美术", "信息"}

SUBJECT_DEFAULTS = {
    "语文": {"full_score": 120, "pass_score": 72, "exc_score": 96},
    "数学": {"full_score": 120, "pass_score": 72, "exc_score": 96},
    "英语": {"full_score": 140, "pass_score": 84, "exc_score": 112},
    "物理": {"full_score": 70, "pass_score": 42, "exc_score": 56},
    "化学": {"full_score": 60, "pass_score": 36, "exc_score": 48},
    "道法": {"full_score": 50, "pass_score": 30, "exc_score": 40},
    "历史": {"full_score": 50, "pass_score": 30, "exc_score": 40},
    "地理": {"full_score": 50, "pass_score": 30, "exc_score": 40},
    "生物": {"full_score": 50, "pass_score": 30, "exc_score": 40},
    "体育": {"full_score": 60, "pass_score": 36, "exc_score": 48},
    "音乐": {"full_score": 100, "pass_score": 60, "exc_score": 80},
    "美术": {"full_score": 100, "pass_score": 60, "exc_score": 80},
    "信息": {"full_score": 100, "pass_score": 60, "exc_score": 80},
}


def get_subject_defaults(subject_name):
    """获取科目的默认满分/及格线/优秀线。
    已知科目使用预设值，未知科目按算法参数中的及格/优秀比例计算。
    """
    if subject_name in SUBJECT_DEFAULTS:
        return SUBJECT_DEFAULTS[subject_name].copy()
    from algo_config import load_algo_params
    params = load_algo_params()
    lines = params.get("score_lines", {})
    pass_ratio = lines.get("pass_ratio", 0.6)
    exc_ratio = lines.get("excellent_ratio", 0.8)
    full = 100
    return {
        "full_score": full,
        "pass_score": round(full * pass_ratio),
        "exc_score": round(full * exc_ratio),
    }


def get_preset(grade_name):
    """获取年级预设（先查内置，再查自定义）。"""
    if grade_name in GRADE_PRESETS:
        return GRADE_PRESETS[grade_name]
    custom = _load_custom_grades()
    return custom.get(grade_name)


def detect_grade_from_class_name(class_name):
    """从班级名推断年级。支持内置和自定义年级。"""
    # 先查内置年级
    if class_name.startswith("七"):
        return "七年级"
    if class_name.startswith("八"):
        return "八年级"
    if class_name.startswith("九"):
        return "九年级"
    # 再查自定义年级（通过 class_pattern 匹配）
    custom = _load_custom_grades()
    for grade_name, preset in custom.items():
        pattern = preset.get("class_pattern", "")
        # 检查班级名是否匹配自定义年级的模式
        if pattern and class_name.startswith(pattern.split("{")[0]):
            return grade_name
    return None
