# KakaoTalk AI Card News Agent Team (카카오톡 배포용 AI 카드뉴스 에이전트 팀)

인공지능 에이전트 협업 팀을 구축하여 최신 AI 기술 소식을 자동으로 수집(Research)하고, 보기 좋은 카드뉴스(1:1 비율) 형태로 제작(Create)하며, 카카오톡 배포용 규격으로 완성(Publish)하는 종합 자동화 프로젝트입니다.

이 프로젝트는 터미널 기반의 **Python CLI 자동화 스크립트**와 실시간 프리뷰 및 상세 편집이 가능한 **프리미엄 웹 대시보드** 두 가지 방식을 모두 지원합니다.

---

## 📂 프로젝트 구조 (Project Structure)

```text
kakao_cardnews_agent/
├── README.md               # 프로젝트 가이드라인 및 설명서
├── requirements.txt        # Python 필수 라이브러리 목록
├── agent_runner.py         # Python CLI 에이전트 구동기 (Pillow 기반 이미지 렌더링)
├── index.html              # 대시보드 메인 마크업
├── index.css               # 대시보드 CSS 스타일시트 (Glassmorphism & Neon theme)
└── app.js                  # 대시보드 에이전트 파이프라인 및 내보내기 JS 로직
```

---

## 💻 1. 웹 대시보드 구동 가이드 (Web Dashboard)

웹 대시보드는 세 에이전트의 작동 과정을 시각적으로 확인하고, 생성된 카드뉴스를 브라우저에서 직접 수정 및 다운로드할 수 있는 프리미엄 관리 도구입니다.

### 실행 방법
1. 프로젝트 폴더가 있는 위치에서 간단한 로컬 웹 서버를 구동합니다.
   ```bash
   python3 -m http.server 8000
   ```
2. 웹 브라우저를 열고 `http://localhost:8000`에 접속합니다.

### 주요 기능
- **에이전트 워크플로 시각화**: 가동 시 조사(Researcher) -> 제작(Creator) -> 배포(Publisher) 에이전트가 데이터와 신호를 주고받는 애니메이션을 확인할 수 있습니다.
- **실시간 카드 편집기**: 생성된 슬라이드 카드를 클릭하면 본문 내용, 제목, 글자 크기, 백그라운드 그라데이션Preset을 실시간으로 커스텀할 수 있습니다.
- **고해상도 다운로드 (html2canvas & JSZip)**: 모든 수정 완료 후 `카드뉴스 다운로드 (ZIP)` 버튼을 누르면 5장의 슬라이드를 `1600x1600px`의 고화질 이미지 패키지로 압축하여 자동 다운로드합니다.
- **카카오톡 실시간 프리뷰**: 스마트폰 목업 화면을 통해 카카오톡으로 전송했을 때 말풍선 이미지가 어떻게 배치되는지 미리 볼 수 있습니다.
- **Gemini API 연동**: 설정창에 Google Gemini API Key를 입력하면, 시뮬레이션 데이터를 넘어 구글 뉴스 실시간 파싱 결과를 Gemini가 직접 분석하여 실시간 카드뉴스를 완전 자동 제작합니다.

---

## 🐍 2. Python CLI 구동 가이드 (CLI Agent Runner)

서버 백그라운드 환경 등에서 카드뉴스 제작을 자동화하고 실제 이미지 파일로 출력하는 Python 스크립트입니다.

### 실행 방법
1. 필수 라이브러리를 설치합니다.
   ```bash
   pip3 install -r requirements.txt
   ```
2. (선택사항) 실시간 AI 요약을 원할 경우 동일 경로에 `.env` 파일을 생성하고 Gemini API 키를 저장합니다.
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   ```
3. 에이전트 스크립트를 실행합니다. (주간 카드뉴스를 원할 경우 인자로 `weekly` 전달)
   ```bash
   # 일간 카드뉴스 생성
   python3 agent_runner.py
   
   # 주간 카드뉴스 생성
   python3 agent_runner.py weekly
   ```
4. 실행 완료 시 `output/` 폴더 아래 5장의 카드뉴스 이미지(`slide_1.png` ~ `slide_5.png`) 및 카카오톡 배포용 스키마 JSON 파일(`kakao_payload.json`)이 자동 저장됩니다.
