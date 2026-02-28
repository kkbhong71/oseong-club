# 🏫 오성중학교 동아리 편성 시스템

학생들이 핸드폰으로 희망 동아리를 선택하고, 교사가 PC에서 관리/배정하는 웹 시스템입니다.

## 📱 주요 기능

### 교사 (PC 관리자)
- 동아리 등록/수정/삭제
- 학생 명단 관리
- 실시간 희망조사 현황 모니터링
- 자동 배정 실행 (1→2→3지망 순차, 정원 초과 시 랜덤 추첨)
- 배정 결과 CSV 다운로드
- 결과 공개/비공개 설정

### 학생 (모바일)
- 학년/반/번호/이름으로 간편 로그인
- 1, 2, 3지망 동아리 선택 및 제출
- 중복 선택 방지
- 배정 결과 확인

---

## 🚀 Render.com 배포 방법

### 1단계: GitHub에 코드 업로드

```bash
# 새 저장소 생성 후
git init
git add .
git commit -m "오성중학교 동아리 편성 시스템"
git branch -M main
git remote add origin https://github.com/[사용자명]/oseong-club.git
git push -u origin main
```

### 2단계: Render.com에서 배포

1. **https://render.com** 접속 → 로그인
2. **New** → **Web Service** 클릭
3. GitHub 저장소 연결 → `oseong-club` 선택
4. 설정:
   - **Name**: `oseong-club-system`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
5. **Environment Variables** 추가:
   - `SECRET_KEY`: 아무 긴 문자열 (예: `my-secret-key-oseong-2026`)
   - `ADMIN_PASSWORD`: `oseong2026` (또는 원하는 비밀번호)
6. **Disk** 추가 (중요! 데이터 보존용):
   - **Name**: `club-data`
   - **Mount Path**: `/opt/render/project/src`
   - **Size**: `1 GB`
7. **Create Web Service** 클릭

### 3단계: 접속 확인

배포 완료 후 `https://oseong-club-system.onrender.com` 형태의 URL이 생성됩니다.

---

## 📋 운영 순서

```
1. 교사가 관리자 로그인 (비밀번호: oseong2026)
2. 동아리 목록 확인/수정
3. 학생 명단 확인/수정
4. 설정에서 "희망조사 접수" ON
5. 학생들에게 URL(QR코드) 배포
6. 학생들이 핸드폰으로 접속 → 로그인 → 1,2,3지망 선택
7. 제출 현황 모니터링 (희망조사 현황 메뉴)
8. 마감 시 "희망조사 접수" OFF
9. "배정 실행" 클릭 → 결과 확인
10. "결과 공개" ON → 학생들이 결과 확인
11. CSV 다운로드로 기록 보관
```

## 🔐 기본 계정 정보

- **관리자 비밀번호**: `oseong2026` (환경변수로 변경 가능)
- **학생 로그인**: 학년 + 반 + 번호 + 이름 (학생 명단에 등록된 정보)

## ⚙️ 로컬 실행 (테스트용)

```bash
pip install -r requirements.txt
python app.py
```

브라우저에서 `http://localhost:5000` 접속

## 📂 파일 구조

```
club-system/
├── app.py                  # Flask 메인 앱 (라우팅, DB, 알고리즘)
├── requirements.txt        # 의존성
├── render.yaml            # Render.com 배포 설정
├── README.md              # 이 파일
└── templates/
    ├── base.html          # 공통 레이아웃 (CSS 포함)
    ├── landing.html       # 메인 페이지
    ├── admin/
    │   ├── base_admin.html  # 관리자 공통 (사이드바)
    │   ├── login.html
    │   ├── dashboard.html
    │   ├── clubs.html
    │   ├── students.html
    │   ├── preferences.html
    │   ├── assign.html
    │   ├── results.html
    │   └── settings.html
    └── student/
        ├── login.html
        └── main.html
```
