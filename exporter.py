"""
Excel 四张报表导出器。
"""

from openpyxl import Workbook
from openpyxl.styles import (Alignment, Border, Font, PatternFill, Side,
                              numbers)
from openpyxl.utils import get_column_letter


# ─── 样式常量（夏日清凉风主题） ────────────────────────────────────────────────

THIN = Side(style="thin", color="99F6E4")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

HEADER_FILL = PatternFill("solid", fgColor="0E7490")
HEADER_FONT = Font(name="Microsoft YaHei", bold=True, size=10, color="FFFFFF")
SUBHEADER_FILL = PatternFill("solid", fgColor="CCFBF1")
SUBHEADER_FONT = Font(name="Microsoft YaHei", bold=True, size=10, color="134E4A")
HIGHLIGHT_FILL = PatternFill("solid", fgColor="FEF3C7")
ROW_EVEN_FILL = PatternFill("solid", fgColor="F0FFFE")
TITLE_FONT = Font(name="Microsoft YaHei", bold=True, size=14, color="0E7490")
BODY_FONT = Font(name="Microsoft YaHei", size=10)
BOLD = Font(name="Microsoft YaHei", bold=True, size=10)
BOLD_HEADER = Font(name="Microsoft YaHei", bold=True, size=11)


def _style(cell, fill=None, bold=False, border=True, center=True, font=None):
    if fill:
        cell.fill = fill
    if font:
        cell.font = font
    elif bold:
        cell.font = BOLD
    else:
        cell.font = BODY_FONT
    if border:
        cell.border = BORDER
    if center:
        cell.alignment = CENTER


def _write_title(ws, title, ncols, date_str=""):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(1, 1, title)
    c.font = TITLE_FONT
    c.alignment = CENTER
    if date_str:
        dc = ws.cell(2, ncols, date_str)
        dc.alignment = Alignment(horizontal="right")
        dc.font = BODY_FONT


# ─── Sheet 1：登分表 ──────────────────────────────────────────────────────────

def _sheet_dengfen(wb, data, exam_info):
    ws = wb.create_sheet("登分表")
    students = data["students"]
    subjects = data["subjects"]
    subj_names = [s["name"] for s in subjects]

    # 表头：序号 | 姓名 | 班级 | 考号 | 科目1 | 科目1班名 | 科目1级名 | ... | 总分 | 班次 | 级次
    headers = ["序号", "姓名", "班级", "考号"]
    for sn in subj_names:
        headers += [sn, "班名", "级名"]
    headers += ["总分", "班次", "级次"]
    ncols = len(headers)

    title = f"{exam_info.get('title','')}成绩统计表"
    _write_title(ws, title, ncols, exam_info.get("date", ""))

    ws.append([])  # 空行
    ws.append(headers)
    for i in range(1, ncols + 1):
        c = ws.cell(3, i)
        _style(c, HEADER_FILL, bold=True, font=HEADER_FONT)

    # 按班级、班次排序
    sorted_students = sorted(students, key=lambda s: (s["class_name"], s.get("class_rank", 9999)))

    for idx, stu in enumerate(sorted_students, 1):
        row = [idx, stu["name"], stu["class_name"], stu["exam_no"]]
        for sn in subj_names:
            score = stu["scores"].get(sn, 0)
            cls_rank = stu.get("subject_class_rank", {}).get(sn, "")
            grade_rank = stu.get("subject_grade_rank", {}).get(sn, "")
            row += [score, cls_rank, grade_rank]
        row += [stu["total"], stu.get("class_rank", ""), stu.get("grade_rank", "")]
        ws.append(row)
        row_fill = ROW_EVEN_FILL if idx % 2 == 0 else None
        for i in range(1, len(row) + 1):
            c = ws.cell(ws.max_row, i)
            c.border = BORDER
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font = BODY_FONT
            if row_fill:
                c.fill = row_fill

    # 列宽
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 8
    ws.column_dimensions["C"].width = 9
    ws.column_dimensions["D"].width = 12
    col_idx = 5
    for _ in subj_names:
        ws.column_dimensions[get_column_letter(col_idx)].width = 7      # 分数
        ws.column_dimensions[get_column_letter(col_idx + 1)].width = 5  # 班名
        ws.column_dimensions[get_column_letter(col_idx + 2)].width = 5  # 级名
        col_idx += 3
    ws.column_dimensions[get_column_letter(col_idx)].width = 7      # 总分
    ws.column_dimensions[get_column_letter(col_idx + 1)].width = 5  # 班次
    ws.column_dimensions[get_column_letter(col_idx + 2)].width = 5  # 级次
    ws.row_dimensions[1].height = 20


# ─── Sheet 2：考试结构成绩表 ───────────────────────────────────────────────────

def _sheet_structure(wb, data, exam_info):
    ws = wb.create_sheet("考试结构成绩表")
    class_metrics = data["class_metrics"]
    classes = sorted(class_metrics.keys())

    title = f"{exam_info.get('title','')}班级结构成绩统计表"
    ncols = 24
    _write_title(ws, title, ncols, exam_info.get("date", ""))
    ws.append([])

    # 表头两行
    headers_r1 = ["项目", "人均成绩（50%）", "", "", "",
                  "全科合格率（20%）", "", "",
                  "全科优秀率（20%）", "", "",
                  "二率一分", "", "",
                  "进线率（15%）", "", "",
                  "参考率（5%）", "",
                  "前10名", "",
                  "增值评价", "", "",
                  "结构总分", "排名"]
    headers_r2 = ["班级", "人均总分", "实考人数", "应考人数", "得分",
                  "合格人数", "合格率%", "得分",
                  "优秀人数", "优秀率%", "得分",
                  "小计", "排名", "上次排名",
                  "进线人数", "进线率%", "得分",
                  "参考率%", "得分",
                  "人数", "得分",
                  "基础分", "增值分", "合计",
                  "", ""]

    ws.append(headers_r1[:26])
    ws.append(headers_r2[:26])

    for col in range(1, 27):
        for r in [3, 4]:
            c = ws.cell(r, col)
            if r == 3:
                _style(c, HEADER_FILL, bold=True, font=HEADER_FONT)
            else:
                _style(c, SUBHEADER_FILL, bold=True, font=SUBHEADER_FONT)

    for row_idx, cls in enumerate(classes):
        m = class_metrics[cls]
        row = [
            cls,
            round(m["avg_total"], 4), m["n_attended"], m["n_actual"], round(m["E"], 4),
            m["n_all_pass"], round(m["pass_rate"], 4), round(m["H"], 4),
            m["n_all_excellent"], round(m["excellent_rate"], 4), round(m["K"], 4),
            round(m["two_rate_score"], 4), m["two_rate_rank"], "",
            m["n_advance"], round(m["advance_rate"], 4), round(m["S"], 4),
            round(m["attend_rate"], 4), round(m["V"], 4),
            m["n_top10"], round(m["X"], 4),
            round(m["Y"], 4), round(m["Z"], 4), round(m["AA"], 4),
            round(m["structure_score"], 4), m["structure_rank"],
        ]
        ws.append(row)
        row_fill = ROW_EVEN_FILL if row_idx % 2 == 0 else None
        for i, val in enumerate(row, 1):
            c = ws.cell(ws.max_row, i)
            c.border = BORDER
            c.alignment = CENTER
            c.font = BODY_FONT
            if row_fill:
                c.fill = row_fill
            if i == 25:
                c.fill = HIGHLIGHT_FILL
                c.font = BOLD

    for i in range(1, 27):
        ws.column_dimensions[get_column_letter(i)].width = max(8, 10)


# ─── Sheet 3：人均及及格率 ────────────────────────────────────────────────────

def _sheet_jigelv(wb, data, exam_info):
    ws = wb.create_sheet("人均及及格率")
    subj_cls = data["subject_class_metrics"]
    active_subjects = data["active_subjects"]
    class_metrics = data["class_metrics"]
    classes = sorted(subj_cls.keys())

    title = f"{exam_info.get('title','')}班级人均及及格率统计表"
    per_subj = 9  # 每科列数: 总分/人均/得分50%/及格数/及格率/得分25%/优秀数/优秀率/得分25% + 结构分 + 名次 = 11, 用10
    per_subj_cols = 11
    ncols = 2 + len(active_subjects) * per_subj_cols + 2
    _write_title(ws, title, ncols, exam_info.get("date", ""))
    ws.append([])

    # 表头行1：班级 | 科目组 | ...
    row_h1 = ["班级", "应考人数"]
    for s in active_subjects:
        row_h1 += [s["name"]] + [""] * (per_subj_cols - 1)
    row_h1 += ["结构总分", "名次"]
    ws.append(row_h1)

    # 表头行2：各科子列
    row_h2 = ["", ""]
    for _ in active_subjects:
        row_h2 += ["总分", "人均", "得分50%", "及格人数", "及格率%", "得分25%", "优秀人数", "优秀率%", "得分25%", "结构分", "名次"]
    row_h2 += ["", ""]
    ws.append(row_h2)

    for col in range(1, ncols + 1):
        for r in [3, 4]:
            c = ws.cell(r, col)
            if r == 3:
                _style(c, HEADER_FILL, bold=True, font=HEADER_FONT)
            else:
                _style(c, SUBHEADER_FILL, bold=True, font=SUBHEADER_FONT)

    # 数据行
    for row_idx, cls in enumerate(classes):
        m = subj_cls.get(cls, {})
        n_actual = class_metrics[cls]["n_actual"] if cls in class_metrics else ""
        row = [cls, n_actual]
        for s in active_subjects:
            sn = s["name"]
            sm = m.get(sn, {})
            row += [
                round(sm.get("total", 0), 2),
                round(sm.get("avg", 0), 4),
                round(sm.get("E", 0), 4),
                sm.get("n_pass", 0),
                round(sm.get("pass_rate", 0), 4),
                round(sm.get("H", 0), 4),
                sm.get("n_excellent", 0),
                round(sm.get("excellent_rate", 0), 4),
                round(sm.get("K", 0), 4),
                round(sm.get("struct_score", 0), 4),
                sm.get("rank", ""),
            ]
        if cls in class_metrics:
            cm = class_metrics[cls]
            row += [round(cm["structure_score"], 4), cm["structure_rank"]]
        else:
            row += ["", ""]
        ws.append(row)
        row_fill = ROW_EVEN_FILL if row_idx % 2 == 0 else None
        for i in range(1, len(row) + 1):
            c = ws.cell(ws.max_row, i)
            c.border = BORDER
            c.alignment = CENTER
            c.font = BODY_FONT
            if row_fill:
                c.fill = row_fill

    for i in range(1, ncols + 1):
        ws.column_dimensions[get_column_letter(i)].width = 9


# ─── Sheet 4：任课教师成绩评比表 ─────────────────────────────────────────────

def _sheet_teacher(wb, data, exam_info):
    ws = wb.create_sheet("任课教师成绩评比表")
    teacher_metrics = data["teacher_metrics"]

    title = f"{exam_info.get('title','')}教师成绩统计表"
    ncols = 16
    _write_title(ws, title, ncols, exam_info.get("date", ""))
    ws.append([])

    headers = ["年级", "科目", "教者", "班级",
               "总分", "应考人数", "平均分", "均差",
               "平均分得分(50%)",
               "及格人数", "实考人数", "及格率%", "均差", "及格率得分(25%)",
               "优秀人数", "优秀率%", "均差", "优秀率得分(25%)",
               "考核总分", "学科排名", "教师签名"]
    ws.append(headers[:21])
    for i in range(1, 22):
        c = ws.cell(3, i)
        _style(c, HEADER_FILL, bold=True, font=HEADER_FONT)

    grade = exam_info.get("grade", "")
    current_subject = None
    row_counter = 0

    for r in teacher_metrics:
        subj = r["subject"]
        teacher = r["teacher"]
        is_summary = teacher == "全级"

        row = [
            grade if not is_summary and subj != current_subject else "",
            subj if subj != current_subject else "",
            teacher,
            "、".join(r["classes"]) if r["classes"] else "",
            round(r["total_score"], 2),
            r["n_students"],
            round(r["avg"], 4),
            round(r.get("avg_diff", 0), 4) if not is_summary else "",
            round(r["M"], 4),
            r["n_pass"],
            "",
            round(r["pass_rate"], 4),
            round(r.get("pass_diff", 0), 4) if not is_summary else "",
            round(r["Q"], 4),
            r["n_excellent"],
            round(r["excellent_rate"], 4),
            round(r.get("exc_diff", 0), 4) if not is_summary else "",
            round(r["U"], 4),
            round(r["eval_score"], 4),
            r["rank"] if r["rank"] is not None else "",
            "",
        ]

        ws.append(row[:21])
        row_fill = SUBHEADER_FILL if is_summary else (ROW_EVEN_FILL if row_counter % 2 == 0 else None)
        for i in range(1, 22):
            c = ws.cell(ws.max_row, i)
            c.border = BORDER
            c.alignment = CENTER
            c.font = BODY_FONT
            if row_fill:
                c.fill = row_fill
            if i == 19:
                c.fill = HIGHLIGHT_FILL
                c.font = BOLD

        if subj != current_subject:
            current_subject = subj
        row_counter += 1

    for i in range(1, 22):
        ws.column_dimensions[get_column_letter(i)].width = 10
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 14


# ─── 数据过滤 ─────────────────────────────────────────────────────────────────

def filter_data_for_class(data, class_name):
    """过滤数据，仅保留指定班级的信息。"""
    filtered = {}

    # 学生：仅目标班级
    filtered["students"] = [s for s in data["students"] if s["class_name"] == class_name]

    # 科目配置透传
    filtered["subjects"] = data["subjects"]
    filtered["active_subjects"] = data["active_subjects"]

    # 班级指标：仅目标班级
    filtered["class_metrics"] = {class_name: data["class_metrics"][class_name]}

    # 分科班级指标：仅目标班级
    filtered["subject_class_metrics"] = {class_name: data["subject_class_metrics"][class_name]}

    # 教师评比：仅保留教目标班级的教师 + 对应科目的"全级"汇总行
    filtered_teachers = []
    subjects_with_teachers = set()
    for t in data["teacher_metrics"]:
        if t["teacher"] == "全级":
            continue
        if class_name in t.get("classes", []):
            filtered_teachers.append(t)
            subjects_with_teachers.add(t["subject"])
    for t in data["teacher_metrics"]:
        if t["teacher"] == "全级" and t["subject"] in subjects_with_teachers:
            filtered_teachers.append(t)
    filtered["teacher_metrics"] = filtered_teachers

    # 透传
    filtered["advance_threshold"] = data["advance_threshold"]
    filtered["total_students"] = len(filtered["students"])

    return filtered


# ─── 主导出函数 ───────────────────────────────────────────────────────────────

def export_excel(buf, data, exam_info):
    wb = Workbook()
    wb.remove(wb.active)

    _sheet_dengfen(wb, data, exam_info)
    _sheet_structure(wb, data, exam_info)
    _sheet_jigelv(wb, data, exam_info)
    _sheet_teacher(wb, data, exam_info)

    # 冻结窗格 + 打印设置
    for ws in wb.worksheets:
        if ws.title == "登分表":
            ws.freeze_panes = "A4"
        elif ws.title in ("考试结构成绩表", "人均及及格率"):
            ws.freeze_panes = "A5"
        elif ws.title == "任课教师成绩评比表":
            ws.freeze_panes = "A4"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True

    wb.save(buf)
