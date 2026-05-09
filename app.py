"""
Flask 主应用 v2：精简 3 步流程 + 一键模式 + 配置管理。
"""

import json
import os
import sys
import uuid
from io import BytesIO

import pandas as pd
from flask import (Flask, redirect, render_template, render_template_string,
                   request, send_file, session, url_for, flash)

# PyInstaller 打包后资源路径处理
if getattr(sys, 'frozen', False):
    # 打包后：资源在临时解压目录
    _BUNDLE_DIR = sys._MEIPASS
    # 可写数据（config/uploads）放在 exe 同级目录
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    _APP_DIR = _BUNDLE_DIR

# 设置环境变量供其他模块使用
os.environ["CHENGJI_APP_DIR"] = _APP_DIR
os.environ["CHENGJI_BUNDLE_DIR"] = _BUNDLE_DIR

from calculator import run_all
from exporter import export_excel, filter_data_for_class
from detector import detect_grade_info
from presets import (GRADE_PRESETS, get_preset, get_subject_defaults,
                     get_all_grades, add_custom_grade, delete_custom_grade, is_builtin_grade)
from config_manager import (
    load_teachers, save_teachers,
    load_class_counts, save_class_counts,
    load_prev_rankings, save_prev_rankings,
    has_config,
)
from algo_config import load_algo_params, save_algo_params, reset_algo_params, DEFAULT_PARAMS

app = Flask(__name__,
            template_folder=os.path.join(_BUNDLE_DIR, "templates"),
            static_folder=os.path.join(_BUNDLE_DIR, "static"))
app.secret_key = os.environ.get("SECRET_KEY", "chengji-dev-key-2026")
app.config["UPLOAD_FOLDER"] = os.path.join(_APP_DIR, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# ─── 工具函数 ──────────────────────────────────────────────────────────────────

def parse_excel(filepath, subject_names):
    from detector import _find_score_sheet
    sheet_name = _find_score_sheet(filepath)

    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None, dtype=str)

    header_row = None
    for i, row in df_raw.iterrows():
        if "姓名" in row.values:
            header_row = i
            break
    if header_row is None:
        raise ValueError("未找到含「姓名」的表头行，请确认 Excel 格式。")

    df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    required = ["姓名", "班级"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Excel 缺少必要列：{col}")

    missing = [sn for sn in subject_names if sn not in df.columns]
    if missing:
        raise ValueError(f"Excel 中找不到以下科目列：{missing}")

    students = []
    for _, row in df.iterrows():
        name = str(row.get("姓名", "")).strip()
        if not name or name in ("nan", "None", ""):
            continue
        exam_no = str(row.get("考号", row.get("学籍号", ""))).strip()
        class_name = str(row.get("班级", "")).strip()
        scores = {}
        for sn in subject_names:
            val = row.get(sn, "0")
            try:
                scores[sn] = float(val) if str(val) not in ("nan", "None", "") else 0.0
            except ValueError:
                scores[sn] = 0.0
        students.append({
            "name": name,
            "class_name": class_name,
            "exam_no": exam_no,
            "scores": scores,
        })

    return students


def save_result(results, exam_info):
    sid = str(uuid.uuid4())
    path = os.path.join(app.config["UPLOAD_FOLDER"], f"result_{sid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "exam_info": exam_info}, f, ensure_ascii=False, default=str)
    session["result_id"] = sid
    return sid


def load_result():
    sid = session.get("result_id")
    if not sid:
        return None, None
    path = os.path.join(app.config["UPLOAD_FOLDER"], f"result_{sid}.json")
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["results"], data["exam_info"]


def save_uploaded_file(file):
    fname = f"{uuid.uuid4()}_{file.filename}"
    fpath = os.path.join(app.config["UPLOAD_FOLDER"], fname)
    file.save(fpath)
    return fpath


# ─── Step 1: 上传页 ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    config_status = {
        grade: has_config(grade) for grade in get_all_grades()
    }
    has_result = session.get("result_id") is not None
    return render_template("upload.html", config_status=config_status, has_result=has_result)


# ─── 清零恢复 ────────────────────────────────────────────────────────────────

@app.route("/reset", methods=["POST"])
def reset():
    sid = session.get("result_id")
    if sid:
        path = os.path.join(app.config["UPLOAD_FOLDER"], f"result_{sid}.json")
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    session.pop("result_id", None)
    session.pop("uploaded_file", None)
    session.pop("detection", None)
    session.pop("selected_grade", None)
    flash("已清零，可以重新开始。")
    return redirect(url_for("index"))


# ─── Step 1→2: 上传处理（统一流程：所有年级都进入确认页） ────────────────────

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("score_file")
    if not file or not file.filename:
        flash("请上传成绩 Excel 文件。")
        return redirect(url_for("index"))

    selected_grade = request.form.get("selected_grade", "").strip()

    fpath = save_uploaded_file(file)

    try:
        detection = detect_grade_info(fpath)
    except Exception as e:
        flash(f"文件解析失败：{e}")
        if os.path.exists(fpath):
            os.remove(fpath)
        return redirect(url_for("index"))

    if "error" in detection:
        flash(detection["error"])
        if os.path.exists(fpath):
            os.remove(fpath)
        return redirect(url_for("index"))

    # 统一流程：所有年级都进入确认页
    session["uploaded_file"] = fpath
    session["detection"] = detection
    if selected_grade:
        session["selected_grade"] = selected_grade
    return redirect(url_for("confirm"))


# ─── Step 2: 确认页 ──────────────────────────────────────────────────────────

@app.route("/confirm")
def confirm():
    detection = session.get("detection")
    if not detection:
        flash("请先上传文件。")
        return redirect(url_for("index"))

    # 优先使用用户选择的年级，其次使用自动检测的年级
    grade = session.get("selected_grade") or detection.get("grade", "")
    preset = get_preset(grade) if grade else None

    detected_subjects = detection.get("detected_subjects", [])
    if detected_subjects:
        subjects = []
        preset_map = {}
        if preset:
            preset_map = {s["name"]: s for s in preset["subjects"]}
        for sn in detected_subjects:
            if sn in preset_map:
                subjects.append(preset_map[sn])
            else:
                defaults = get_subject_defaults(sn)
                subjects.append({"name": sn, **defaults, "qualify": True})
    elif preset:
        subjects = preset["subjects"]
    else:
        subjects = []

    saved_teachers = load_teachers(grade) if grade else []
    saved_counts = load_class_counts(grade) if grade else {}
    saved_rankings = load_prev_rankings(grade) if grade else {}

    class_names = detection.get("class_names", [])
    n_students = detection.get("n_students_per_class", {})

    class_info = []
    for cn in class_names:
        detected_count = n_students.get(cn, 0)
        # 默认应考人数 = 实考人数（从 Excel 自动统计）
        n_actual = saved_counts.get(cn, detected_count) if saved_counts else detected_count
        class_info.append({
            "name": cn,
            "n_attended": detected_count,
            "n_actual": n_actual,
        })

    return render_template("confirm.html",
                           detection=detection,
                           grade=grade,
                           subjects=subjects,
                           class_info=class_info,
                           teachers=saved_teachers,
                           prev_rankings=saved_rankings,
                           class_names=class_names)


# ─── Step 2→3: 执行计算 ──────────────────────────────────────────────────────

@app.route("/process", methods=["POST"])
def process():
    fpath = session.get("uploaded_file")
    if not fpath or not os.path.exists(fpath):
        flash("上传文件已过期，请重新上传。")
        return redirect(url_for("index"))

    grade = request.form.get("grade", "")
    exam_info = {
        "title": request.form.get("exam_title", "期末考试"),
        "grade": grade,
        "semester": request.form.get("semester", ""),
        "date": request.form.get("exam_date", ""),
    }

    subj_names = request.form.getlist("subj_name[]")
    subj_full = request.form.getlist("subj_full[]")
    subj_pass = request.form.getlist("subj_pass[]")
    subj_exc = request.form.getlist("subj_exc[]")

    subjects = []
    for i, name in enumerate(subj_names):
        name = name.strip()
        if not name:
            continue
        fs = float(subj_full[i]) if i < len(subj_full) else 100
        ps = float(subj_pass[i]) if i < len(subj_pass) and subj_pass[i].strip() else fs * 0.6
        es = float(subj_exc[i]) if i < len(subj_exc) and subj_exc[i].strip() else fs * 0.8
        subjects.append({"name": name, "full_score": fs, "pass_score": ps, "exc_score": es})

    if not subjects:
        flash("科目配置为空。")
        return redirect(url_for("confirm"))

    try:
        students = parse_excel(fpath, [s["name"] for s in subjects])
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("confirm"))

    if not students:
        flash("未读取到学生数据。")
        return redirect(url_for("confirm"))

    cls_names = request.form.getlist("cls_name[]")
    cls_n_actual = request.form.getlist("cls_n_actual[]")
    n_actual_map = {}
    for cn, na in zip(cls_names, cls_n_actual):
        cn = cn.strip()
        if cn:
            try:
                n_actual_map[cn] = int(na)
            except (ValueError, TypeError):
                pass

    prev_cls = request.form.getlist("prev_cls[]")
    prev_rank_vals = request.form.getlist("prev_rank[]")
    prev_rankings = {}
    for cls, rv in zip(prev_cls, prev_rank_vals):
        cls = cls.strip()
        if cls and rv.strip():
            try:
                prev_rankings[cls] = int(rv)
            except (ValueError, TypeError):
                pass

    try:
        advance_threshold = int(request.form.get("advance_threshold", 0))
    except ValueError:
        advance_threshold = 0
    if advance_threshold <= 0:
        advance_threshold = None

    teacher_names = request.form.getlist("teacher_name[]")
    teacher_subjects = request.form.getlist("teacher_subject[]")
    teacher_classes_raw = request.form.getlist("teacher_classes[]")
    teacher_assignments = []
    for tname, tsubj, tclasses_str in zip(teacher_names, teacher_subjects, teacher_classes_raw):
        tname = tname.strip()
        tsubj = tsubj.strip()
        if not tname or not tsubj:
            continue
        tclasses = [c.strip() for c in tclasses_str.replace("，", ",").split(",") if c.strip()]
        teacher_assignments.append({"teacher": tname, "subject": tsubj, "classes": tclasses})

    # 保存配置
    if request.form.get("save_config") == "1" and grade:
        save_teachers(grade, teacher_assignments)
        save_class_counts(grade, n_actual_map)
    if request.form.get("save_rankings") == "1" and grade:
        pass  # 计算完成后保存

    try:
        results = run_all(
            students=students,
            subjects=subjects,
            n_actual_map=n_actual_map,
            teacher_assignments=teacher_assignments,
            advance_threshold=advance_threshold,
            prev_rankings=prev_rankings or None,
        )
    except Exception as e:
        flash(f"计算出错：{e}")
        return redirect(url_for("confirm"))

    # 保存本次排名供下次使用
    if request.form.get("save_rankings") == "1" and grade:
        current_rankings = {
            cls: m["two_rate_rank"]
            for cls, m in results["class_metrics"].items()
        }
        save_prev_rankings(grade, current_rankings)

    save_result(results, exam_info)

    # 清理上传文件
    try:
        if os.path.exists(fpath):
            os.remove(fpath)
    except OSError:
        pass
    session.pop("uploaded_file", None)
    session.pop("detection", None)

    return redirect(url_for("results"))


# ─── Step 3: 结果页 ──────────────────────────────────────────────────────────

@app.route("/results")
def results():
    data, exam_info = load_result()
    if data is None:
        flash("没有可显示的结果，请先上传数据。")
        return redirect(url_for("index"))

    class_list = sorted(data["class_metrics"].values(), key=lambda m: m["structure_rank"])

    teacher_by_subject = {}
    for row in data["teacher_metrics"]:
        subj = row["subject"]
        teacher_by_subject.setdefault(subj, []).append(row)

    # 摘要统计
    students = data.get("students", [])
    total_students = len(students)
    total_classes = len(data["class_metrics"])
    highest_score = max((s["total"] for s in students), default=0)
    overall_avg = round(sum(s["total"] for s in students) / total_students, 1) if total_students else 0
    top_class = class_list[0]["class_name"] if class_list else ""
    class_names_list = [m["class_name"] for m in class_list]

    return render_template(
        "results.html",
        exam_info=exam_info,
        class_list=class_list,
        teacher_by_subject=teacher_by_subject,
        subjects=data["subjects"],
        active_subjects=data["active_subjects"],
        advance_threshold=data["advance_threshold"],
        total_classes=total_classes,
        total_students=total_students,
        highest_score=highest_score,
        overall_avg=overall_avg,
        top_class=top_class,
        class_names_list=class_names_list,
    )


@app.route("/download")
def download():
    data, exam_info = load_result()
    if data is None:
        flash("没有可下载的结果。")
        return redirect(url_for("index"))

    buf = BytesIO()
    export_excel(buf, data, exam_info)
    buf.seek(0)

    fname = f"{exam_info.get('grade','')}{exam_info.get('semester','')}成绩核算.xlsx"
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/download/<path:class_name>")
def download_class(class_name):
    """按班级下载报表。"""
    data, exam_info = load_result()
    if data is None:
        flash("没有可下载的结果。")
        return redirect(url_for("index"))
    if class_name not in data.get("class_metrics", {}):
        flash(f"未找到班级「{class_name}」的数据。")
        return redirect(url_for("results"))

    filtered = filter_data_for_class(data, class_name)
    buf = BytesIO()
    export_excel(buf, filtered, exam_info)
    buf.seek(0)

    fname = f"{exam_info.get('grade','')}{class_name}{exam_info.get('semester','')}成绩核算.xlsx"
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ─── 模板下载 ─────────────────────────────────────────────────────────────────

@app.route("/template/<grade_name>")
def template_download(grade_name):
    """按年级下载空白登分表模板。"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side

    preset = get_preset(grade_name)
    if not preset:
        flash(f"未找到年级「{grade_name}」的预设。")
        return redirect(url_for("index"))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "登分表"

    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center")

    # 标题行
    subj_names = [s["name"] for s in preset["subjects"]]
    headers = ["序号", "姓名", "班级", "考号"] + subj_names + ["总分", "班次", "级次"]
    ncols = len(headers)

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    title_cell = ws.cell(1, 1, f"____学年度____学期期末考试成绩统计表（{grade_name}）")
    title_cell.font = Font(bold=True, size=12)
    title_cell.alignment = center

    ws.cell(2, ncols, "考试日期：____").alignment = Alignment(horizontal="right")

    for i, h in enumerate(headers, 1):
        c = ws.cell(3, i, h)
        c.font = Font(bold=True)
        c.border = border
        c.alignment = center

    # 预填班级名示例（前几行）
    pattern = preset["class_pattern"]
    row_idx = 4
    for n in range(1, 8):
        ws.cell(row_idx, 1, row_idx - 3)
        ws.cell(row_idx, 3, pattern.format(n=n))
        for col in range(1, ncols + 1):
            ws.cell(row_idx, col).border = border
            ws.cell(row_idx, col).alignment = center
        row_idx += 1

    # 列宽
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 12
    for i in range(5, 5 + len(subj_names)):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = 8

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"{grade_name}登分表模板.xlsx"
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ─── 配置管理 ─────────────────────────────────────────────────────────────────

@app.route("/config")
def config_page():
    grade = request.args.get("grade", "七年级")
    teachers = load_teachers(grade)
    counts = load_class_counts(grade)
    rankings = load_prev_rankings(grade)
    preset = get_preset(grade)
    all_grades = get_all_grades()
    # 班级名列表：优先从已保存的 counts 获取，否则从预设生成
    if counts:
        class_names = list(counts.keys())
    elif preset:
        class_names = [preset["class_pattern"].format(n=i) for i in range(1, preset["n_active_subjects"] + 1)]
    else:
        class_names = []
    return render_template("config_edit.html",
                           grade=grade,
                           grades=all_grades,
                           teachers=teachers,
                           counts=counts,
                           rankings=rankings,
                           preset=preset,
                           is_builtin=is_builtin_grade(grade),
                           class_names=class_names)


@app.route("/config/save", methods=["POST"])
def config_save():
    grade = request.form.get("grade", "七年级")

    teacher_names = request.form.getlist("teacher_name[]")
    teacher_subjects = request.form.getlist("teacher_subject[]")
    teacher_classes_raw = request.form.getlist("teacher_classes[]")
    teacher_assignments = []
    for tname, tsubj, tclasses_str in zip(teacher_names, teacher_subjects, teacher_classes_raw):
        tname = tname.strip()
        tsubj = tsubj.strip()
        if not tname or not tsubj:
            continue
        tclasses = [c.strip() for c in tclasses_str.replace("，", ",").split(",") if c.strip()]
        teacher_assignments.append({"teacher": tname, "subject": tsubj, "classes": tclasses})

    cls_names = request.form.getlist("cls_name[]")
    cls_n_actual = request.form.getlist("cls_n_actual[]")
    counts = {}
    for cn, na in zip(cls_names, cls_n_actual):
        cn = cn.strip()
        if cn and na.strip():
            try:
                counts[cn] = int(na)
            except ValueError:
                pass

    save_teachers(grade, teacher_assignments)
    if counts:
        save_class_counts(grade, counts)

    flash(f"「{grade}」配置已保存。")
    return redirect(url_for("config_page", grade=grade))


# ─── 年级动态管理 ────────────────────────────────────────────────────────────

@app.route("/config/grade/add", methods=["POST"])
def grade_add():
    name = request.form.get("grade_name", "").strip()
    if not name:
        flash("请输入年级名称。")
        return redirect(url_for("config_page"))
    if get_preset(name):
        flash(f"年级「{name}」已存在。")
        return redirect(url_for("config_page", grade=name))

    # 获取默认科目列表（基于内置年级的模板）
    class_pattern = request.form.get("class_pattern", f"{name}{{n}}").strip()
    if not class_pattern:
        class_pattern = f"{name}{{n}}"

    # 默认科目：语文/数学/英语
    default_subjects = [
        {"name": "语文", "full_score": 120, "pass_score": 72, "exc_score": 96, "qualify": True},
        {"name": "数学", "full_score": 120, "pass_score": 72, "exc_score": 96, "qualify": True},
        {"name": "英语", "full_score": 140, "pass_score": 84, "exc_score": 112, "qualify": True},
    ]
    add_custom_grade(name, default_subjects, 3, class_pattern)
    flash(f"年级「{name}」已添加。请在配置页补充科目和教师信息。")
    return redirect(url_for("config_page", grade=name))


@app.route("/config/grade/delete", methods=["POST"])
def grade_delete():
    name = request.form.get("grade_name", "").strip()
    if not name:
        flash("未指定年级。")
        return redirect(url_for("config_page"))
    if is_builtin_grade(name):
        flash(f"「{name}」是内置年级，不能删除。")
        return redirect(url_for("config_page", grade=name))
    ok, msg = delete_custom_grade(name)
    if ok:
        flash(f"年级「{name}」已删除。")
    else:
        flash(msg)
    return redirect(url_for("config_page"))


# ─── 教师任课导入/导出 ────────────────────────────────────────────────────────

@app.route("/teachers/template")
def teacher_template():
    """下载教师任课信息导入模板。"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "教师任课"

    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)

    headers = ["教师姓名", "科目", "所带班级"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(1, i, h)
        c.font = header_font
        c.fill = header_fill
        c.border = border
        c.alignment = center

    examples = [
        ("张三", "语文", "七（1）, 七（2）"),
        ("李四", "数学", "七（1）, 七（3）"),
        ("王五", "英语", "七（2）, 七（3）, 七（4）"),
    ]
    for row_idx, (name, subj, classes) in enumerate(examples, 2):
        ws.cell(row_idx, 1, name).border = border
        ws.cell(row_idx, 2, subj).border = border
        ws.cell(row_idx, 3, classes).border = border
        ws.cell(row_idx, 1).alignment = center
        ws.cell(row_idx, 2).alignment = center
        ws.cell(row_idx, 1).font = Font(color="808080")
        ws.cell(row_idx, 2).font = Font(color="808080")
        ws.cell(row_idx, 3).font = Font(color="808080")

    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 35

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="教师任课导入模板.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/teachers/import", methods=["POST"])
def teacher_import():
    """从 Excel 导入教师任课信息。"""
    grade = request.form.get("grade", "七年级")
    file = request.files.get("teacher_file")
    if not file or not file.filename:
        flash("请选择教师任课 Excel 文件。")
        return redirect(url_for("config_page", grade=grade))

    try:
        df = pd.read_excel(file, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]

        col_name = None
        col_subj = None
        col_classes = None
        for col in df.columns:
            if "姓名" in col or "教师" in col:
                col_name = col
            elif "科目" in col:
                col_subj = col
            elif "班级" in col:
                col_classes = col

        if not col_name or not col_subj or not col_classes:
            flash("Excel 格式不正确，需包含「教师姓名」「科目」「所带班级」三列。")
            return redirect(url_for("config_page", grade=grade))

        teacher_assignments = []
        for _, row in df.iterrows():
            tname = str(row.get(col_name, "")).strip()
            tsubj = str(row.get(col_subj, "")).strip()
            tclasses_str = str(row.get(col_classes, "")).strip()
            if not tname or not tsubj or tname in ("nan", "None"):
                continue
            tclasses = [c.strip() for c in tclasses_str.replace("，", ",").split(",") if c.strip()]
            if tclasses:
                teacher_assignments.append({"teacher": tname, "subject": tsubj, "classes": tclasses})

        if not teacher_assignments:
            flash("未从文件中读取到有效的教师任课数据。")
            return redirect(url_for("config_page", grade=grade))

        save_teachers(grade, teacher_assignments)
        flash(f"成功导入 {len(teacher_assignments)} 条教师任课记录到「{grade}」。")

    except Exception as e:
        flash(f"导入失败：{e}")

    return redirect(url_for("config_page", grade=grade))


# ─── 算法参数配置 ─────────────────────────────────────────────────────────────

@app.route("/algo")
def algo_page():
    params = load_algo_params()
    return render_template("algo_edit.html", params=params, defaults=DEFAULT_PARAMS)


@app.route("/algo/save", methods=["POST"])
def algo_save():
    params = {
        "weights": {
            "avg_score": float(request.form.get("w_avg_score", 0.5)),
            "pass_rate": float(request.form.get("w_pass_rate", 0.2)),
            "excellent_rate": float(request.form.get("w_excellent_rate", 0.2)),
            "advance_rate": float(request.form.get("w_advance_rate", 0.15)),
            "attend_rate": float(request.form.get("w_attend_rate", 0.05)),
            "top_n_each": float(request.form.get("w_top_n_each", 0.2)),
        },
        "advance_ratio": float(request.form.get("advance_ratio", 0.75)),
        "top_n": int(request.form.get("top_n", 10)),
        "value_added": {
            "base_start": float(request.form.get("va_base_start", 5.1)),
            "base_step": float(request.form.get("va_base_step", 0.1)),
            "progress_step": float(request.form.get("va_progress_step", 0.05)),
        },
        "teacher_weights": {
            "avg_score": float(request.form.get("tw_avg_score", 0.5)),
            "pass_rate": float(request.form.get("tw_pass_rate", 0.25)),
            "excellent_rate": float(request.form.get("tw_excellent_rate", 0.25)),
        },
        "score_lines": {
            "pass_ratio": float(request.form.get("sl_pass_ratio", 0.6)),
            "excellent_ratio": float(request.form.get("sl_excellent_ratio", 0.8)),
        },
    }
    save_algo_params(params)
    flash("算法参数已保存。")
    return redirect(url_for("algo_page"))


@app.route("/algo/reset", methods=["POST"])
def algo_reset():
    reset_algo_params()
    flash("算法参数已恢复默认值。")
    return redirect(url_for("algo_page"))


if __name__ == "__main__":
    import webbrowser
    import threading
    from activation import check_activation, get_machine_id, try_activate

    port = 5000
    is_frozen = getattr(sys, 'frozen', False)

    # ── 激活检查路由 ──
    @app.route("/activate", methods=["GET", "POST"])
    def activate_page():
        from activation import check_trial
        mid = get_machine_id() or "无法获取机器码"

        # 获取试用状态
        trial_valid, trial_remaining, trial_message = check_trial()
        trial_expired = not trial_valid and trial_remaining == 0

        if request.method == "POST":
            code = request.form.get("code", "").strip()
            result = try_activate(code)
            if result["success"]:
                if result.get("is_trial"):
                    msg = "试用激活成功！请重新启动程序。"
                else:
                    msg = "激活成功！请重新启动程序。"
                return render_template_string(
                    f"<script>alert('{msg}');window.close();</script>"
                )
            return render_template("activation.html", machine_id=mid, error=result["error"],
                                 trial_message=trial_message, trial_expired=trial_expired)
        return render_template("activation.html", machine_id=mid, error=None,
                             trial_message=trial_message, trial_expired=trial_expired)

    # ── 未激活时拦截所有请求 ──
    @app.before_request
    def _check_activation():
        if request.path not in ("/activate", "/static/icon.png") and not request.path.startswith("/static/"):
            status, message = check_activation()
            if status == "activated":
                return  # 永久激活，正常访问
            elif status == "trial":
                # 试用中，设置提示信息
                if not hasattr(app, '_trial_warned'):
                    app._trial_warned = True
                    # 可以在页面上显示剩余天数
                return
            else:
                # 过期或无效，跳转激活页面
                return redirect(url_for("activate_page"))

    if is_frozen:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
        app.run(debug=False, host="127.0.0.1", port=port)
    else:
        app.run(debug=True, host="0.0.0.0", port=port)
