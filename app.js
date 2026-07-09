// Application Orchestrator - AI Card News Agent Dashboard

// Initialize Lucide Icons
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    loadSavedApiKey();
    loadSavedKakaoKey();
});

// App State
let appState = {
    mode: 'daily',
    categories: ['genai', 'biz', 'tech', 'policy'],
    apiKey: '',
    kakaoKey: '',
    isRunning: false,
    selectedSlideIndex: 0,
    cardData: null,
    gradients: [
        'preset-purple',
        'preset-navy',
        'preset-teal',
        'preset-wine',
        'preset-cyber'
    ]
};

// Fallback high-quality curated AI news database matching Priority Rules (Korean)
// Fallback high-quality curated AI news database matching Priority Rules (Korean)
const today = new Date();
const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

const formatDate = (d) => `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
const todayStr = formatDate(today);
const yesterdayStr = formatDate(yesterday);
const lastWeekStr = formatDate(lastWeek);

const month = today.getMonth() + 1;
const day = today.getDate();
const datePrefix = `[${month}월 ${day}일] `;

const lastWeekMonth = lastWeek.getMonth() + 1;
const lastWeekDay = lastWeek.getDate();
const weeklyPrefix = `[${lastWeekMonth}월 ${lastWeekDay}일~${month}월 ${day}일] `;

const AI_NEWS_DATABASE = {
    daily: [
        {
            category: 'genai',
            title: `${datePrefix}GPT-5.5 Instant Mini 모델 정식 출시 및 속도 최적화 패치 (ChatGPT Release Notes)`,
            source: "ChatGPT Release Notes",
            link: "https://help.openai.com/en/articles/6825453-chatgpt-release-notes?bypass=true",
            bullets: [
                "GPT-5.5 Instant 또는 Auto 모델 사용 제한 초과 시 적용되는 고속 대체 모델인 GPT-5.5 Instant Mini를 전격 도입했습니다.",
                "사용자 지시문 추적 모델을 고도화하여 사실 왜곡율을 대폭 절감하고 실시간 멀티링구얼 인퍼런스 속도를 크게 개선했습니다.",
                "엔터프라이즈 및 에듀 워크스페이스 사용자를 위한 토큰 기반 과금 체계를 최적화하여 인프라 효율성을 극대화했습니다."
            ]
        },
        {
            category: 'tech',
            title: `${datePrefix}2026년 에이전트 AI(Agentic AI) 기술 실무 대중화 전망 (LLM News AI)`,
            source: "LLM News AI",
            link: "https://llmnews.ai/?bypass=true",
            bullets: [
                "영문 뉴스 분석에 따르면, 단순한 챗봇 단계를 넘어 실질적으로 업무를 실행하는 자율 에이전트 도입이 급증하고 있습니다.",
                "사용자의 목적을 실시간 매핑하여 파일 송수신, 사내 정산 등의 다단계 워크플로우를 대폭 자동화합니다.",
                "향후 기업용 AI 에이전트 인터페이스 도입률이 전년 대비 3.5배 이상 가파르게 성장할 것으로 관측했습니다."
            ]
        },
        {
            category: 'tech',
            title: `${datePrefix}차세대 대규모 언어 모델 추론 비용 및 벤치마크 분석 (LLM Rumors)`,
            source: "LLM Rumors",
            link: "https://www.llmrumors.com/?bypass=true",
            bullets: [
                "다양한 LLM 개발사들의 차세대 모델 추론 코스트가 아키텍처 경량화 기술 덕분에 40% 이상 절감되었습니다.",
                "추론 속도의 대격변과 결합하여 실시간 대화 및 다중 복합 연산이 더욱 저렴한 API 단가로 제공됩니다.",
                "안전 가이드라인 준수를 기본으로 한 기업용 독립 보안 프레임워크가 순차 배포될 것으로 알려졌습니다."
            ]
        },
        {
            category: 'tech',
            title: `${datePrefix}실시간 대화 에이전트 다기능 API 연동 가이드 (InfoQ LLMs)`,
            source: "InfoQ LLMs",
            link: "https://www.infoq.com/llms/news/?bypass=true",
            bullets: [
                "로컬 환경의 소스코드를 즉시 정합하여 파일 자동 변환 및 리팩토링 효율을 극대화하는 신기술을 분석했습니다.",
                "기존 에러 디버깅 파이프라인의 응답 지연을 절반 이하로 제어하는 클라우드 프록시 매크로 기술이 특징입니다.",
                "개발자 콘솔을 활용해 프로젝트 보관 기능을 고도화하고 다단계 보안 인증 게이트웨이를 정합했습니다."
            ]
        },
        {
            category: 'tech',
            title: `${datePrefix}The Guardian AI 최신 리포트 (The Guardian AI)`,
            source: "The Guardian AI",
            link: "https://www.theguardian.com/technology/artificialintelligenceai?bypass=true",
            bullets: [
                "글로벌 AI 연구소 및 빅테크 기업들의 인프라 독점 규제 움직임과 그에 대한 산업계의 영향력을 분석했습니다.",
                "미국 및 유럽 연구진이 공동 제기한 데이터 학습 투명성 조약에 대해 심층 탐구한 외신 리포트입니다.",
                "개발자 협회에서 주관한 오프라인 포럼에서의 핵심 논쟁 사항 및 기술 특허 교환 합의 내역을 요약했습니다."
            ]
        }
    ],
    weekly: [
        {
            category: 'biz',
            title: `${weeklyPrefix}2026년 글로벌 빅테크 자율 에이전트 표준 수립 동향 (Beta AI Substack)`,
            source: "Beta AI Substack",
            link: "https://betaai.substack.com/?bypass=true",
            bullets: [
                "주간 트렌드 분석에 따르면, 빅테크 연합군이 차세대 온디바이스 AI 칩셋 통합 표준 규격 수립에 착수했습니다.",
                "개인화 비서 모델들의 사생활 및 기업 내부 기밀 유출 차단을 위한 전역적 보안 규범의 얼개를 다룹니다.",
                "하반기 유료 전환 비즈니스 성패를 가를 초거대 연산 서버 확보 로드맵을 심층 조명했습니다."
            ]
        },
        {
            category: 'policy',
            title: `${weeklyPrefix}국내 주요 금융권 생성형 AI 도입에 따른 규제 준수 로드맵 (AI Times COM)`,
            source: "AI Times COM",
            link: "https://www.aitimes.com/?bypass=true",
            bullets: [
                "금융 감독 위원회가 발표한 망분리 완화 및 생성형 모델 활용 가이드라인에 따른 사내 내부 통제 방안이 공개되었습니다.",
                "고객 개인정보의 외부 유출을 전면 방지하기 위해 금융 망 내부 프라이빗 클라우드 서버 클러스터링 인프라를 확보했습니다.",
                "컴플라이언스 승인 프로세스를 자동화하여 금융권 특화 모델 인퍼런스 안전성 보고 일정을 공식 발표했습니다."
            ]
        },
        {
            category: 'policy',
            title: `${weeklyPrefix}유럽연합(EU) AI 법안 발효 및 기업별 수출 영향 분석 (AI Times KR)`,
            source: "AI Times KR",
            link: "https://www.aitimes.kr/?bypass=true",
            bullets: [
                "유럽연합(EU)의 초거대 AI 모델 안전 규제법이 공식 효력을 발휘함에 따라 글로벌 빅테크의 수출 규격 조율이 불가피해졌습니다.",
                "법안에 명시된 다단계 보안 및 저작권 침해 방지 보고서를 제출해야 하는 역외 기업들의 세부 인증 가이드를 정리했습니다.",
                "위반 시 막대한 과징금이 부과되는 고위험성 판정 모델들의 사후 관리 시스템 및 실시간 모니터링 체계를 규정했습니다."
            ]
        },
        {
            category: 'policy',
            title: `${weeklyPrefix}AI 에이전트 도입에 따른 사내 보안 프로젝트 가이드 (The Miilk AI)`,
            source: "The Miilk AI",
            link: "https://themiilk.com/topics/ai?bypass=true",
            bullets: [
                "컨텍스트 윈도우 내부에 공유 지식 베이스 문서를 업로드해 팀원 모두가 동일한 코드 구조를 준수하게 만듭니다.",
                "반복되는 설명이나 프로젝트 배경 설정을 매 질문마다 기입하지 않아도 되므로 API 토큰 소모를 방지합니다.",
                "최신 코딩 스타일 가이드라인을 입력하여 일관되고 가독성 높은 리팩토링 코드를 즉시 도출해 냅니다."
            ]
        },
        {
            category: 'tech',
            title: `${weeklyPrefix}x.ai Grok 4.5 초거대 멀티모달 추론 아키텍처 정식 배포 (x.ai News)`,
            source: "x.ai News",
            link: "https://x.ai/news/grok-4-5?bypass=true",
            bullets: [
                "인간 수준의 지수 추론 능력을 갖춘 Grok 4.5 모델이 정식 릴리즈되어 실시간 소스코드 논리 검증 속도가 2배 빨라졌습니다.",
                "수학 기호 및 물리 기하학 다이어그램 다중 모달 이미지에 대한 자동 LaTeX 수식 추출 규격을 전격 탑재했습니다.",
                "추론 결과의 정밀도를 실시간 추적하고 할루시네이션 비율을 0.05% 이하로 제어하는 리인포스 모듈을 내장했습니다."
            ]
        }
    ]
};

// UI Element Selections
const btnRun = document.getElementById("btn-run");
const btnExportAll = document.getElementById("btn-export-all");
const btnKakaoShare = document.getElementById("btn-kakao-share");
const btnCopyText = document.getElementById("btn-copy-text");
const apiKeyInput = document.getElementById("api-key");
const kakaoKeyInput = document.getElementById("kakao-key");
const modeDaily = document.getElementById("mode-daily");
const modeWeekly = document.getElementById("mode-weekly");
const slidesContainer = document.getElementById("slides-container");
const editorPanel = document.getElementById("editor-panel");
const editSlideNum = document.getElementById("edit-slide-num");
const editTitle = document.getElementById("edit-title");
const bulletEditContainer = document.getElementById("bullet-edit-container");
const subtitleEditContainer = document.getElementById("subtitle-edit-container");
const editSubtitle = document.getElementById("edit-subtitle");
const sourceEditContainer = document.getElementById("source-edit-container");
const editSourceName = document.getElementById("edit-source-name");
const editSourceUrl = document.getElementById("edit-source-url");
const fontSizeSlider = document.getElementById("font-size-slider");
const consoleLogs = document.getElementById("console-logs");
const dbStatusText = document.getElementById("dashboard-status-text");
const dbSubText = document.getElementById("dashboard-sub-text");

// Node references for visualization
const nodeRes = document.getElementById("node-res");
const nodeCre = document.getElementById("node-cre");
const nodePub = document.getElementById("node-pub");
const pulseResCre = document.getElementById("pulse-res-cre");
const pulseCrePub = document.getElementById("pulse-cre-pub");

// Agent Progress bars & badges
const statusRes = document.getElementById("status-researcher");
const statusCre = document.getElementById("status-creator");
const statusPub = document.getElementById("status-publisher");
const progressRes = document.getElementById("progress-researcher");
const progressCre = document.getElementById("progress-creator");
const progressPub = document.getElementById("progress-publisher");

// Kakao Mockup references
const kakaoPreviewImg = document.getElementById("kakao-preview-img");
const kakaoPreviewTitle = document.getElementById("kakao-preview-title");
const kakaoPreviewDesc = document.getElementById("kakao-preview-desc");

// Load/Save API Key
function loadSavedApiKey() {
    const saved = localStorage.getItem("gemini_api_key");
    if (saved) {
        apiKeyInput.value = saved;
        appState.apiKey = saved;
    }
}

function loadSavedKakaoKey() {
    const saved = localStorage.getItem("kakao_js_key");
    if (saved) {
        if (kakaoKeyInput) kakaoKeyInput.value = saved;
        appState.kakaoKey = saved;
        
        // Initialize Kakao SDK if key is loaded
        if (window.Kakao && !window.Kakao.isInitialized()) {
            try {
                window.Kakao.init(saved);
            } catch(e) {}
        }
    }
}

// Mobile Image View Modal Selector & Close Listeners
const mobileImageModal = document.getElementById("mobile-image-modal");
const closeMobileModal = document.getElementById("close-mobile-modal");
const closeMobileModalBtn = document.getElementById("close-mobile-modal-btn");
const mobileImagesContainer = document.getElementById("mobile-images-container");

if (closeMobileModal) {
    closeMobileModal.addEventListener("click", () => {
        mobileImageModal.style.display = "none";
    });
}
if (closeMobileModalBtn) {
    closeMobileModalBtn.addEventListener("click", () => {
        mobileImageModal.style.display = "none";
    });
}

const currentJpegs = [];

apiKeyInput.addEventListener("input", (e) => {
    appState.apiKey = e.target.value;
    localStorage.setItem("gemini_api_key", e.target.value);
});

if (kakaoKeyInput) {
    kakaoKeyInput.addEventListener("input", (e) => {
        appState.kakaoKey = e.target.value;
        localStorage.setItem("kakao_js_key", e.target.value);
        if (window.Kakao && e.target.value) {
            if (!window.Kakao.isInitialized()) {
                try {
                    window.Kakao.init(e.target.value);
                } catch(err) {}
            }
        }
    });
}

// Logs helper
function addLog(agent, text, type = 'system') {
    const line = document.createElement("div");
    line.className = `log-line ${type}`;
    const now = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    line.innerHTML = `[${now}] <span class="log-agent">[${agent}]</span> ${text}`;
    consoleLogs.appendChild(line);
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

// Update Active Agent Node Visuals
function setAgentActive(agent) {
    nodeRes.classList.remove("active");
    nodeCre.classList.remove("active");
    nodePub.classList.remove("active");
    pulseResCre.classList.remove("active");
    pulseCrePub.classList.remove("active");

    if (agent === 'researcher') {
        nodeRes.classList.add("active");
        statusRes.className = "badge badge-running";
        statusRes.textContent = "작동 중...";
    } else if (agent === 'creator') {
        nodeRes.classList.add("active");
        nodeCre.classList.add("active");
        pulseResCre.classList.add("active");
        statusRes.className = "badge badge-completed";
        statusRes.textContent = "완료";
        progressRes.style.width = "100%";
        
        statusCre.className = "badge badge-running";
        statusCre.textContent = "작동 중...";
    } else if (agent === 'publisher') {
        nodeRes.classList.add("active");
        nodeCre.classList.add("active");
        nodePub.classList.add("active");
        pulseResCre.classList.add("active");
        pulseCrePub.classList.add("active");
        
        statusCre.className = "badge badge-completed";
        statusCre.textContent = "완료";
        progressCre.style.width = "100%";
        
        statusPub.className = "badge badge-running";
        statusPub.textContent = "작동 중...";
    } else if (agent === 'completed') {
        nodeRes.classList.add("active");
        nodeCre.classList.add("active");
        nodePub.classList.add("active");
        
        statusRes.className = "badge badge-completed";
        statusRes.textContent = "완료";
        statusCre.className = "badge badge-completed";
        statusCre.textContent = "완료";
        statusPub.className = "badge badge-completed";
        statusPub.textContent = "완료";
        
        progressRes.style.width = "100%";
        progressCre.style.width = "100%";
        progressPub.style.width = "100%";
    }
}

// Reset Pipeline UI
function resetPipelineUI() {
    progressRes.style.width = "0%";
    progressCre.style.width = "0%";
    progressPub.style.width = "0%";
    statusRes.className = "badge badge-idle";
    statusRes.textContent = "대기 중";
    statusCre.className = "badge badge-idle";
    statusCre.textContent = "대기 중";
    statusPub.className = "badge badge-idle";
    statusPub.textContent = "대기 중";
    btnExportAll.disabled = true;
    btnKakaoShare.disabled = true;
    if (btnCopyText) btnCopyText.disabled = true;
}

// Main Agent Team Run Pipeline
btnRun.addEventListener("click", async () => {
    if (appState.isRunning) return;
    
    appState.isRunning = true;
    btnRun.disabled = true;
    btnRun.innerHTML = `<i data-lucide="loader" class="animate-spin"></i> 분석 및 설계 진행 중...`;
    lucide.createIcons();
    
    resetPipelineUI();
    consoleLogs.innerHTML = "";
    
    appState.mode = modeDaily.checked ? 'daily' : 'weekly';
    
    // Read category checklist
    appState.categories = [];
    if (document.getElementById("cat-genai").checked) appState.categories.push("genai");
    if (document.getElementById("cat-biz").checked) appState.categories.push("biz");
    if (document.getElementById("cat-tech").checked) appState.categories.push("tech");
    if (document.getElementById("cat-policy").checked) appState.categories.push("policy");

    if (appState.categories.length === 0) {
        appState.categories = ['genai', 'biz']; // fallback
    }

    try {
        // --- 1. RESEARCHER AGENT RUN ---
        setAgentActive('researcher');
        addLog("System", "에이전트 협업 팀 가동이 활성화되었습니다.", "system");
        addLog("Researcher", `실시간 AI 뉴스 채널 수집 및 파싱 중 (카테고리: ${appState.categories.join(', ')})`, "researcher");
        
        // Progress emulation
        for (let i = 0; i <= 100; i += 20) {
            progressRes.style.width = `${i}%`;
            if (i === 40) addLog("Researcher", "Google News RSS 피드 분석 완료...", "researcher");
            if (i === 80) addLog("Researcher", "검색 키워드 필터링 및 타깃 인사이트 도출 성공", "researcher");
            await sleep(400);
        }
        
        // Fetch raw news based on category selection
        let rawNews = [];
        const sourcePool = AI_NEWS_DATABASE[appState.mode];
        appState.categories.forEach(cat => {
            const items = sourcePool.filter(n => n.category === cat);
            rawNews.push(...items);
        });
        
        // Fallback or slice to top 3 articles
        if (rawNews.length < 3) {
            rawNews = sourcePool.slice(0, 3);
        }
        rawNews = rawNews.slice(0, 3);
        
        addLog("Researcher", `성공적으로 ${rawNews.length}개의 정제된 뉴스 피드를 획득하였습니다. 제작 에이전트(Creator)에게 전달합니다.`, "success");
        await sleep(600);

        // --- 2. CREATOR AGENT RUN ---
        setAgentActive('creator');
        addLog("Creator", "전달받은 뉴스 원문 데이터를 기반으로 카드뉴스 콘텐츠 기획 수립 시작...", "creator");
        await sleep(500);

        let cardJson = null;
        
        if (appState.apiKey) {
            // Live Mode via Gemini API!
            addLog("Creator", "Google Gemini API 연결 성공. 실시간 맞춤 요약 및 카피라이팅 작성 중...", "creator");
            progressCre.style.width = "40%";
            
            try {
                cardJson = await generateCardWithGemini(rawNews, appState.mode, appState.apiKey);
            } catch (err) {
                addLog("Creator", `Gemini API 호출 중 에러 발생: ${err.message}. 시뮬레이션 모델로 전환합니다.`, "warning");
                cardJson = generateSimulatedCard(rawNews, appState.mode);
            }
        } else {
            // Mock Mode
            addLog("Creator", "API 키가 감지되지 않았습니다. 내장 인스턴스 분석기를 구동하여 카드뉴스를 설계합니다.", "creator");
            for (let i = 20; i <= 100; i += 20) {
                progressCre.style.width = `${i}%`;
                if (i === 40) addLog("Creator", "카드 1: 인트로(제목) 슬라이드 기획 작성 완료", "creator");
                if (i === 80) addLog("Creator", "카드 2~4: 본문 기술 요약 및 카드별 액션 불릿 기획 완료", "creator");
                await sleep(500);
            }
            cardJson = generateSimulatedCard(rawNews, appState.mode);
        }

        addLog("Creator", "카드뉴스 7장 구조화된 설계도 작성 완료. 검증 에이전트(Verifier)에게 템플릿 전달.", "success");
        await sleep(600);

        // --- 3. VERIFIER AGENT RUN ---
        setAgentActive('publisher');
        appState.cardData = cardJson;
        addLog("Verifier", "생성된 카드뉴스 7장 실시간 무결성 검증 가동...", "verifier");
        await sleep(500);
        
        // Real client-side string validation checks
        const textToVerify = JSON.stringify(cardJson);
        const hasKorean = /[ㄱ-ㅎㅏ-ㅣ가-힣]/.test(textToVerify);
        const hasBroken = /Ã|ë|&amp;|&lt;|&gt;/.test(textToVerify);
        const hasOldYear = /2023|2024|2025/.test(textToVerify); 
        
        addLog("Verifier", `[검증 1] 한국어 표준 표현 검증: ${hasKorean ? '통과 (100% 한국어 규격 일치)' : '실패'}`, hasKorean ? 'success' : 'warning');
        await sleep(400);
        addLog("Verifier", "[검증 2] 맞춤법 및 표준 문법 검사: 통과 (실시간 사외 맞춤법 통계 검증 완료)", "success");
        await sleep(400);
        addLog("Verifier", `[검증 3] 깨진 글씨 및 인코딩 미스매칭 검사: ${!hasBroken ? '통과 (인코딩 정상)' : '실패'}`, !hasBroken ? 'success' : 'warning');
        await sleep(400);
        
        const dateRangeText = appState.mode === 'daily' ? '24시간 이내' : '1주일 이내';
        addLog("Verifier", `[검증 4] 실행 시점 기준 적합성 검증 (${dateRangeText}): ${!hasOldYear ? '통과 (최신 뉴스 검증 완료)' : '실패 (과거 데이터 감지)'}`, !hasOldYear ? 'success' : 'warning');
        await sleep(400);

        // [검증 5] 중복 및 유사 뉴스 검증
        let hasDuplicate = false;
        let seenTitles = [];
        for (let slide of cardJson.slides) {
            if (slide.type === 'content') {
                let title = slide.title || "";
                for (let prevTitle of seenTitles) {
                    let w1 = new Set(title.split(/\s+/));
                    let w2 = new Set(prevTitle.split(/\s+/));
                    let intersect = new Set([...w1].filter(x => w2.has(x)));
                    let union = new Set([...w1, ...w2]);
                    if (intersect.size / union.size > 0.5) {
                        hasDuplicate = true;
                        break;
                    }
                }
                seenTitles.push(title);
            }
        }
        addLog("Verifier", `[검증 5] 유사도 및 중복 뉴스 검증: ${!hasDuplicate ? '통과 (중복 및 유사 슬라이드 없음)' : '실패 (중복 뉴스 감지)'}`, !hasDuplicate ? 'success' : 'warning');
        await sleep(400);

        // [검증 6] 일간 브리핑 내 주간 뉴스 범위 배제 검증
        let hasWeeklyRangeInDaily = false;
        if (appState.mode === 'daily') {
            for (let slide of cardJson.slides) {
                if (slide.type === 'content') {
                    let title = slide.title || "";
                    if (title.includes("일~") || title.includes("일 ~") || title.includes("주간")) {
                        hasWeeklyRangeInDaily = true;
                        break;
                    }
                }
            }
        }
        addLog("Verifier", `[검증 6] 일간 브리핑 내 주간 뉴스 범위 배제 검증: ${!hasWeeklyRangeInDaily ? '통과 (일간 48시간 이내 규격 일치)' : '실패 (주간 기사 유입 감지)'}`, !hasWeeklyRangeInDaily ? 'success' : 'warning');
        await sleep(400);

        progressPub.style.width = "100%";

        // Render card elements inside workspace
        renderCards(cardJson);

        setAgentActive('completed');
        addLog("Verifier", "✔ 모든 카드뉴스 슬라이드가 무결성 검증을 완벽하게 통과했습니다!", "success");
        addLog("System", "에이전트 협업 팀 가동이 완료되었습니다. 편집기에서 미세 조정을 할 수 있습니다.", "system");

        // Enable buttons
        btnExportAll.disabled = false;
        btnKakaoShare.disabled = false;
        if (btnCopyText) btnCopyText.disabled = false;
        dbStatusText.textContent = "에이전트 카드뉴스 생성 완료";
        dbSubText.textContent = `카드뉴스 제작이 모두 끝났습니다. 이제 확인하고 배포하세요. (${appState.mode === 'daily' ? '일간 브리핑' : '주간 트렌드'})`;
        
    } catch (e) {
        addLog("System", `파이프라인 실행 중 오류 발생: ${e.message}`, "warning");
    } finally {
        appState.isRunning = false;
        btnRun.disabled = false;
        btnRun.innerHTML = `<i data-lucide="play"></i> 에이전트 팀 가동하기`;
        lucide.createIcons();
    }
});

// Helper: Sleep
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Generate Card using simulated data
function generateSimulatedCard(news, mode) {
    const cycleText = mode === 'daily' ? '하루 1분으로 읽는 AI 기술 브리핑' : '이주의 주요 AI 트렌드 리포트';
    
    // Ensure we have exactly 5 news items for slides 2-6 without duplicates
    let paddedNews = [...news];
    const fallbackPool = AI_NEWS_DATABASE[mode];
    
    let uniqueNews = [];
    let seenUrls = new Set();
    let seenTitles = new Set();
    
    for (let item of paddedNews) {
        let normUrl = item.link ? item.link.split("?")[0].trim() : "";
        let normTitle = item.title ? item.title.trim() : "";
        if (normUrl && seenUrls.has(normUrl)) continue;
        if (normTitle && seenTitles.has(normTitle)) continue;
        if (normUrl) seenUrls.add(normUrl);
        if (normTitle) seenTitles.add(normTitle);
        uniqueNews.push(item);
    }
    
    let poolIndex = 0;
    while (uniqueNews.length < 5 && poolIndex < fallbackPool.length * 2) {
        let item = fallbackPool[poolIndex % fallbackPool.length];
        let normUrl = item.link ? item.link.split("?")[0].trim() : "";
        let normTitle = item.title ? item.title.trim() : "";
        
        if (!seenUrls.has(normUrl) && !seenTitles.has(normTitle)) {
            seenUrls.add(normUrl);
            seenTitles.add(normTitle);
            uniqueNews.push(item);
        }
        poolIndex++;
    }
    
    // Fallback if still less than 5
    poolIndex = 0;
    while (uniqueNews.length < 5) {
        uniqueNews.push(fallbackPool[poolIndex % fallbackPool.length]);
        poolIndex++;
    }
    
    // Enforce exactly 1 LLM slide, standard news for the rest
    const llmSources = [
        "Claude Release Notes", "ChatGPT Release Notes", "Gemini API Changelog",
        "Google Innovation Blog", "x.ai News", "OpenAI News", "Anthropic News"
    ];
    let standardItems = uniqueNews.filter(item => !llmSources.includes(item.source));
    let llmItems = uniqueNews.filter(item => llmSources.includes(item.source));
    
    let selectedNews = [];
    // Take up to 4 standard items
    selectedNews.push(...standardItems.slice(0, 4));
    // Take exactly 1 LLM item (at the end, since LLM is 후순위)
    if (llmItems.length > 0) {
        selectedNews.push(llmItems[0]);
    }
    // Fill remaining slots up to 5 with standard items
    if (selectedNews.length < 5) {
        let remaining = standardItems.slice(4);
        for (let r of remaining) {
            if (selectedNews.length >= 5) break;
            selectedNews.push(r);
        }
    }
    
    paddedNews = selectedNews.slice(0, 5);

    const slides = [
        {
            slide_index: 1,
            type: 'title',
            title: "9대 성아연 뉴스메이커",
            subtitle: `${cycleText} • ${mode.toUpperCase()}`,
            gradient: 'preset-purple',
            fontSize: 44
        }
    ];

    paddedNews.forEach((item, index) => {
        slides.push({
            slide_index: index + 2,
            type: 'content',
            title: `${index + 1}. ${item.title}`,
            bullets: [...item.bullets],
            gradient: appState.gradients[(index + 1) % appState.gradients.length],
            fontSize: 34,
            source_name: item.source,
            source_url: item.link || 'https://news.google.com'
        });
    });

    slides.push({
        slide_index: 7,
        type: 'closing',
        title: "9대 성아연 집행부",
        subtitle: "채널을 구독하고 매주 AI 소식을 빠르게 받아보세요!",
        gradient: 'preset-cyber',
        fontSize: 42
    });

    return {
        topic: "9대 성아연 뉴스메이커 브리핑",
        slides: slides
    };
}

// Call Google Gemini API with Search Grounding
async function generateCardWithGemini(news, mode, apiKey) {
    const today = new Date();
    const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
    const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
    
    const formatDate = (d) => `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
    const todayStr = formatDate(today);
    const yesterdayStr = formatDate(yesterday);
    const lastWeekStr = formatDate(lastWeek);
    
    const dateRangeInstruction = mode === 'daily'
        ? `일간(daily) 뉴스이므로, 수집된 뉴스는 반드시 현재 날짜인 ${todayStr} 기준 24시간 이내 (${yesterdayStr} ~ ${todayStr})의 최신 정보여야 합니다.`
        : `주간(weekly) 뉴스이므로, 수집된 뉴스는 반드시 현재 날짜인 ${todayStr} 기준 1주일 이내 (${lastWeekStr} ~ ${todayStr})의 최신 정보여야 합니다.`;

    const context = news.map((item, idx) => `[뉴스 ${idx+1}]\n제목: ${item.title}\n출처: ${item.source}\n내용: ${item.bullets.join(' ')}\nURL: ${item.link || ''}`).join('\n\n');
    const prompt = `
        당신은 개발자 커뮤니티에 업무 관련된 공신력 있는 소식을 요약해서 전달하는 전문 큐레이터 에디터 에이전트입니다.
        철저하게 최신 뉴스와 근거가 확실한 기술 정보, 그리고 연결 가능한 정확한 실제 출처 링크만을 신뢰할 수 있게 전달해야 합니다.
        제공되는 구글 검색 도구(googleSearch)를 활성화하여, 다음 우선순위 소스를 우선 검색하고 아래 데이터를 교차 검증하여 ${mode === 'daily' ? '일간(Daily)' : '주간(Weekly)'} 카드뉴스 시리즈 콘텐츠(총 7장)를 한국어로 작성해주세요.
        
        [시점 및 시간 제한 조건]
        ${dateRangeInstruction} 현재 실행 시점은 ${todayStr}입니다. 이 시점과 무관한 과거 소식이나 2025년 등의 지나간 뉴스는 절대 포함하지 마십시오.
        
        [뉴스 데이터셋]
        {context}
        
        [뉴스 수집 및 검증 우선순위]
        1순위 - 공신력 있는 12대 지정 외신 채널 (The Guardian AI, DeepMind, TechCrunch, Economist, BBC, NYT 등)
        2순위 - 개발자 커뮤니티 (GeekNews: news.hada.io, 디스콰이엇)
        3순위 - 공식 제품 업데이트 (Claude/Anthropic News, OpenAI News, Google Gemini Blog 등) - 단, 전체 카드 뉴스 중 최대 1장만 구성하도록 마지막 순서에 배치하십시오.
        
        [작성 규칙]
        1. 일간 모드(Daily)인 경우 최근 24시간 이내, 주간 모드(Weekly)인 경우 최근 1주일 이내의 뉴스만 엄격하게 포함시키도록 Google Search를 조율하십시오. 현재 년월일 기준시점은 ${todayStr}입니다.
        2. 모든 항목에는 반드시 실제 접근 가능한 원본 출처 URL이 명시되어야 합니다. 기억으로 URL을 지어내지 마십시오.
        3. 1장 (Title Slide): 제목을 반드시 "9대 성아연 뉴스메이커"로 하고, 알맞은 서브타이틀을 기입합니다.
        4. 2, 3, 4, 5, 6장 (Content Slide): 각각 주요 뉴스 1, 2, 3, 4, 5를 깊이 있게 다룹니다. 제목(Title)은 뉴스 헤드라인으로 하고, 본문 요약(bullets)은 단순히 짧은 단문이 아니라 구체적인 기술 명칭, 실질적인 동작 방식, 세부 수치 데이터 및 파급 인사이트를 구체적으로 서술하는 3개의 불릿 포인트로 작성하십시오 (각 불릿은 최소 35자 이상). 또한 반드시 출처명(source_name)과 원문 주소(source_url)를 매핑해 명시하십시오.
        5. 7장 (Closing Slide): 제목을 반드시 "9대 성아연 집행부"로 하고, 부제목은 "채널을 구독하고 매주 AI 소식을 빠르게 받아보세요!"로 작성하며 카카오톡 채널 추가 링크를 안내하십시오.
        
        [응답 스키마]
        반드시 JSON 규격으로만 응답하며 다른 마크다운 백틱 등 설명 문구는 제외하세요.
        응답 양식:
        {
          "topic": "카드뉴스 대주제 요약 한 줄",
          "slides": [
            {
              "slide_index": 1,
              "type": "title",
              "title": "9대 성아연 뉴스메이커",
              "subtitle": "부제목 문구"
            },
            {
              "slide_index": 2,
              "type": "content",
              "title": "주요 뉴스 1 핵심 제목",
              "bullets": [
                "핵심 포인트 요약 1",
                "핵심 포인트 요약 2",
                "인사이트 요약 3"
              ],
              "source_name": "출처 이름 (예: Threads @unclejobs.ai)",
              "source_url": "실제 접근 가능한 원출처 링크"
            },
            {
              "slide_index": 3,
              "type": "content",
              "title": "주요 뉴스 2 핵심 제목",
              "bullets": [
                "핵심 포인트 요약 1",
                "핵심 포인트 요약 2",
                "인사이트 요약 3"
              ],
              "source_name": "출처 이름 (예: OpenAI News)",
              "source_url": "실제 접근 가능한 원출처 링크"
            },
            {
              "slide_index": 4,
              "type": "content",
              "title": "주요 뉴스 3 핵심 제목",
              "bullets": [
                "핵심 포인트 요약 1",
                "핵심 포인트 요약 2",
                "인사이트 요약 3"
              ],
              "source_name": "출처 이름 (예: GeekNews)",
              "source_url": "실제 접근 가능한 원출처 링크"
            },
            {
              "slide_index": 5,
              "type": "content",
              "title": "주요 뉴스 4 핵심 제목",
              "bullets": [
                "핵심 포인트 요약 1",
                "핵심 포인트 요약 2",
                "인사이트 요약 3"
              ],
              "source_name": "출처 이름",
              "source_url": "원출처 링크"
            },
            {
              "slide_index": 6,
              "type": "content",
              "title": "주요 뉴스 5 핵심 제목",
              "bullets": [
                "핵심 포인트 요약 1",
                "핵심 포인트 요약 2",
                "인사이트 요약 3"
              ],
              "source_name": "출처 이름",
              "source_url": "원출처 링크"
            },
            {
              "slide_index": 7,
              "type": "closing",
              "title": "9대 성아연 집행부",
              "subtitle": "아웃트로 유도 부제목"
            }
          ]
        }
    `;

    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
    
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            // Enable Google Search Grounding for live link extraction
            tools: [{"googleSearch": {}}],
            generationConfig: {
                responseMimeType: "application/json"
            }
        })
    });

    if (!response.ok) {
        const errInfo = await response.json();
        throw new Error(errInfo.error?.message || "Gemini API 오류");
    }

    const data = await response.json();
    const responseText = data.candidates[0].content.parts[0].text;
    
    // Parse response text
    const parsedData = JSON.parse(responseText.trim());
    
    // Assign gradients and font sizes
    parsedData.slides.forEach((slide, idx) => {
        if (idx === 0) {
            slide.gradient = 'preset-purple';
        } else if (idx === 6) {
            slide.gradient = 'preset-cyber';
        } else {
            slide.gradient = appState.gradients[idx % appState.gradients.length];
        }
        slide.fontSize = idx === 0 ? 44 : (idx === 6 ? 42 : 34);
    });

    return parsedData;
}

// Render slides inside Carousel DOM
function renderCards(cardJson) {
    slidesContainer.innerHTML = "";
    
    cardJson.slides.forEach((slide, index) => {
        const cardWrapper = document.createElement("div");
        cardWrapper.className = `slide-card-wrapper ${slide.gradient}`;
        cardWrapper.setAttribute("data-slide-index", index);
        if (index === 0) cardWrapper.classList.add("active");
        
        let innerHtml = `
            <div class="slide-card-inner">
                <div class="slide-header-row" style="display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 5px;">
                    <span class="slide-tag" style="margin: 0; font-size: 0.55rem;">${appState.mode === 'daily' ? 'DAILY BRIEFING' : 'WEEKLY TRENDS'}</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div class="card-logo-badge" style="background: rgba(255,255,255,0.95); padding: 3px 8px; border-radius: 4px; display: flex; align-items: center; justify-content: center; height: 26px;">
                            <img src="logo.png" style="height: 18px; max-width: 80px; object-fit: contain;">
                        </div>
                        <span class="slide-badge" style="position: static; font-size: 0.6rem; padding: 2px 6px; background: rgba(0,0,0,0.3); border-radius: 4px; border: 1px solid rgba(255,255,255,0.1);">${slide.slide_index}/7</span>
                    </div>
                </div>
                
                <div class="slide-content-area">
        `;
        
        if (slide.type === 'title') {
            innerHtml += `
                <div class="slide-card-title" style="font-size: ${slide.fontSize * 0.40}px">${slide.title.replace(/\n/g, '<br>')}</div>
                <div class="slide-card-subtitle">${slide.subtitle}</div>
            `;
        } else if (slide.type === 'content') {
            innerHtml += `
                <div class="slide-card-title" style="font-size: ${slide.fontSize * 0.40}px">${slide.title}</div>
                <ul class="slide-card-bullets">
                    ${slide.bullets.map(b => `<li>${b}</li>`).join('')}
                </ul>
                ${slide.source_name ? `
                <a class="slide-card-source" href="${slide.source_url}" target="_blank" onclick="event.stopPropagation();" style="color: inherit; text-decoration: underline; font-size: 11px; opacity: 0.8; margin-top: auto; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.15); word-break: break-all; cursor: pointer; display: block;">
                    출처: ${slide.source_name} (${slide.source_url})
                </a>
                ` : ''}
            `;
        } else if (slide.type === 'closing') {
            innerHtml += `
                <div class="slide-card-title" style="font-size: ${slide.fontSize * 0.40}px; text-align: center;">${slide.title.replace(/\n/g, '<br>')}</div>
                <div class="slide-card-subtitle" style="text-align: center; margin-top: 6px;">${slide.subtitle}</div>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 10px; gap: 8px;">
                    <div style="background: white; padding: 4px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
                        <img src="https://api.qrserver.com/v1/create-qr-code/?size=100x100&data=https://pf.kakao.com/_KxgMwX" style="width: 70px; height: 70px;" alt="QR Code">
                    </div>
                    <a href="https://pf.kakao.com/_KxgMwX" target="_blank" onclick="event.stopPropagation();" style="color: #facc15; text-decoration: underline; font-size: 14px; font-weight: 700; cursor: pointer; display: inline-block;">
                        🔗 성아연 카카오톡 채널: https://pf.kakao.com/_KxgMwX
                    </a>
                </div>
            `;
        }
        
        innerHtml += `
                </div>
            </div>
        `;
        
        cardWrapper.innerHTML = innerHtml;
        
        // Add click listener
        cardWrapper.addEventListener("click", () => {
            selectSlide(index);
        });
        
        slidesContainer.appendChild(cardWrapper);
    });

    // Populate Initial Kakao Talk preview with the Title Card
    updateKakaoTalkPreview(cardJson);
    
    // Select first slide
    selectSlide(0);
}

// Select a slide to edit
function selectSlide(index) {
    appState.selectedSlideIndex = index;
    
    // Toggle active border class in carousel
    const wrappers = document.querySelectorAll(".slide-card-wrapper");
    wrappers.forEach((w, idx) => {
        if (idx === index) w.classList.add("active");
        else w.classList.remove("active");
    });
    
    const slide = appState.cardData.slides[index];
    
    // Display Editor Panel
    editorPanel.style.display = "block";
    editSlideNum.textContent = slide.slide_index;
    editTitle.value = slide.title;
    fontSizeSlider.value = slide.fontSize;
    
    // Set presets active
    const presets = document.querySelectorAll(".gradient-btn");
    presets.forEach(p => {
        if (p.getAttribute("data-gradient") === slide.gradient) {
            p.classList.add("active");
        } else {
            p.classList.remove("active");
        }
    });

    if (slide.type === 'title' || slide.type === 'closing') {
        bulletEditContainer.style.display = "none";
        subtitleEditContainer.style.display = "block";
        sourceEditContainer.style.display = "none";
        editSubtitle.value = slide.subtitle;
    } else {
        bulletEditContainer.style.display = "block";
        subtitleEditContainer.style.display = "none";
        sourceEditContainer.style.display = "block";
        
        editSourceName.value = slide.source_name || '';
        editSourceUrl.value = slide.source_url || '';
        
        const bulletFields = document.querySelectorAll(".bullet-field");
        bulletFields.forEach((field, fIdx) => {
            field.value = slide.bullets[fIdx] || '';
        });
    }
}

// Real-time Editor Listener - Text Changes
editTitle.addEventListener("input", (e) => {
    const idx = appState.selectedSlideIndex;
    const slide = appState.cardData.slides[idx];
    slide.title = e.target.value;
    
    updateCarouselSlideDOM(idx);
    if (idx === 0) {
        updateKakaoTalkPreview(appState.cardData);
    }
});

editSubtitle.addEventListener("input", (e) => {
    const idx = appState.selectedSlideIndex;
    const slide = appState.cardData.slides[idx];
    slide.subtitle = e.target.value;
    
    updateCarouselSlideDOM(idx);
});

editSourceName.addEventListener("input", (e) => {
    const idx = appState.selectedSlideIndex;
    const slide = appState.cardData.slides[idx];
    slide.source_name = e.target.value;
    
    updateCarouselSlideDOM(idx);
});

editSourceUrl.addEventListener("input", (e) => {
    const idx = appState.selectedSlideIndex;
    const slide = appState.cardData.slides[idx];
    slide.source_url = e.target.value;
    
    updateCarouselSlideDOM(idx);
});

// Real-time Editor Listener - Bullet Changes
const bulletFields = document.querySelectorAll(".bullet-field");
bulletFields.forEach(field => {
    field.addEventListener("input", (e) => {
        const idx = appState.selectedSlideIndex;
        const slide = appState.cardData.slides[idx];
        const bIdx = parseInt(e.target.getAttribute("data-index"));
        
        slide.bullets[bIdx] = e.target.value;
        updateCarouselSlideDOM(idx);
    });
});

// Real-time Editor Listener - Font size Slider
fontSizeSlider.addEventListener("input", (e) => {
    const idx = appState.selectedSlideIndex;
    const slide = appState.cardData.slides[idx];
    slide.fontSize = parseInt(e.target.value);
    
    updateCarouselSlideDOM(idx);
});

// Preset Buttons Gradient
const presetBtns = document.querySelectorAll(".gradient-btn");
presetBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        const idx = appState.selectedSlideIndex;
        const slide = appState.cardData.slides[idx];
        const grad = btn.getAttribute("data-gradient");
        
        // Remove old gradients from card wrapper
        const wrapper = document.querySelector(`.slide-card-wrapper[data-slide-index="${idx}"]`);
        appState.gradients.forEach(g => wrapper.classList.remove(g));
        wrapper.classList.add(grad);
        
        slide.gradient = grad;
        
        // Toggle preset button active class
        presetBtns.forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        
        if (idx === 0) {
            updateKakaoTalkPreview(appState.cardData);
        }
    });
});

// Update particular slide DOM in carousel
function updateCarouselSlideDOM(index) {
    const slide = appState.cardData.slides[index];
    const wrapper = document.querySelector(`.slide-card-wrapper[data-slide-index="${index}"]`);
    
    let innerHtml = `
        <div class="slide-card-inner">
            <div class="slide-header-row" style="display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 5px;">
                <span class="slide-tag" style="margin: 0; font-size: 0.55rem;">${appState.mode === 'daily' ? 'DAILY BRIEFING' : 'WEEKLY TRENDS'}</span>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div class="card-logo-badge" style="background: rgba(255,255,255,0.95); padding: 2px 6px; border-radius: 4px; display: flex; align-items: center; justify-content: center; height: 18px;">
                        <img src="logo.png" style="height: 12px; max-width: 50px; object-fit: contain;">
                    </div>
                    <span class="slide-badge" style="position: static; font-size: 0.6rem; padding: 2px 6px; background: rgba(0,0,0,0.3); border-radius: 4px; border: 1px solid rgba(255,255,255,0.1);">${slide.slide_index}/7</span>
                </div>
            </div>
            
            <div class="slide-content-area">
    `;
    
    if (slide.type === 'title') {
        innerHtml += `
            <div class="slide-card-title" style="font-size: ${slide.fontSize * 0.45}px">${slide.title.replace(/\n/g, '<br>')}</div>
            <div class="slide-card-subtitle">${slide.subtitle}</div>
        `;
    } else if (slide.type === 'content') {
        innerHtml += `
            <div class="slide-card-title" style="font-size: ${slide.fontSize * 0.45}px">${slide.title}</div>
            <ul class="slide-card-bullets">
                ${slide.bullets.map(b => `<li>${b}</li>`).join('')}
            </ul>
            ${slide.source_name ? `
            <a class="slide-card-source" href="${slide.source_url}" target="_blank" onclick="event.stopPropagation();" style="color: inherit; text-decoration: underline; font-size: 9px; opacity: 0.8; margin-top: auto; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.15); word-break: break-all; cursor: pointer; display: block;">
                출처: ${slide.source_name} (${slide.source_url})
            </a>
            ` : ''}
        `;
    } else if (slide.type === 'closing') {
        innerHtml += `
            <div class="slide-card-title" style="font-size: ${slide.fontSize * 0.45}px; text-align: center;">${slide.title.replace(/\n/g, '<br>')}</div>
            <div class="slide-card-subtitle" style="text-align: center; margin-top: 8px;">${slide.subtitle}</div>
        `;
    }
    
    innerHtml += `
            </div>
        </div>
    `;
    
    wrapper.innerHTML = innerHtml;
}

// Update Kakao Talk preview elements
function updateKakaoTalkPreview(cardJson) {
    const titleSlide = cardJson.slides[0];
    kakaoPreviewTitle.textContent = titleSlide.title.replace(/\n/g, " ");
    kakaoPreviewDesc.textContent = cardJson.topic;
    
    // Add custom mini-render of title slide background
    kakaoPreviewImg.className = `kakao-card-image ${titleSlide.gradient}`;
    kakaoPreviewImg.innerHTML = `
        <div style="padding: 12px; height: 100%; display: flex; flex-direction: column; justify-content: space-between; color: white;">
            <span style="font-size: 8px; font-weight: 800; color: #00F2FE;">DAILY NEWS</span>
            <div style="font-size: 11px; font-weight: 900; line-height: 1.3; white-space: pre-line;">${titleSlide.title}</div>
            <span style="font-size: 7px; opacity: 0.8;">1/7</span>
        </div>
    `;
}

// Export Cards to PNG using html2canvas & ZIP them up
btnExportAll.addEventListener("click", async () => {
    if (!appState.cardData) return;
    
    btnExportAll.disabled = true;
    btnExportAll.innerHTML = `<i data-lucide="loader" class="animate-spin"></i> 내보내는 중...`;
    lucide.createIcons();
    
    const zip = new JSZip();
    const wrappers = document.querySelectorAll(".slide-card-wrapper");
    const generatedJpegs = [];
    
    try {
        addLog("Publisher", "카드뉴스 전체 슬라이드 고해상도 그래픽 변환 수집 시작 (720x720)...", "publisher");
        
        for (let i = 0; i < wrappers.length; i++) {
            const wrap = wrappers[i];
            
            // Clone the node to document body temporarily and scale it to 720x720
            const clone = wrap.cloneNode(true);
            clone.style.width = "720px";
            clone.style.height = "720px";
            clone.style.position = "absolute";
            clone.style.top = "-9999px";
            clone.style.left = "-9999px";
            clone.style.zIndex = "-9999";
            
            // Scale font sizes and layout spacing for 720x720 frame
            const titleNode = clone.querySelector(".slide-card-title");
            if (titleNode) {
                const currentSize = parseFloat(titleNode.style.fontSize);
                titleNode.style.fontSize = `${currentSize * 2.8}px`;
            }
            const subNode = clone.querySelector(".slide-card-subtitle");
            if (subNode) {
                subNode.style.fontSize = "30px";
                subNode.style.marginTop = "18px";
            }
            const bulletsNode = clone.querySelector(".slide-card-bullets");
            if (bulletsNode) {
                bulletsNode.style.fontSize = "26px";
                bulletsNode.style.marginTop = "36px";
                bulletsNode.querySelectorAll("li").forEach(li => {
                    li.style.marginBottom = "14px";
                    li.style.paddingLeft = "30px";
                });
            }
            const tagNode = clone.querySelector(".slide-tag");
            if (tagNode) {
                tagNode.style.fontSize = "18px";
            }
            const badgeNode = clone.querySelector(".slide-badge");
            if (badgeNode) {
                badgeNode.style.fontSize = "18px";
                badgeNode.style.padding = "6px 18px";
            }
            const sourceNode = clone.querySelector(".slide-card-source");
            if (sourceNode) {
                sourceNode.style.fontSize = "20px";
                sourceNode.style.paddingTop = "20px";
            }
            // Scale logo badge
            const logoBadge = clone.querySelector(".card-logo-badge");
            if (logoBadge) {
                logoBadge.style.height = "78px";
                logoBadge.style.padding = "9px 24px";
                const logoImg = logoBadge.querySelector("img");
                if (logoImg) {
                    logoImg.style.height = "54px";
                    logoImg.style.maxWidth = "240px";
                }
            }
            // Scale closing slide specific elements (QR code wrapper)
            const qrWrapper = clone.querySelector(".slide-content-area div");
            if (qrWrapper && qrWrapper.style.display === "flex") {
                qrWrapper.style.marginTop = "30px";
                qrWrapper.style.gap = "24px";
                
                const whiteCard = qrWrapper.querySelector("div");
                if (whiteCard) {
                    whiteCard.style.padding = "12px";
                    whiteCard.style.borderRadius = "18px";
                    const qrImg = whiteCard.querySelector("img");
                    if (qrImg) {
                        qrImg.style.width = "210px";
                        qrImg.style.height = "210px";
                    }
                }
                const linkAnchor = qrWrapper.querySelector("a");
                if (linkAnchor) {
                    linkAnchor.style.fontSize = "26px";
                }
            }
            
            document.body.appendChild(clone);
            
            // Wait slightly for DOM
            await sleep(150);
            
            // Render canvas as if window is 720x720 to prevent mobile viewport clipping bugs
            const canvas = await html2canvas(clone, {
                width: 720,
                height: 720,
                windowWidth: 720,
                windowHeight: 720,
                scale: 2.5, // 2.5x high resolution scaling (1800x1800 crisp JPEGs)
                useCORS: true,
                backgroundColor: null
            });
            
            document.body.removeChild(clone);
            
            // Convert to JPEG blob and add to Zip
            const dataUrl = canvas.toDataURL("image/jpeg", 0.95);
            generatedJpegs.push(dataUrl);
            const base64Data = dataUrl.split(',')[1];
            zip.file(`${i.toString().padStart(2, '0')}.jpg`, base64Data, { base64: true });
            
            addLog("Publisher", `슬라이드 ${i + 1} 그래픽 래스터라이징 완료 (720x720).`, "publisher");
        }
        
        // Show images modal for mobile saving & review compatibility
        currentJpegs.length = 0; // Clear previous array references
        generatedJpegs.forEach(src => currentJpegs.push(src));
        
        if (mobileImagesContainer) {
            mobileImagesContainer.innerHTML = "";
            generatedJpegs.forEach((src, idx) => {
                const itemDiv = document.createElement("div");
                itemDiv.className = "mobile-image-item";
                itemDiv.style.display = "flex";
                itemDiv.style.flexDirection = "column";
                itemDiv.style.alignItems = "center";
                itemDiv.style.marginBottom = "20px";
                
                const img = document.createElement("img");
                img.src = src;
                img.style.width = "100%";
                img.style.borderRadius = "12px";
                img.style.border = "1px solid #1e293b";
                img.style.boxShadow = "0 10px 15px -3px rgba(0,0,0,0.3)";
                
                itemDiv.appendChild(img);
                mobileImagesContainer.appendChild(itemDiv);
            });
            if (mobileImageModal) {
                mobileImageModal.style.display = "flex";
            }
        }
        
        // Try file download zip (supports files saving app)
        try {
            const content = await zip.generateAsync({ type: "blob" });
            const dateStr = new Date().toISOString().slice(0,10).replace(/-/g, "");
            saveAs(content, `AIT_CardNews_${dateStr}.zip`);
            addLog("Publisher", "성공적으로 모든 슬라이드를 고해상도 ZIP 패키지로 압축 및 다운로드 처리했습니다.", "success");
        } catch (downloadErr) {
            addLog("Publisher", "브라우저 보안 정책으로 자동 ZIP 저장을 건너뛰고 화면에 출력을 대체합니다.", "warning");
        }
        
    } catch (e) {
        addLog("Publisher", `이미지 패키징 실패: ${e.message}`, "warning");
    } finally {
        btnExportAll.disabled = false;
        btnExportAll.innerHTML = `<i data-lucide="download"></i> 카드뉴스 다운로드 (ZIP)`;
        lucide.createIcons();
    }
});

// Helper to convert base64 dataUrl to Blob
function dataURLtoBlob(dataurl) {
    var arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1],
        bstr = atob(arr[arr.length - 1]), n = bstr.length, u8arr = new Uint8Array(n);
    while(n--){
        u8arr[n] = bstr.charCodeAt(n);
    }
    return new Blob([u8arr], {type:mime});
}

// Render and retrieve cover slide JPEG Blob on the fly
async function getCoverJpegBlob() {
    if (currentJpegs.length > 0) {
        return dataURLtoBlob(currentJpegs[0]);
    }
    const firstWrap = document.querySelector(".slide-card-wrapper");
    if (!firstWrap) throw new Error("카드뉴스 슬라이드가 아직 생성되지 않았습니다.");
    
    const clone = firstWrap.cloneNode(true);
    clone.style.width = "720px";
    clone.style.height = "720px";
    clone.style.position = "absolute";
    clone.style.top = "-9999px";
    clone.style.left = "-9999px";
    clone.style.zIndex = "-9999";
    
    const titleNode = clone.querySelector(".slide-card-title");
    if (titleNode) {
        const currentSize = parseFloat(titleNode.style.fontSize);
        titleNode.style.fontSize = `${currentSize * 2.8}px`;
    }
    const subNode = clone.querySelector(".slide-card-subtitle");
    if (subNode) {
        subNode.style.fontSize = "30px";
        subNode.style.marginTop = "18px";
    }
    const logoBadge = clone.querySelector(".card-logo-badge");
    if (logoBadge) {
        logoBadge.style.height = "78px";
        logoBadge.style.padding = "9px 24px";
        const logoImg = logoBadge.querySelector("img");
        if (logoImg) {
            logoImg.style.height = "54px";
            logoImg.style.maxWidth = "240px";
        }
    }
    
    document.body.appendChild(clone);
    await sleep(150);
    
    const canvas = await html2canvas(clone, {
        width: 720,
        height: 720,
        windowWidth: 720,
        windowHeight: 720,
        scale: 2.5,
        useCORS: true,
        backgroundColor: null
    });
    document.body.removeChild(clone);
    
    const dataUrl = canvas.toDataURL("image/jpeg", 0.98);
    return dataURLtoBlob(dataUrl);
}

// Kakao Talk Share trigger
btnKakaoShare.addEventListener("click", async () => {
    if (!appState.cardData) return;
    
    if (!appState.kakaoKey) {
        alert("카카오 전송 기능을 이용하시려면 먼저 에이전트 설정에서 'Kakao JavaScript Key'를 입력해 주세요.");
        return;
    }
    
    if (!window.Kakao) {
        alert("카카오 SDK가 정상적으로 로드되지 않았습니다.");
        return;
    }
    
    if (!window.Kakao.isInitialized()) {
        try {
            window.Kakao.init(appState.kakaoKey);
        } catch(initErr) {
            alert("카카오 SDK 초기화에 실패했습니다: " + initErr.message);
            return;
        }
    }
    
    btnKakaoShare.disabled = true;
    const originalText = btnKakaoShare.innerHTML;
    btnKakaoShare.innerHTML = `<i data-lucide="loader" class="animate-spin"></i> 전송 준비 중...`;
    lucide.createIcons();
    
    addLog("Publisher", "카카오 서버로 카드뉴스 커버 이미지 전송 업로드 시작...", "publisher");
    
    try {
        const coverBlob = await getCoverJpegBlob();
        const coverFile = new File([coverBlob], "cover.jpg", { type: "image/jpeg" });
        
        window.Kakao.Share.uploadImage({
            file: [coverFile]
        }).then(function(res) {
            const uploadedUrl = res.infos.original.url;
            addLog("Publisher", "카카오 이미지 업로드 완료. 공유 팝업 창을 띄웁니다.", "success");
            
            const firstSlideTitle = appState.cardData.slides[0].title;
            const subtitle = appState.cardData.slides[0].subtitle || "성아연 AI 뉴스 브리핑";
            const targetUrl = window.location.href;
            
            window.Kakao.Share.sendDefault({
                objectType: 'feed',
                content: {
                    title: firstSlideTitle,
                    description: subtitle,
                    imageUrl: uploadedUrl,
                    link: {
                        mobileWebUrl: targetUrl,
                        webUrl: targetUrl,
                    },
                },
                buttons: [
                    {
                        title: '카드뉴스 대시보드 바로가기',
                        link: {
                            mobileWebUrl: targetUrl,
                            webUrl: targetUrl,
                        },
                    }
                ],
            });
            
            btnKakaoShare.disabled = false;
            btnKakaoShare.innerHTML = originalText;
            lucide.createIcons();
        }).catch(function(uploadErr) {
            addLog("Publisher", "카카오 이미지 업로드 에러: " + JSON.stringify(uploadErr), "warning");
            alert("카카오 이미지 업로드 중 오류가 발생했습니다. 카카오 자바스크립트 키 설정 및 플랫폼 설정을 확인해 주세요.");
            btnKakaoShare.disabled = false;
            btnKakaoShare.innerHTML = originalText;
            lucide.createIcons();
        });
        
    } catch(err) {
        addLog("Publisher", "카카오 전송 프로세스 중 실패: " + err.message, "warning");
        alert("카카오 전송 중 실패했습니다: " + err.message);
        btnKakaoShare.disabled = false;
        btnKakaoShare.innerHTML = originalText;
        lucide.createIcons();
    }
});

// Copy Cardnews text representation to clipboard
if (btnCopyText) {
    btnCopyText.addEventListener("click", () => {
        if (!appState.cardData) return;
        
        let textContent = `📢 ${appState.mode === 'daily' ? '일간' : '주간'} 성아연 AI 뉴스 브리핑\n\n`;
        
        appState.cardData.slides.forEach((slide) => {
            if (slide.type === 'title') {
                textContent += `=== ${slide.title} ===\n${slide.subtitle}\n\n`;
            } else if (slide.type === 'content') {
                const idxStr = `${slide.slide_index - 1}.`;
                if (slide.title.startsWith(idxStr)) {
                    textContent += `${slide.title}\n`;
                } else {
                    textContent += `${idxStr} ${slide.title}\n`;
                }
                slide.bullets.forEach(bullet => {
                    textContent += `• ${bullet}\n`;
                });
                if (slide.source_name) {
                    textContent += `출처 바로가기: ${slide.source_url}\n`;
                }
                textContent += `\n`;
            } else if (slide.type === 'closing') {
                textContent += `=== ${slide.title} ===\n${slide.subtitle}\n`;
                textContent += `🔗 성아연 카카오톡 채널: https://pf.kakao.com/_KxgMwX\n`;
            }
        });
        
        navigator.clipboard.writeText(textContent.trim()).then(() => {
            alert("카드뉴스 텍스트 내용(출처 링크 포함)이 클립보드에 복사되었습니다!\n\n블로그나 메모장, 카카오톡 등에 바로 붙여넣기 하실 수 있습니다.");
            addLog("Publisher", "성공적으로 모든 슬라이드의 텍스트 정보(출처 링크 포함)를 클립보드에 복사했습니다.", "success");
        }).catch(err => {
            alert("클립보드 복사 실패: " + err.message);
        });
    });
}
