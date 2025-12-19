# AI Model Release Watcher 🔍

AI 모델의 출시 예정 및 실제 출시를 실시간으로 모니터링하고 Slack으로 알림을 보내는 서비스입니다.

## ✨ 주요 기능

- **다중 소스 모니터링**: GitHub, Hugging Face, ModelScope, arXiv, Google News RSS
- **리더보드 추적**: Artificial Analysis Image Generation 리더보드 순위 변동 감지
- **출시 단계 구분**: 출시 예정(Announced) vs 실제 출시(Launched) 자동 분류
- **다중 Slack 채널**: 이벤트 유형별 다른 채널로 알림 라우팅
- **우선순위 모델**: 특정 모델(예: Z-Image)의 모든 변경사항 추적
- **24시간 운영**: Docker 컨테이너로 무중단 모니터링

## 📁 프로젝트 구조

```
watcher/
├── main.py                 # 메인 엔트리포인트
├── config.yaml             # 설정 파일
├── requirements.txt        # Python 의존성
├── Dockerfile              # Docker 이미지 설정
├── docker-compose.yml      # Docker Compose 설정
├── .env.example            # 환경변수 템플릿
├── watchers/               # 각 소스별 Watcher
│   ├── base.py
│   ├── github_watcher.py
│   ├── huggingface_watcher.py
│   ├── modelscope_watcher.py
│   ├── arxiv_watcher.py
│   ├── news_watcher.py
│   └── leaderboard_watcher.py
├── notifiers/              # 알림 전송
│   └── slack.py
├── models/                 # 데이터 모델
│   └── state.py
├── utils/                  # 유틸리티
│   └── config_loader.py
└── data/                   # SQLite DB 저장소
    └── watcher_state.db
```

## 🚀 빠른 시작

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/ai-model-watcher.git
cd ai-model-watcher
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 편집하여 API 키를 설정합니다:

```env
# Slack Webhook URLs (필수)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_WEBHOOK_LEADERBOARD=https://hooks.slack.com/services/YOUR/LEADERBOARD/WEBHOOK
SLACK_WEBHOOK_ANNOUNCEMENTS=https://hooks.slack.com/services/YOUR/ANNOUNCEMENTS/WEBHOOK
SLACK_WEBHOOK_LAUNCHES=https://hooks.slack.com/services/YOUR/LAUNCHES/WEBHOOK

# API Tokens (선택)
GITHUB_TOKEN=ghp_your_github_token
HF_TOKEN=hf_your_huggingface_token
ARTIFICIAL_ANALYSIS_API_KEY=your_aa_api_key
```

### 3. Docker로 실행

```bash
docker-compose up -d --build
```

### 4. 로그 확인

```bash
docker-compose logs -f watcher
```

---

## ⚙️ 환경 변수 설정 (.env)

### Slack Webhook URL 발급 방법

1. [Slack API](https://api.slack.com/apps) 접속
2. **Create New App** > **From scratch** 선택
3. 앱 이름과 워크스페이스 선택
4. **Features** > **Incoming Webhooks** 클릭
5. **Activate Incoming Webhooks** 활성화
6. **Add New Webhook to Workspace** 클릭
7. 채널 선택 후 **Allow**
8. 생성된 Webhook URL 복사

> 💡 채널별로 다른 Webhook이 필요하면 위 과정을 반복하세요.

### 환경 변수 목록

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `SLACK_WEBHOOK_URL` | ✅ | 기본 Slack Webhook URL |
| `SLACK_WEBHOOK_LEADERBOARD` | ❌ | 리더보드 알림 채널 |
| `SLACK_WEBHOOK_ANNOUNCEMENTS` | ❌ | 출시 예정 알림 채널 |
| `SLACK_WEBHOOK_LAUNCHES` | ❌ | 실제 출시 알림 채널 |
| `GITHUB_TOKEN` | ❌ | GitHub API 토큰 (Rate Limit 증가) |
| `HF_TOKEN` | ❌ | Hugging Face 토큰 (비공개 모델 접근) |
| `ARTIFICIAL_ANALYSIS_API_KEY` | ❌ | Artificial Analysis API 키 (리더보드 필수) |

### API 토큰 발급 방법

#### GitHub Token
1. [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. **Generate new token (classic)** 클릭
3. `public_repo` 권한 선택
4. 생성된 토큰 복사

#### Hugging Face Token
1. [Hugging Face Settings > Access Tokens](https://huggingface.co/settings/tokens)
2. **New token** 클릭
3. `read` 권한으로 생성

#### Artificial Analysis API Key
1. [Artificial Analysis Documentation](https://artificialanalysis.ai/documentation) 접속
2. API 키 발급 신청

---

## 📝 설정 파일 (config.yaml)

### 기본 구조

```yaml
# 체크 주기 (시간 단위)
check_interval_hours: 1

# 데이터베이스 경로
database_path: "data/watcher_state.db"

# 리더보드 설정
leaderboards:
  enabled: true
  boards:
    - text-to-image
    - editing
  max_rank: 30  # 30등 이내 모델만 추적

# 모니터링할 모델
models:
  - name: "Z-Image"
    github: "Tongyi-MAI/Z-Image"
    huggingface: "Tongyi-MAI/Z-Image-Turbo"
    priority: high

# 우선순위 모델 (모든 변경사항 추적)
priority_models:
  - name: "Z-Image"
    notify_all_commits: true
    notify_all_hf_changes: true
    mention_channel: true

# 알림 설정
notifications:
  include_icons: true
  include_timestamp: true
  mention_channel_for:
    - new_release
    - release_launched
```

### 주요 설정 항목

#### 리더보드 설정 (`leaderboards`)

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `enabled` | `true` | 리더보드 모니터링 전체 활성화 |
| `max_rank` | `30` | 이 순위 이내의 모델만 추적 |
| `boards` | 아래 참조 | 각 리더보드별 활성화 설정 |

**지원하는 리더보드** ([Artificial Analysis API](https://artificialanalysis.ai/documentation)):

| Board ID | 카테고리 | 설명 |
|----------|----------|------|
| `text-to-image` | 🖼️ Image | 텍스트→이미지 생성 |
| `image-editing` | 🖼️ Image | 이미지 편집 |
| `text-to-video` | 🎬 Video | 텍스트→비디오 생성 |
| `image-to-video` | 🎬 Video | 이미지→비디오 생성 |
| `text-to-speech` | 🔊 Speech | 텍스트→음성 생성 |

**설정 예시:**

```yaml
leaderboards:
  enabled: true
  max_rank: 30
  boards:
    # 원하는 리더보드만 true로 설정
    text-to-image: true      # 활성화
    image-editing: true      # 활성화
    text-to-video: false     # 비활성화
    image-to-video: false    # 비활성화
    text-to-speech: false    # 비활성화
```

#### 모델 설정 (`models`)

```yaml
models:
  - name: "모델명"              # 필수: 표시될 모델 이름
    github: "owner/repo"        # GitHub 레포지토리
    huggingface: "org/model"    # Hugging Face 모델 ID
    modelscope: "org/model"     # ModelScope 모델 ID
    arxiv_query: "검색어"        # arXiv 검색 쿼리
    news_keywords: "뉴스 키워드"  # Google News 검색어
    priority: high              # 우선순위 (high/normal)
```

#### 우선순위 모델 (`priority_models`)

```yaml
priority_models:
  - name: "Z-Image"
    notify_all_commits: true     # 모든 커밋 알림
    notify_all_hf_changes: true  # 모든 HF 변경 알림
    mention_channel: true        # @channel 멘션
```

#### 알림 설정 (`notifications`)

```yaml
notifications:
  include_icons: true            # 이모지 아이콘 포함
  include_timestamp: true        # 타임스탬프 포함
  mention_channel_for:           # @channel 멘션할 이벤트
    - release_launched
    - new_release
    - new_model
    - leaderboard_top3_change
  event_routing:                 # 이벤트별 채널 라우팅
    leaderboard_new_entry: "leaderboard"
    leaderboard_rank_change: "leaderboard"
    release_announced: "announcements"
    release_launched: "launches"
```

---

## 🐳 Docker 사용법

### 시작

```bash
# 빌드 및 시작
docker-compose up -d --build

# 로그 확인
docker-compose logs -f watcher
```

### 중지

```bash
docker-compose down
```

### 상태 확인

```bash
# 컨테이너 상태
docker-compose ps

# DB 상태 확인
sqlite3 data/watcher_state.db "SELECT key FROM watcher_states;"
```

### 상태 초기화

```bash
# 모든 상태 초기화 (모든 이벤트 재감지됨)
docker-compose exec watcher python main.py --clear-state
```

---

## 🖥️ 로컬 실행 (개발용)

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 로드
export $(cat .env | xargs)

# 단일 실행
python main.py

# 데몬 모드 (주기적 실행)
python main.py --daemon

# Slack 연결 테스트
python main.py --test
```

---

## 📊 모니터링 대상

### 지원하는 이벤트 유형

| 소스 | 이벤트 | 설명 |
|------|--------|------|
| GitHub | `new_commit` | 새 커밋 |
| GitHub | `new_release` | 새 릴리스 |
| GitHub | `repo_created` | 레포지토리 생성 |
| Hugging Face | `new_model` | 새 모델 등록 |
| Hugging Face | `model_update` | 모델 업데이트 |
| Leaderboard | `leaderboard_new_entry` | 새 모델 진입 |
| Leaderboard | `leaderboard_rank_change` | 순위 변동 |
| Leaderboard | `leaderboard_top3_change` | Top 3 변경 |
| arXiv | `new_paper` | 새 논문 |
| News | `news_article` | 뉴스 기사 |

---

## 🔧 문제 해결

### Slack 알림이 오지 않음
1. `.env` 파일의 Webhook URL 확인
2. `python main.py --test`로 연결 테스트
3. Slack 앱이 해당 채널에 추가되어 있는지 확인

### 리더보드 데이터가 비어있음
1. `ARTIFICIAL_ANALYSIS_API_KEY` 설정 확인
2. API 키가 유효한지 확인

### GitHub Rate Limit 오류
1. `GITHUB_TOKEN` 설정 (미인증: 60회/시간 → 인증: 5000회/시간)

---

## 📄 라이선스

MIT License
