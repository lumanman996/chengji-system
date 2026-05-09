"""
Excel 自动检测：从上传的登分表推断年级、科目、班级等信息。
"""

import re
import pandas as pd
from presets import GRADE_PRESETS, detect_grade_from_class_name


def detect_grade_info(filepath):
    """
    读取 Excel 文件，自动推断年级和配置信息。
    优先读取名为"登分表"的 sheet，否则读取第一个 sheet。
    返回 dict:
        grade: str — 检测到的年级名
        detected_subjects: list — 科目列名列表
        class_names: list — 班级名称列表（排序后）
        n_students_per_class: dict — {班级: 学生人数}
        exam_title_hint: str — 从标题行提取的考试名称
        exam_date_hint: str — 从标题行提取的日期
        header_row: int — 表头所在行号
        sheet_name: str — 使用的 sheet 名
    """
    sheet_name = _find_score_sheet(filepath)

    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None, dtype=str, nrows=5)

    exam_title_hint = ""
    exam_date_hint = ""
    if len(df_raw) > 0:
        row0 = " ".join(str(v) for v in df_raw.iloc[0].dropna().values)
        exam_title_hint = row0.strip()
    if len(df_raw) > 1:
        row1 = " ".join(str(v) for v in df_raw.iloc[1].dropna().values)
        date_match = re.search(r"(\d{4}[.\-/年]\d{1,2}[.\-/月]\d{1,2})", row1)
        if date_match:
            exam_date_hint = date_match.group(1)
        elif re.search(r"\d{4}", row1):
            exam_date_hint = row1.strip()

    header_row = _find_header_row(filepath, sheet_name)
    if header_row is None:
        return {"error": "未找到含「姓名」的表头行，请确认上传的是登分表。"}

    df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    detected_subjects = _extract_subjects(df.columns.tolist())

    class_col = None
    for col in df.columns:
        if "班级" in col or col == "班级":
            class_col = col
            break

    class_names = []
    n_students_per_class = {}
    grade = None

    if class_col:
        df[class_col] = df[class_col].astype(str).str.strip()
        valid = df[df[class_col].notna() & (df[class_col] != "") & (df[class_col] != "nan")]
        class_names = sorted(valid[class_col].unique().tolist())
        n_students_per_class = valid[class_col].value_counts().to_dict()

        for cn in class_names:
            g = detect_grade_from_class_name(cn)
            if g:
                grade = g
                break

    if not grade:
        grade = _infer_grade_from_subjects(detected_subjects)

    if not grade:
        grade = _infer_grade_from_title(exam_title_hint)

    return {
        "grade": grade,
        "detected_subjects": detected_subjects,
        "class_names": class_names,
        "n_students_per_class": n_students_per_class,
        "exam_title_hint": exam_title_hint,
        "exam_date_hint": exam_date_hint,
        "header_row": header_row,
        "sheet_name": sheet_name,
    }


def _find_score_sheet(filepath):
    """找到登分表 sheet，优先匹配含'登分'的名称，否则用第一个 sheet。"""
    xl = pd.ExcelFile(filepath)
    for name in xl.sheet_names:
        if "登分" in name:
            return name
    return xl.sheet_names[0]


def _find_header_row(filepath, sheet_name, max_rows=10):
    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None, dtype=str, nrows=max_rows)
    for i, row in df_raw.iterrows():
        vals = [str(v).strip() for v in row.values if str(v).strip() not in ("nan", "")]
        if "姓名" in vals:
            return i
    return None


def _extract_subjects(columns):
    """
    提取科目列：位于"班级"/"考号"/"学籍号"之后、"总分"/"班次"/"级次"之前的所有有效列名。
    不再限制为已知科目，任何非系统列都视为科目。
    """
    skip_cols = {"序号", "姓名", "班级", "考号", "学籍号", "总分", "班次", "级次", "名次"}

    start_idx = 0
    end_idx = len(columns)

    for i, col in enumerate(columns):
        if col in ("考号", "学籍号", "班级"):
            start_idx = max(start_idx, i + 1)
        if col in ("总分", "班次", "级次") and i > start_idx:
            end_idx = i
            break

    candidates = columns[start_idx:end_idx]
    subjects = [c for c in candidates
                if c not in skip_cols
                and str(c).strip() not in ("nan", "", "None")
                and not str(c).startswith("Unnamed")
                and not re.match(r".+\.\d+$", str(c))]

    return subjects


def _infer_grade_from_subjects(subjects):
    """通过科目组合推断年级。"""
    subj_set = set(subjects)
    if "化学" in subj_set:
        return "九年级"
    if "物理" in subj_set and "化学" not in subj_set:
        if "地理" in subj_set and "生物" in subj_set:
            return "八年级"
        return "八年级"
    if "地理" in subj_set and "生物" in subj_set and "物理" not in subj_set:
        return "七年级"
    return None


def _infer_grade_from_title(title):
    """从标题文字推断年级。"""
    if "七年级" in title or "七年" in title:
        return "七年级"
    if "八年级" in title or "八年" in title:
        return "八年级"
    if "九年级" in title or "九年" in title:
        return "九年级"
    return None
