"""
오성중학교 동아리 편성 시스템
Flask + SQLite 웹 애플리케이션
"""

import os
import random
import csv
import io
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, Response, g
)
import sqlite3

# ============================================
# 앱 설정
# ============================================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "oseong-club-secret-2026")
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "club_system.db")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "oseong2026")

# ============================================
# 데이터베이스 연결
# ============================================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    """데이터베이스 초기화"""
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    
    db.executescript("""
        CREATE TABLE IF NOT EXISTS clubs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '기타',
            max_capacity INTEGER NOT NULL DEFAULT 20,
            min_capacity INTEGER NOT NULL DEFAULT 5,
            teacher TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade INTEGER NOT NULL,
            class_num INTEGER NOT NULL,
            number INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(grade, class_num, number)
        );

        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE,
            first_choice INTEGER NOT NULL,
            second_choice INTEGER NOT NULL,
            third_choice INTEGER NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (first_choice) REFERENCES clubs(id),
            FOREIGN KEY (second_choice) REFERENCES clubs(id),
            FOREIGN KEY (third_choice) REFERENCES clubs(id)
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE,
            club_id INTEGER NOT NULL,
            preference_rank INTEGER NOT NULL DEFAULT 0,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (club_id) REFERENCES clubs(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    
    # 기본 설정
    defaults = {
        "survey_open": "1",
        "show_results": "0",
        "is_assigned": "0",
        "default_max_capacity": "14",
        "default_min_capacity": "6",
    }
    for key, value in defaults.items():
        db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
    
    db.commit()
    db.close()

def get_setting(key, default="0"):
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, str(value))
    )
    db.commit()

# ============================================
# 샘플 데이터 삽입
# ============================================
def insert_sample_data():
    """처음 실행 시 샘플 데이터 삽입"""
    db = sqlite3.connect(DATABASE)
    
    # 동아리가 이미 있으면 스킵
    count = db.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
    if count > 0:
        db.close()
        return
    
    clubs = [
        ("축구부", "스포츠", 14, 6, "김체육", "축구 기술 향상 및 친선경기"),
        ("농구부", "스포츠", 14, 6, "이체육", "농구 기본기와 경기 운영"),
        ("배드민턴부", "스포츠", 14, 6, "박체육", "배드민턴 기초 및 실전 경기"),
        ("탁구부", "스포츠", 14, 6, "심체육", "탁구 기초 및 실전 경기"),
        ("미술부", "예술", 14, 6, "박미술", "다양한 미술 기법 학습과 작품 제작"),
        ("밴드부", "예술", 14, 6, "최음악", "악기 연주 및 합주 활동"),
        ("사진영상반", "예술", 14, 6, "남예술", "사진 촬영 및 영상 편집 활동"),
        ("과학탐구반", "학술", 14, 6, "정과학", "과학 실험 및 탐구 활동"),
        ("코딩반", "학술", 14, 6, "한정보", "프로그래밍 및 소프트웨어 개발"),
        ("독서토론반", "학술", 14, 6, "윤국어", "독서 및 토론 활동"),
        ("영어회화반", "학술", 14, 6, "오영어", "영어 회화 및 문화 체험"),
        ("수학탐구반", "학술", 14, 6, "장수학", "수학 심화 학습 및 문제 풀이"),
        ("역사탐방반", "학술", 14, 6, "고역사", "역사 유적 탐방 및 연구"),
        ("봉사단", "봉사", 14, 6, "강도덕", "지역사회 봉사활동"),
        ("환경지킴이", "봉사", 14, 6, "배환경", "환경 보호 및 생태 체험 활동"),
    ]
    db.executemany(
        "INSERT INTO clubs (name, category, max_capacity, min_capacity, teacher, description) VALUES (?, ?, ?, ?, ?, ?)",
        clubs
    )
    
    db.commit()
    db.close()

# ============================================
# 인증 데코레이터
# ============================================
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("student_id"):
            return redirect(url_for("student_login"))
        return f(*args, **kwargs)
    return decorated

# ============================================
# 배정 알고리즘
# ============================================
def run_assignment_algorithm():
    """1→2→3지망 순차 배정, 정원 초과 시 랜덤 추첨"""
    db = get_db()
    
    # 기존 배정 삭제
    db.execute("DELETE FROM assignments")
    
    # 데이터 로드
    clubs = {row["id"]: dict(row) for row in db.execute("SELECT * FROM clubs").fetchall()}
    preferences = db.execute("SELECT * FROM preferences").fetchall()
    
    # 동아리별 잔여 정원
    slots = {cid: c["max_capacity"] for cid, c in clubs.items()}
    
    assigned = set()  # 배정된 학생 ID
    results = []      # 배정 결과
    
    # 1지망 → 2지망 → 3지망 순서로 처리
    choice_keys = ["first_choice", "second_choice", "third_choice"]
    
    for round_num, choice_key in enumerate(choice_keys, 1):
        # 각 동아리별로 이번 라운드 지원자 수집
        club_applicants = {cid: [] for cid in clubs}
        
        for pref in preferences:
            sid = pref["student_id"]
            if sid in assigned:
                continue
            club_id = pref[choice_key]
            if club_id in slots and slots[club_id] > 0:
                club_applicants[club_id].append(sid)
        
        # 각 동아리별 배정
        for club_id, applicants in club_applicants.items():
            remaining = slots[club_id]
            if not applicants:
                continue
            
            if len(applicants) <= remaining:
                # 전원 배정
                for sid in applicants:
                    results.append((sid, club_id, round_num))
                    slots[club_id] -= 1
                    assigned.add(sid)
            else:
                # 랜덤 추첨
                random.shuffle(applicants)
                selected = applicants[:remaining]
                for sid in selected:
                    results.append((sid, club_id, round_num))
                    slots[club_id] -= 1
                    assigned.add(sid)
    
    # 미배정자 → 잔여석 배정
    all_student_ids = {row["student_id"] for row in preferences}
    unassigned = all_student_ids - assigned
    
    if unassigned:
        available = sorted(
            [(cid, slots[cid]) for cid in slots if slots[cid] > 0],
            key=lambda x: -x[1]
        )
        for sid in unassigned:
            for i, (club_id, remaining) in enumerate(available):
                if remaining > 0:
                    results.append((sid, club_id, 0))
                    available[i] = (club_id, remaining - 1)
                    assigned.add(sid)
                    break
    
    # DB에 저장
    db.executemany(
        "INSERT INTO assignments (student_id, club_id, preference_rank) VALUES (?, ?, ?)",
        results
    )
    db.commit()
    
    return len(results)

# ============================================
# 라우트: 메인
# ============================================
@app.route("/")
def landing():
    return render_template("landing.html")

# ============================================
# 라우트: 관리자
# ============================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("관리자로 로그인되었습니다.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("비밀번호가 올바르지 않습니다.", "error")
    return render_template("admin/login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("landing"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    total_students = db.execute("SELECT COUNT(*) as cnt FROM students").fetchone()["cnt"]
    total_clubs = db.execute("SELECT COUNT(*) as cnt FROM clubs").fetchone()["cnt"]
    total_prefs = db.execute("SELECT COUNT(*) as cnt FROM preferences").fetchone()["cnt"]
    total_assigned = db.execute("SELECT COUNT(*) as cnt FROM assignments").fetchone()["cnt"]
    
    # 학년별 통계
    grade_stats = []
    for g in range(1, 4):
        total = db.execute("SELECT COUNT(*) as cnt FROM students WHERE grade = ?", (g,)).fetchone()["cnt"]
        submitted = db.execute("""
            SELECT COUNT(*) as cnt FROM preferences p
            JOIN students s ON p.student_id = s.id
            WHERE s.grade = ?
        """, (g,)).fetchone()["cnt"]
        grade_stats.append({"grade": g, "total": total, "submitted": submitted})
    
    return render_template("admin/dashboard.html",
        total_students=total_students,
        total_clubs=total_clubs,
        total_prefs=total_prefs,
        total_assigned=total_assigned,
        grade_stats=grade_stats,
        survey_open=get_setting("survey_open") == "1",
        show_results=get_setting("show_results") == "1",
    )

# --- 동아리 관리 ---
@app.route("/admin/clubs")
@admin_required
def admin_clubs():
    db = get_db()
    clubs = db.execute("SELECT * FROM clubs ORDER BY category, name").fetchall()
    return render_template("admin/clubs.html",
        clubs=clubs,
        default_max=get_setting("default_max_capacity", "20"),
        default_min=get_setting("default_min_capacity", "5"),
    )

@app.route("/admin/clubs/add", methods=["POST"])
@admin_required
def admin_club_add():
    db = get_db()
    db.execute(
        "INSERT INTO clubs (name, category, max_capacity, min_capacity, teacher, description) VALUES (?, ?, ?, ?, ?, ?)",
        (
            request.form["name"],
            request.form["category"],
            int(request.form["max_capacity"]),
            int(request.form["min_capacity"]),
            request.form["teacher"],
            request.form.get("description", ""),
        )
    )
    db.commit()
    flash(f"'{request.form['name']}' 동아리가 추가되었습니다.", "success")
    return redirect(url_for("admin_clubs"))

@app.route("/admin/clubs/edit/<int:club_id>", methods=["POST"])
@admin_required
def admin_club_edit(club_id):
    db = get_db()
    db.execute(
        "UPDATE clubs SET name=?, category=?, max_capacity=?, min_capacity=?, teacher=?, description=? WHERE id=?",
        (
            request.form["name"],
            request.form["category"],
            int(request.form["max_capacity"]),
            int(request.form["min_capacity"]),
            request.form["teacher"],
            request.form.get("description", ""),
            club_id,
        )
    )
    db.commit()
    flash("동아리 정보가 수정되었습니다.", "success")
    return redirect(url_for("admin_clubs"))

@app.route("/admin/clubs/delete/<int:club_id>", methods=["POST"])
@admin_required
def admin_club_delete(club_id):
    db = get_db()
    db.execute("DELETE FROM clubs WHERE id = ?", (club_id,))
    db.commit()
    flash("동아리가 삭제되었습니다.", "success")
    return redirect(url_for("admin_clubs"))

# --- 학생 관리 ---
@app.route("/admin/students")
@admin_required
def admin_students():
    db = get_db()
    grade_filter = request.args.get("grade", "")
    class_filter = request.args.get("class_num", "")
    
    query = """
        SELECT s.*, 
            CASE WHEN p.id IS NOT NULL THEN 1 ELSE 0 END as has_pref
        FROM students s
        LEFT JOIN preferences p ON s.id = p.student_id
        WHERE 1=1
    """
    params = []
    if grade_filter:
        query += " AND s.grade = ?"
        params.append(int(grade_filter))
    if class_filter:
        query += " AND s.class_num = ?"
        params.append(int(class_filter))
    
    query += " ORDER BY s.grade, s.class_num, s.number"
    students = db.execute(query, params).fetchall()
    
    return render_template("admin/students.html",
        students=students,
        grade_filter=grade_filter,
        class_filter=class_filter,
    )

@app.route("/admin/students/add", methods=["POST"])
@admin_required
def admin_student_add():
    db = get_db()
    try:
        db.execute(
            "INSERT INTO students (grade, class_num, number, name) VALUES (?, ?, ?, ?)",
            (int(request.form["grade"]), int(request.form["class_num"]),
             int(request.form["number"]), request.form["name"])
        )
        db.commit()
        flash("학생이 추가되었습니다.", "success")
    except sqlite3.IntegrityError:
        flash("동일한 학년/반/번호의 학생이 이미 존재합니다.", "error")
    return redirect(url_for("admin_students"))

@app.route("/admin/students/delete/<int:student_id>", methods=["POST"])
@admin_required
def admin_student_delete(student_id):
    db = get_db()
    db.execute("DELETE FROM preferences WHERE student_id = ?", (student_id,))
    db.execute("DELETE FROM assignments WHERE student_id = ?", (student_id,))
    db.execute("DELETE FROM students WHERE id = ?", (student_id,))
    db.commit()
    flash("학생이 삭제되었습니다.", "success")
    return redirect(url_for("admin_students"))

@app.route("/admin/students/upload", methods=["POST"])
@admin_required
def admin_students_upload():
    """CSV 파일로 학생 명단 일괄 업로드"""
    file = request.files.get("csv_file")
    if not file or not file.filename:
        flash("파일을 선택해주세요.", "error")
        return redirect(url_for("admin_students"))
    
    if not file.filename.lower().endswith(".csv"):
        flash("CSV 파일만 업로드 가능합니다.", "error")
        return redirect(url_for("admin_students"))
    
    try:
        # 파일 읽기 (UTF-8, BOM 처리)
        raw = file.read()
        # BOM 제거 및 인코딩 처리
        for encoding in ["utf-8-sig", "utf-8", "euc-kr", "cp949"]:
            try:
                content = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            flash("파일 인코딩을 인식할 수 없습니다. UTF-8 또는 EUC-KR로 저장해주세요.", "error")
            return redirect(url_for("admin_students"))
        
        # CSV 파싱
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        
        if len(rows) < 2:
            flash("데이터가 없습니다. 헤더 행과 데이터 행이 필요합니다.", "error")
            return redirect(url_for("admin_students"))
        
        # 헤더 확인 (첫 행 건너뛰기)
        header = [h.strip() for h in rows[0]]
        data_rows = rows[1:]
        
        # 컬럼 매핑: 학년, 반, 번호, 이름 순서 자동 감지
        col_map = {}
        for i, h in enumerate(header):
            h_lower = h.replace(" ", "")
            if "학년" in h_lower:
                col_map["grade"] = i
            elif "반" in h_lower:
                col_map["class_num"] = i
            elif "번호" in h_lower or "번" == h_lower:
                col_map["number"] = i
            elif "이름" in h_lower or "성명" in h_lower:
                col_map["name"] = i
        
        # 컬럼을 찾지 못한 경우 순서대로 할당 (학년, 반, 번호, 이름)
        if len(col_map) < 4 and len(header) >= 4:
            col_map = {"grade": 0, "class_num": 1, "number": 2, "name": 3}
        elif len(col_map) < 4:
            flash("CSV 파일에 학년, 반, 번호, 이름 컬럼이 필요합니다.", "error")
            return redirect(url_for("admin_students"))
        
        db = get_db()
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for row_num, row in enumerate(data_rows, 2):
            if len(row) < 4:
                error_count += 1
                continue
            
            try:
                grade_str = row[col_map["grade"]].strip().replace("학년", "")
                class_str = row[col_map["class_num"]].strip().replace("반", "")
                number_str = row[col_map["number"]].strip().replace("번", "")
                name = row[col_map["name"]].strip()
                
                grade = int(grade_str)
                class_num = int(class_str)
                number = int(number_str)
                
                if not name or grade < 1 or grade > 3:
                    error_count += 1
                    continue
                
                db.execute(
                    "INSERT OR IGNORE INTO students (grade, class_num, number, name) VALUES (?, ?, ?, ?)",
                    (grade, class_num, number, name)
                )
                if db.execute("SELECT changes()").fetchone()[0] > 0:
                    success_count += 1
                else:
                    skip_count += 1
                    
            except (ValueError, IndexError):
                error_count += 1
                continue
        
        db.commit()
        
        msg = f"업로드 완료! {success_count}명 추가"
        if skip_count > 0:
            msg += f", {skip_count}명 중복(건너뜀)"
        if error_count > 0:
            msg += f", {error_count}건 오류"
        flash(msg, "success" if success_count > 0 else "warning")
        
    except Exception as e:
        flash(f"파일 처리 중 오류가 발생했습니다: {str(e)}", "error")
    
    return redirect(url_for("admin_students"))

@app.route("/admin/students/delete-all", methods=["POST"])
@admin_required
def admin_students_delete_all():
    """전체 학생 삭제"""
    db = get_db()
    db.execute("DELETE FROM preferences")
    db.execute("DELETE FROM assignments")
    db.execute("DELETE FROM students")
    db.commit()
    set_setting("is_assigned", "0")
    set_setting("show_results", "0")
    flash("모든 학생 데이터가 삭제되었습니다.", "success")
    return redirect(url_for("admin_students"))

@app.route("/admin/students/sample-csv")
@admin_required
def admin_students_sample_csv():
    """샘플 CSV 다운로드"""
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["학년", "반", "번호", "이름"])
    writer.writerow(["1", "1", "1", "김민준"])
    writer.writerow(["1", "1", "2", "이서윤"])
    writer.writerow(["1", "1", "3", "박도윤"])
    writer.writerow(["2", "1", "1", "최서연"])
    writer.writerow(["3", "2", "1", "정시우"])
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=student_sample.csv"}
    )

# --- 희망조사 현황 ---
@app.route("/admin/preferences")
@admin_required
def admin_preferences():
    db = get_db()
    
    clubs = db.execute("SELECT * FROM clubs ORDER BY category, name").fetchall()
    club_stats = []
    for club in clubs:
        first = db.execute("SELECT COUNT(*) as cnt FROM preferences WHERE first_choice = ?", (club["id"],)).fetchone()["cnt"]
        second = db.execute("SELECT COUNT(*) as cnt FROM preferences WHERE second_choice = ?", (club["id"],)).fetchone()["cnt"]
        third = db.execute("SELECT COUNT(*) as cnt FROM preferences WHERE third_choice = ?", (club["id"],)).fetchone()["cnt"]
        club_stats.append({
            "club": club,
            "first": first,
            "second": second,
            "third": third,
            "total": first + second + third,
            "competition": round(first / club["max_capacity"], 1) if first > 0 else 0,
        })
    
    total_students = db.execute("SELECT COUNT(*) as cnt FROM students").fetchone()["cnt"]
    total_prefs = db.execute("SELECT COUNT(*) as cnt FROM preferences").fetchone()["cnt"]
    
    # 미제출자 목록
    not_submitted = db.execute("""
        SELECT s.* FROM students s
        LEFT JOIN preferences p ON s.id = p.student_id
        WHERE p.id IS NULL
        ORDER BY s.grade, s.class_num, s.number
    """).fetchall()
    
    return render_template("admin/preferences.html",
        club_stats=club_stats,
        total_students=total_students,
        total_prefs=total_prefs,
        not_submitted=not_submitted,
        survey_open=get_setting("survey_open") == "1",
    )

# --- 배정 실행 ---
@app.route("/admin/assign")
@admin_required
def admin_assign():
    db = get_db()
    total_prefs = db.execute("SELECT COUNT(*) as cnt FROM preferences").fetchone()["cnt"]
    total_assigned = db.execute("SELECT COUNT(*) as cnt FROM assignments").fetchone()["cnt"]
    
    # 배정 통계
    assign_stats = None
    if total_assigned > 0:
        assign_stats = {
            "total": total_assigned,
            "first": db.execute("SELECT COUNT(*) as cnt FROM assignments WHERE preference_rank = 1").fetchone()["cnt"],
            "second": db.execute("SELECT COUNT(*) as cnt FROM assignments WHERE preference_rank = 2").fetchone()["cnt"],
            "third": db.execute("SELECT COUNT(*) as cnt FROM assignments WHERE preference_rank = 3").fetchone()["cnt"],
            "none": db.execute("SELECT COUNT(*) as cnt FROM assignments WHERE preference_rank = 0").fetchone()["cnt"],
        }
        # 동아리별 배정
        assign_stats["clubs"] = db.execute("""
            SELECT c.name, c.max_capacity,
                COUNT(a.id) as assigned_count,
                SUM(CASE WHEN a.preference_rank = 1 THEN 1 ELSE 0 END) as r1,
                SUM(CASE WHEN a.preference_rank = 2 THEN 1 ELSE 0 END) as r2,
                SUM(CASE WHEN a.preference_rank = 3 THEN 1 ELSE 0 END) as r3,
                SUM(CASE WHEN a.preference_rank = 0 THEN 1 ELSE 0 END) as r0
            FROM clubs c
            LEFT JOIN assignments a ON c.id = a.club_id
            GROUP BY c.id
            ORDER BY c.category, c.name
        """).fetchall()
    
    return render_template("admin/assign.html",
        total_prefs=total_prefs,
        total_assigned=total_assigned,
        assign_stats=assign_stats,
        is_assigned=get_setting("is_assigned") == "1",
    )

@app.route("/admin/assign/run", methods=["POST"])
@admin_required
def admin_assign_run():
    count = run_assignment_algorithm()
    set_setting("is_assigned", "1")
    flash(f"배정이 완료되었습니다! 총 {count}명이 배정되었습니다.", "success")
    return redirect(url_for("admin_assign"))

@app.route("/admin/assign/reset", methods=["POST"])
@admin_required
def admin_assign_reset():
    db = get_db()
    db.execute("DELETE FROM assignments")
    db.commit()
    set_setting("is_assigned", "0")
    set_setting("show_results", "0")
    flash("배정 결과가 초기화되었습니다.", "success")
    return redirect(url_for("admin_assign"))

# --- 배정 결과 ---
@app.route("/admin/results")
@admin_required
def admin_results():
    db = get_db()
    club_filter = request.args.get("club_id", "")
    grade_filter = request.args.get("grade", "")
    
    query = """
        SELECT s.grade, s.class_num, s.number, s.name as student_name,
            c.name as club_name, c.category, a.preference_rank
        FROM assignments a
        JOIN students s ON a.student_id = s.id
        JOIN clubs c ON a.club_id = c.id
        WHERE 1=1
    """
    params = []
    if club_filter:
        query += " AND a.club_id = ?"
        params.append(int(club_filter))
    if grade_filter:
        query += " AND s.grade = ?"
        params.append(int(grade_filter))
    
    query += " ORDER BY s.grade, s.class_num, s.number"
    results = db.execute(query, params).fetchall()
    clubs = db.execute("SELECT * FROM clubs ORDER BY name").fetchall()
    
    return render_template("admin/results.html",
        results=results,
        clubs=clubs,
        club_filter=club_filter,
        grade_filter=grade_filter,
        show_results=get_setting("show_results") == "1",
    )

@app.route("/admin/results/print")
@admin_required
def admin_results_print():
    """인쇄용 배정 결과"""
    db = get_db()
    view_type = request.args.get("view", "club")  # club 또는 class
    
    # 전체 배정 결과
    results = db.execute("""
        SELECT s.grade, s.class_num, s.number, s.name as student_name,
            c.id as club_id, c.name as club_name, c.category, c.teacher,
            a.preference_rank
        FROM assignments a
        JOIN students s ON a.student_id = s.id
        JOIN clubs c ON a.club_id = c.id
        ORDER BY s.grade, s.class_num, s.number
    """).fetchall()
    
    if not results:
        flash("배정 결과가 없습니다.", "error")
        return redirect(url_for("admin_results"))
    
    # 통계
    total = len(results)
    rank_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for r in results:
        rank_counts[r["preference_rank"]] = rank_counts.get(r["preference_rank"], 0) + 1
    
    # 동아리별 그룹핑
    clubs_grouped = {}
    for r in results:
        cid = r["club_id"]
        if cid not in clubs_grouped:
            clubs_grouped[cid] = {
                "name": r["club_name"],
                "category": r["category"],
                "teacher": r["teacher"],
                "students": []
            }
        clubs_grouped[cid]["students"].append(r)
    
    # 학급별 그룹핑
    class_grouped = {}
    for r in results:
        key = f"{r['grade']}-{r['class_num']}"
        if key not in class_grouped:
            class_grouped[key] = {
                "grade": r["grade"],
                "class_num": r["class_num"],
                "students": []
            }
        class_grouped[key]["students"].append(r)
    # 학급 순서 정렬
    class_grouped = dict(sorted(class_grouped.items()))
    
    return render_template("admin/results_print.html",
        results=results,
        clubs_grouped=clubs_grouped,
        class_grouped=class_grouped,
        view_type=view_type,
        total=total,
        rank_counts=rank_counts,
    )

@app.route("/admin/results/csv")
@admin_required
def admin_results_csv():
    db = get_db()
    results = db.execute("""
        SELECT s.grade, s.class_num, s.number, s.name,
            c.name as club_name, c.category, a.preference_rank
        FROM assignments a
        JOIN students s ON a.student_id = s.id
        JOIN clubs c ON a.club_id = c.id
        ORDER BY s.grade, s.class_num, s.number
    """).fetchall()
    
    output = io.StringIO()
    output.write('\ufeff')  # BOM for Excel
    writer = csv.writer(output)
    writer.writerow(["학년", "반", "번호", "이름", "배정동아리", "카테고리", "지망"])
    
    for r in results:
        rank = "잔여배정" if r["preference_rank"] == 0 else f"{r['preference_rank']}지망"
        writer.writerow([
            f"{r['grade']}학년", f"{r['class_num']}반", f"{r['number']}번",
            r["name"], r["club_name"], r["category"], rank
        ])
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=oseong_club_results.csv"}
    )

# --- 설정 ---
@app.route("/admin/settings")
@admin_required
def admin_settings():
    return render_template("admin/settings.html",
        survey_open=get_setting("survey_open") == "1",
        show_results=get_setting("show_results") == "1",
        default_max=get_setting("default_max_capacity", "20"),
        default_min=get_setting("default_min_capacity", "5"),
    )

@app.route("/admin/settings/toggle", methods=["POST"])
@admin_required
def admin_settings_toggle():
    key = request.form.get("key")
    if key in ("survey_open", "show_results"):
        current = get_setting(key)
        new_value = "0" if current == "1" else "1"
        set_setting(key, new_value)
        labels = {"survey_open": "희망조사 접수", "show_results": "결과 공개"}
        status = "시작" if new_value == "1" else "중지"
        flash(f"{labels[key]}가 {status}되었습니다.", "success")
    return redirect(url_for("admin_settings"))

@app.route("/admin/settings/defaults", methods=["POST"])
@admin_required
def admin_settings_defaults():
    max_cap = request.form.get("default_max_capacity", "20")
    min_cap = request.form.get("default_min_capacity", "5")
    try:
        max_val = int(max_cap)
        min_val = int(min_cap)
        if min_val > max_val:
            flash("최소 인원이 최대 정원보다 클 수 없습니다.", "error")
            return redirect(url_for("admin_settings"))
        if min_val < 1 or max_val < 1:
            flash("인원은 1명 이상이어야 합니다.", "error")
            return redirect(url_for("admin_settings"))
        set_setting("default_max_capacity", str(max_val))
        set_setting("default_min_capacity", str(min_val))
        flash(f"기본 정원이 최소 {min_val}명 / 최대 {max_val}명으로 설정되었습니다.", "success")
    except ValueError:
        flash("올바른 숫자를 입력해주세요.", "error")
    return redirect(url_for("admin_settings"))

@app.route("/admin/settings/reset-preferences", methods=["POST"])
@admin_required
def admin_reset_preferences():
    db = get_db()
    db.execute("DELETE FROM preferences")
    db.execute("DELETE FROM assignments")
    db.commit()
    set_setting("is_assigned", "0")
    set_setting("show_results", "0")
    flash("희망조사 및 배정 데이터가 초기화되었습니다.", "success")
    return redirect(url_for("admin_settings"))

@app.route("/admin/settings/reset-all", methods=["POST"])
@admin_required
def admin_reset_all():
    db = get_db()
    db.execute("DELETE FROM preferences")
    db.execute("DELETE FROM assignments")
    db.execute("DELETE FROM students")
    db.execute("DELETE FROM clubs")
    db.commit()
    set_setting("survey_open", "1")
    set_setting("is_assigned", "0")
    set_setting("show_results", "0")
    db.close()
    insert_sample_data()
    flash("시스템이 완전히 초기화되었습니다.", "success")
    return redirect(url_for("admin_settings"))

# ============================================
# 라우트: 학생
# ============================================
@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        grade = request.form.get("grade")
        class_num = request.form.get("class_num")
        number = request.form.get("number")
        name = request.form.get("name", "").strip()
        
        if not all([grade, class_num, number, name]):
            flash("모든 항목을 입력해주세요.", "error")
            return render_template("student/login.html")
        
        db = get_db()
        student = db.execute(
            "SELECT * FROM students WHERE grade=? AND class_num=? AND number=? AND name=?",
            (int(grade), int(class_num), int(number), name)
        ).fetchone()
        
        if student:
            session["student_id"] = student["id"]
            session["student_name"] = student["name"]
            session["student_grade"] = student["grade"]
            session["student_class"] = student["class_num"]
            return redirect(url_for("student_page"))
        else:
            flash("학생 정보를 찾을 수 없습니다. 다시 확인해주세요.", "error")
    
    return render_template("student/login.html")

@app.route("/student/logout")
def student_logout():
    session.pop("student_id", None)
    session.pop("student_name", None)
    session.pop("student_grade", None)
    session.pop("student_class", None)
    return redirect(url_for("landing"))

@app.route("/student")
@student_required
def student_page():
    db = get_db()
    student_id = session["student_id"]
    
    clubs = db.execute("SELECT * FROM clubs ORDER BY category, name").fetchall()
    preference = db.execute("SELECT * FROM preferences WHERE student_id = ?", (student_id,)).fetchone()
    assignment = db.execute("""
        SELECT a.*, c.name as club_name, c.category
        FROM assignments a
        JOIN clubs c ON a.club_id = c.id
        WHERE a.student_id = ?
    """, (student_id,)).fetchone()
    
    # 동아리별 1지망 지원자 수
    club_first_counts = {}
    for club in clubs:
        cnt = db.execute("SELECT COUNT(*) as cnt FROM preferences WHERE first_choice = ?", (club["id"],)).fetchone()["cnt"]
        club_first_counts[club["id"]] = cnt
    
    return render_template("student/main.html",
        clubs=clubs,
        preference=preference,
        assignment=assignment,
        club_first_counts=club_first_counts,
        survey_open=get_setting("survey_open") == "1",
        show_results=get_setting("show_results") == "1",
    )

@app.route("/student/submit", methods=["POST"])
@student_required
def student_submit():
    student_id = session["student_id"]
    
    if get_setting("survey_open") != "1":
        flash("현재 희망조사 기간이 아닙니다.", "error")
        return redirect(url_for("student_page"))
    
    first = request.form.get("first_choice")
    second = request.form.get("second_choice")
    third = request.form.get("third_choice")
    
    if not all([first, second, third]):
        flash("1, 2, 3지망을 모두 선택해주세요.", "error")
        return redirect(url_for("student_page"))
    
    if len({first, second, third}) < 3:
        flash("같은 동아리를 중복 선택할 수 없습니다.", "error")
        return redirect(url_for("student_page"))
    
    db = get_db()
    db.execute("DELETE FROM preferences WHERE student_id = ?", (student_id,))
    db.execute(
        "INSERT INTO preferences (student_id, first_choice, second_choice, third_choice) VALUES (?, ?, ?, ?)",
        (student_id, int(first), int(second), int(third))
    )
    db.commit()
    flash("희망조사가 제출되었습니다! 🎉", "success")
    return redirect(url_for("student_page"))

# ============================================
# API 엔드포인트 (AJAX용)
# ============================================
@app.route("/api/club-stats")
def api_club_stats():
    db = get_db()
    clubs = db.execute("SELECT * FROM clubs").fetchall()
    result = []
    for club in clubs:
        first = db.execute("SELECT COUNT(*) as cnt FROM preferences WHERE first_choice = ?", (club["id"],)).fetchone()["cnt"]
        result.append({"id": club["id"], "name": club["name"], "first_count": first, "max": club["max_capacity"]})
    return jsonify(result)

# ============================================
# 앱 실행
# ============================================
with app.app_context():
    init_db()
    insert_sample_data()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
