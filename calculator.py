"""
计算引擎：纯函数，无 Flask 依赖。
处理流程：
  A. 丰富学生数据（总分、班次、级次）
  B. 按班级聚合（结构成绩表指标）
  C. 按教师聚合（教师考核指标）
"""

from collections import defaultdict


# ─── A. 学生排名 ───────────────────────────────────────────────────────────────

def enrich_students(students, subjects):
    """
    给每个学生计算 total / class_rank / grade_rank / 各科排名。
    students: list of dict，含 name / class_name / exam_no / scores(dict)
    subjects: list of dict，含 name / full_score（仅用于确定科目列表）
    返回修改后的 students 列表（in-place）。
    """
    subject_names = [s["name"] for s in subjects]

    for stu in students:
        stu["total"] = sum(stu["scores"].get(sn, 0) or 0 for sn in subject_names)

    # 级次：全年级按总分降序，RANK（并列同名次，下一名跳过）
    totals = [s["total"] for s in students]
    for stu in students:
        stu["grade_rank"] = sum(1 for t in totals if t > stu["total"]) + 1

    # 班次：班内按总分降序
    classes = set(s["class_name"] for s in students)
    for cls in classes:
        cls_totals = [s["total"] for s in students if s["class_name"] == cls]
        for stu in students:
            if stu["class_name"] == cls:
                stu["class_rank"] = sum(1 for t in cls_totals if t > stu["total"]) + 1

    # 单科年级排名 & 班级排名
    for sn in subject_names:
        all_scores = [s["scores"].get(sn, 0) or 0 for s in students]
        for stu in students:
            sc = stu["scores"].get(sn, 0) or 0
            stu.setdefault("subject_grade_rank", {})[sn] = sum(1 for v in all_scores if v > sc) + 1

        for cls in classes:
            cls_scores = [s["scores"].get(sn, 0) or 0 for s in students if s["class_name"] == cls]
            for stu in students:
                if stu["class_name"] == cls:
                    sc = stu["scores"].get(sn, 0) or 0
                    stu.setdefault("subject_class_rank", {})[sn] = sum(1 for v in cls_scores if v > sc) + 1

    return students


# ─── B. 班级指标 ───────────────────────────────────────────────────────────────

def compute_class_metrics(students, subjects, n_actual_map, advance_threshold, prev_rankings=None, algo_params=None):
    """
    subjects: list of {name, full_score}，按考试科目顺序排列（0分科目不计入人均）
    n_actual_map: {class_name: 应考人数}，由用户提供（可从数据推断兜底）
    advance_threshold: 进线级次上限（≈全年级人数×75%）
    prev_rankings: {class_name: 上次二率一分排名}，可为 None
    algo_params: 算法参数字典（权重、增值系数等）
    返回: {class_name: metrics_dict}
    """
    if prev_rankings is None:
        prev_rankings = {}
    if algo_params is None:
        from algo_config import DEFAULT_PARAMS
        algo_params = DEFAULT_PARAMS

    w = algo_params["weights"]
    va = algo_params["value_added"]
    top_n = algo_params.get("top_n", 10)
    score_lines = algo_params.get("score_lines", {})
    default_pass_ratio = score_lines.get("pass_ratio", 0.6)
    default_exc_ratio = score_lines.get("excellent_ratio", 0.8)

    # 按班级分组
    by_class = defaultdict(list)
    for stu in students:
        by_class[stu["class_name"]].append(stu)

    # 确定参与人均计算的科目（全年级该科有分的科目）
    active_subjects = []
    for subj in subjects:
        sn = subj["name"]
        has_score = any((s["scores"].get(sn) or 0) > 0 for s in students)
        if has_score:
            active_subjects.append(subj)

    n_active = len(active_subjects)

    raw_metrics = {}

    for cls, stus in by_class.items():
        n_actual = n_actual_map.get(cls) or len(stus)
        n_attended = sum(1 for s in stus if s["total"] > 0)

        # 各科总分（仅活跃科目）
        subj_totals = {
            subj["name"]: sum(s["scores"].get(subj["name"]) or 0 for s in stus)
            for subj in active_subjects
        }
        total_sum = sum(subj_totals.values())

        # 人均得分 E
        E = (total_sum / n_actual / n_active * w["avg_score"]) if n_actual and n_active else 0

        # 全科合格（所有活跃科目同时达及格线）
        def is_all_pass(stu):
            return all(
                (stu["scores"].get(s["name"]) or 0) >= s.get("pass_score", s["full_score"] * default_pass_ratio)
                for s in active_subjects
            )

        def is_all_excellent(stu):
            return all(
                (stu["scores"].get(s["name"]) or 0) >= s.get("exc_score", s["full_score"] * default_exc_ratio)
                for s in active_subjects
            )

        n_all_pass = sum(1 for s in stus if is_all_pass(s))
        pass_rate = n_all_pass / n_actual * 100 if n_actual else 0
        H = pass_rate * w["pass_rate"]

        n_all_excellent = sum(1 for s in stus if is_all_excellent(s))
        excellent_rate = n_all_excellent / n_actual * 100 if n_actual else 0
        K = excellent_rate * w["excellent_rate"]

        two_rate_score = E + H + K  # 二率一分小计 L

        # 进线人数
        n_advance = sum(1 for s in stus if s["grade_rank"] <= advance_threshold)
        advance_rate = n_advance / n_actual * 100 if n_actual else 0
        S = advance_rate * w["advance_rate"]

        # 参考率
        attend_rate = n_attended / n_actual * 100 if n_actual else 0
        V = attend_rate * w["attend_rate"]

        # 前N名
        n_top10 = sum(1 for s in stus if s["grade_rank"] <= top_n)
        X = n_top10 * w["top_n_each"]

        raw_metrics[cls] = {
            "class_name": cls,
            "n_actual": n_actual,
            "n_attended": n_attended,
            "total_sum": total_sum,
            "avg_total": total_sum / n_actual if n_actual else 0,
            "E": E,
            "n_all_pass": n_all_pass,
            "pass_rate": pass_rate,
            "H": H,
            "n_all_excellent": n_all_excellent,
            "excellent_rate": excellent_rate,
            "K": K,
            "two_rate_score": two_rate_score,
            "n_advance": n_advance,
            "advance_rate": advance_rate,
            "S": S,
            "n_attended": n_attended,
            "attend_rate": attend_rate,
            "V": V,
            "n_top10": n_top10,
            "X": X,
            # 各科明细（供人均及及格率表用）
            "subj_totals": subj_totals,
        }

    # 二率一分排名 M（按 two_rate_score 降序，RANK 并列）
    two_rate_scores = {cls: m["two_rate_score"] for cls, m in raw_metrics.items()}
    for cls, m in raw_metrics.items():
        score = m["two_rate_score"]
        m["two_rate_rank"] = sum(1 for v in two_rate_scores.values() if v > score) + 1

    # 增值分
    for cls, m in raw_metrics.items():
        M_rank = m["two_rate_rank"]
        Y = va["base_start"] - va["base_step"] * M_rank
        prev_rank = prev_rankings.get(cls)
        Z = (prev_rank - M_rank) * va["progress_step"] if prev_rank else 0
        m["Y"] = Y
        m["Z"] = Z
        m["AA"] = Y + Z

    # 结构总分 & 最终排名
    for cls, m in raw_metrics.items():
        m["structure_score"] = m["E"] + m["H"] + m["K"] + m["S"] + m["V"] + m["X"] + m["AA"]

    struct_scores = {cls: m["structure_score"] for cls, m in raw_metrics.items()}
    for cls, m in raw_metrics.items():
        score = m["structure_score"]
        m["structure_rank"] = sum(1 for v in struct_scores.values() if v > score) + 1

    return raw_metrics


def compute_subject_class_metrics(students, subjects, n_actual_map, algo_params=None):
    """
    人均及及格率表：按班级×科目统计（独立于全科合格逻辑）。
    返回: {class_name: {subject_name: {avg, pass_rate, excellent_rate, ...}}}
    """
    if algo_params is None:
        from algo_config import DEFAULT_PARAMS
        algo_params = DEFAULT_PARAMS

    tw = algo_params["teacher_weights"]
    score_lines = algo_params.get("score_lines", {})
    default_pass_ratio = score_lines.get("pass_ratio", 0.6)
    default_exc_ratio = score_lines.get("excellent_ratio", 0.8)
    by_class = defaultdict(list)
    for stu in students:
        by_class[stu["class_name"]].append(stu)

    result = {}
    for cls, stus in by_class.items():
        n_actual = n_actual_map.get(cls) or len(stus)
        result[cls] = {}
        for subj in subjects:
            sn = subj["name"]
            full = subj["full_score"]
            pass_line = subj.get("pass_score", full * default_pass_ratio)
            exc_line = subj.get("exc_score", full * default_exc_ratio)
            scores = [s["scores"].get(sn) or 0 for s in stus]
            total = sum(scores)
            avg = total / n_actual if n_actual else 0
            n_pass = sum(1 for sc in scores if sc >= pass_line)
            n_exc = sum(1 for sc in scores if sc >= exc_line)
            pass_rate = n_pass / n_actual * 100 if n_actual else 0
            exc_rate = n_exc / n_actual * 100 if n_actual else 0

            E_subj = avg * tw["avg_score"]
            H_subj = pass_rate * tw["pass_rate"]
            K_subj = exc_rate * tw["excellent_rate"]
            struct = E_subj + H_subj + K_subj

            result[cls][sn] = {
                "total": total,
                "avg": avg,
                "E": E_subj,
                "n_pass": n_pass,
                "pass_rate": pass_rate,
                "H": H_subj,
                "n_excellent": n_exc,
                "excellent_rate": exc_rate,
                "K": K_subj,
                "struct_score": struct,
            }

    # 科目内班级排名
    classes = list(result.keys())
    for subj in subjects:
        sn = subj["name"]
        scores_map = {cls: result[cls][sn]["struct_score"] for cls in classes if sn in result[cls]}
        for cls in classes:
            if sn in result[cls]:
                sc = result[cls][sn]["struct_score"]
                result[cls][sn]["rank"] = sum(1 for v in scores_map.values() if v > sc) + 1

    return result


# ─── C. 教师评比 ───────────────────────────────────────────────────────────────

def compute_teacher_metrics(teacher_assignments, subject_class_metrics, n_actual_map, subjects, algo_params=None):
    """
    teacher_assignments: list of {teacher, subject, classes}
    subject_class_metrics: 来自 compute_subject_class_metrics 的结果
    返回: list of teacher_metric dict，按科目分组
    """
    if algo_params is None:
        from algo_config import DEFAULT_PARAMS
        algo_params = DEFAULT_PARAMS

    tw = algo_params["teacher_weights"]
    full_score_map = {s["name"]: s["full_score"] for s in subjects}
    pass_score_map = {s["name"]: s.get("pass_score", s["full_score"] * 0.6) for s in subjects}
    exc_score_map = {s["name"]: s.get("exc_score", s["full_score"] * 0.8) for s in subjects}
    results = []

    by_subject = defaultdict(list)
    for ta in teacher_assignments:
        by_subject[ta["subject"]].append(ta)

    for subject, teachers in by_subject.items():
        full_score = full_score_map.get(subject, 100)
        teacher_rows = []
        for ta in teachers:
            teacher_name = ta["teacher"]
            classes = ta["classes"]

            total_score = 0
            n_students = 0
            n_pass = 0
            n_excellent = 0

            for cls in classes:
                n_act = n_actual_map.get(cls, 0)
                n_students += n_act
                if cls in subject_class_metrics and subject in subject_class_metrics[cls]:
                    sm = subject_class_metrics[cls][subject]
                    total_score += sm["total"]
                    n_pass += sm["n_pass"]
                    n_excellent += sm["n_excellent"]

            avg = total_score / n_students if n_students else 0
            pass_rate = n_pass / n_students * 100 if n_students else 0
            exc_rate = n_excellent / n_students * 100 if n_students else 0

            M = avg / full_score * (tw["avg_score"] * 100)
            Q_score = pass_rate * tw["pass_rate"]
            U_score = exc_rate * tw["excellent_rate"]
            eval_score = M + Q_score + U_score

            teacher_rows.append({
                "subject": subject,
                "teacher": teacher_name,
                "classes": classes,
                "n_students": n_students,
                "total_score": total_score,
                "avg": avg,
                "n_pass": n_pass,
                "pass_rate": pass_rate,
                "n_excellent": n_excellent,
                "excellent_rate": exc_rate,
                "M": M,
                "Q": Q_score,
                "U": U_score,
                "eval_score": eval_score,
            })

        # 全科汇总行（用于均差计算）
        total_n = sum(r["n_students"] for r in teacher_rows)
        total_sum = sum(r["total_score"] for r in teacher_rows)
        grade_avg = total_sum / total_n if total_n else 0
        grade_pass = sum(r["n_pass"] for r in teacher_rows)
        grade_exc = sum(r["n_excellent"] for r in teacher_rows)
        grade_pass_rate = grade_pass / total_n * 100 if total_n else 0
        grade_exc_rate = grade_exc / total_n * 100 if total_n else 0
        grade_M = grade_avg / full_score * (tw["avg_score"] * 100)
        grade_Q = grade_pass_rate * tw["pass_rate"]
        grade_U = grade_exc_rate * tw["excellent_rate"]

        # 均差 & 排名
        eval_scores = [r["eval_score"] for r in teacher_rows]
        for r in teacher_rows:
            r["avg_diff"] = r["avg"] - grade_avg
            r["pass_diff"] = r["Q"] - grade_Q
            r["exc_diff"] = r["U"] - grade_U
            r["rank"] = sum(1 for v in eval_scores if v > r["eval_score"]) + 1

        summary = {
            "subject": subject,
            "teacher": "全级",
            "classes": [],
            "n_students": total_n,
            "total_score": total_sum,
            "avg": grade_avg,
            "n_pass": grade_pass,
            "pass_rate": grade_pass_rate,
            "n_excellent": grade_exc,
            "excellent_rate": grade_exc_rate,
            "M": grade_M,
            "Q": grade_Q,
            "U": grade_U,
            "eval_score": grade_M + grade_Q + grade_U,
            "avg_diff": 0,
            "pass_diff": 0,
            "exc_diff": 0,
            "rank": None,
        }

        results.extend(teacher_rows)
        results.append(summary)

    return results


# ─── 主入口（供 app.py 调用） ──────────────────────────────────────────────────

def run_all(students, subjects, n_actual_map, teacher_assignments,
            advance_threshold=None, prev_rankings=None, algo_params=None):
    """
    一次性完成所有计算，返回供模板和导出使用的完整结果字典。
    """
    if algo_params is None:
        from algo_config import load_algo_params
        algo_params = load_algo_params()

    total_students = len(students)
    if advance_threshold is None:
        advance_threshold = round(total_students * algo_params.get("advance_ratio", 0.75))

    enrich_students(students, subjects)

    class_metrics = compute_class_metrics(
        students, subjects, n_actual_map, advance_threshold, prev_rankings, algo_params
    )
    subject_class_metrics = compute_subject_class_metrics(
        students, subjects, n_actual_map, algo_params
    )
    teacher_metrics = compute_teacher_metrics(
        teacher_assignments, subject_class_metrics, n_actual_map, subjects, algo_params
    )

    # 有活跃分数的科目列表（用于人均及及格率表标题）
    active_subjects = [
        s for s in subjects
        if any((stu["scores"].get(s["name"]) or 0) > 0 for stu in students)
    ]

    return {
        "students": students,
        "subjects": subjects,
        "active_subjects": active_subjects,
        "class_metrics": class_metrics,
        "subject_class_metrics": subject_class_metrics,
        "teacher_metrics": teacher_metrics,
        "advance_threshold": advance_threshold,
        "total_students": total_students,
    }
