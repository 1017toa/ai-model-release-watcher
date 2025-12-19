# AI Model Release Watcher 🔍

A service that monitors AI model releases and announcements in real-time across multiple platforms and sends notifications to Slack.

## ✨ Key Features

- **Multi-Source Monitoring**: GitHub, Hugging Face, ModelScope, arXiv, Google News RSS
- **Leaderboard Tracking**: Detects ranking changes on Artificial Analysis leaderboards
- **Release Stage Detection**: Automatically classifies events as Announced vs Launched
- **Multi-Channel Slack Notifications**: Routes different event types to specific channels
- **Priority Model Tracking**: Monitor all changes for specific models (e.g., Z-Image)
- **24/7 Operation**: Continuous monitoring via Docker containers

## 📁 Project Structure

```
watcher/
├── main.py                 # Main entry point
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image configuration
├── docker-compose.yml      # Docker Compose configuration
├── .env.example            # Environment variables template
├── watchers/               # Source-specific watchers
│   ├── base.py
│   ├── github_watcher.py
│   ├── huggingface_watcher.py
│   ├── modelscope_watcher.py
│   ├── arxiv_watcher.py
│   ├── news_watcher.py
│   └── leaderboard_watcher.py
├── notifiers/              # Notification handlers
│   └── slack.py
├── models/                 # Data models
│   └── state.py
├── utils/                  # Utilities
│   └── config_loader.py
└── data/                   # SQLite DB storage
    └── watcher_state.db
```

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-username/ai-model-release-watcher.git
cd ai-model-release-watcher
```

### 2. Setup Environment Variables

```bash
cp .env.example .env
```

Edit the `.env` file to configure your API keys:

```env
# Slack Webhook URLs (Required)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_WEBHOOK_LEADERBOARD=https://hooks.slack.com/services/YOUR/LEADERBOARD/WEBHOOK
SLACK_WEBHOOK_ANNOUNCEMENTS=https://hooks.slack.com/services/YOUR/ANNOUNCEMENTS/WEBHOOK
SLACK_WEBHOOK_LAUNCHES=https://hooks.slack.com/services/YOUR/LAUNCHES/WEBHOOK

# API Tokens (Optional)
GITHUB_TOKEN=ghp_your_github_token
HF_TOKEN=hf_your_huggingface_token
ARTIFICIAL_ANALYSIS_API_KEY=your_aa_api_key
```

### 3. Run with Docker

```bash
docker-compose up -d --build
```

### 4. Check Logs

```bash
docker-compose logs -f watcher
```

---

## ⚙️ Environment Variables (.env)

### How to Get Slack Webhook URLs

1. Visit [Slack API](https://api.slack.com/apps)
2. Click **Create New App** > **From scratch**
3. Enter app name and select workspace
4. Click **Features** > **Incoming Webhooks**
5. Activate **Incoming Webhooks**
6. Click **Add New Webhook to Workspace**
7. Select channel and click **Allow**
8. Copy the generated Webhook URL

> 💡 Repeat this process for each channel that needs a separate webhook.

### Environment Variables List

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_WEBHOOK_URL` | ✅ | Default Slack Webhook URL |
| `SLACK_WEBHOOK_LEADERBOARD` | ❌ | Leaderboard notifications channel |
| `SLACK_WEBHOOK_ANNOUNCEMENTS` | ❌ | Announcement notifications channel |
| `SLACK_WEBHOOK_LAUNCHES` | ❌ | Launch notifications channel |
| `GITHUB_TOKEN` | ❌ | GitHub API token (increases rate limit) |
| `HF_TOKEN` | ❌ | Hugging Face token (access private models) |
| `ARTIFICIAL_ANALYSIS_API_KEY` | ❌ | Artificial Analysis API key (required for leaderboards) |

### How to Get API Tokens

#### GitHub Token
1. Visit [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Select `public_repo` scope
4. Copy the generated token

#### Hugging Face Token
1. Visit [Hugging Face Settings > Access Tokens](https://huggingface.co/settings/tokens)
2. Click **New token**
3. Create with `read` permission

#### Artificial Analysis API Key
1. Visit [Artificial Analysis Documentation](https://artificialanalysis.ai/documentation)
2. Request API key access

---

## 📝 Configuration File (config.yaml)

### Basic Structure

```yaml
# Check interval in hours
check_interval_hours: 1

# Database path
database_path: "data/watcher_state.db"

# Leaderboard settings
leaderboards:
  enabled: true
  max_rank: 30  # Only track models within top 30
  boards:
    text-to-image: true
    image-editing: true
    text-to-video: false
    image-to-video: false
    text-to-speech: false

# Models to monitor
models:
  - name: "Z-Image"
    github: "Tongyi-MAI/Z-Image"
    huggingface: "Tongyi-MAI/Z-Image-Turbo"
    priority: high

# Priority models (track all changes)
priority_models:
  - name: "Z-Image"
    notify_all_commits: true
    notify_all_hf_changes: true
    mention_channel: true

# Notification settings
notifications:
  include_icons: true
  include_timestamp: true
  mention_channel_for:
    - new_release
    - release_launched
```

### Key Configuration Options

#### Leaderboard Settings (`leaderboards`)

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `true` | Enable/disable all leaderboard monitoring |
| `max_rank` | `30` | Only track models within this rank |
| `boards` | See below | Enable/disable each leaderboard |

**Supported Leaderboards** ([Artificial Analysis API](https://artificialanalysis.ai/documentation)):

| Board ID | Category | Description |
|----------|----------|-------------|
| `text-to-image` | 🖼️ Image | Text-to-Image generation |
| `image-editing` | 🖼️ Image | Image editing |
| `text-to-video` | 🎬 Video | Text-to-Video generation |
| `image-to-video` | 🎬 Video | Image-to-Video generation |
| `text-to-speech` | 🔊 Speech | Text-to-Speech generation |

**Configuration Example:**

```yaml
leaderboards:
  enabled: true
  max_rank: 30
  boards:
    # Set to true to enable, false to disable
    text-to-image: true      # Enabled
    image-editing: true      # Enabled
    text-to-video: false     # Disabled
    image-to-video: false    # Disabled
    text-to-speech: false    # Disabled
```

#### Model Settings (`models`)

```yaml
models:
  - name: "Model Name"           # Required: Display name
    github: "owner/repo"         # GitHub repository
    huggingface: "org/model"     # Hugging Face model ID
    modelscope: "org/model"      # ModelScope model ID
    arxiv_query: "search query"  # arXiv search query
    news_keywords: "keywords"    # Google News search terms
    priority: high               # Priority level (high/normal)
```

#### Priority Models (`priority_models`)

```yaml
priority_models:
  - name: "Z-Image"
    notify_all_commits: true     # Notify on every commit
    notify_all_hf_changes: true  # Notify on all HF changes
    mention_channel: true        # Use @channel mentions
```

#### Notification Settings (`notifications`)

```yaml
notifications:
  include_icons: true            # Include emoji icons
  include_timestamp: true        # Include timestamps
  mention_channel_for:           # Events to mention @channel
    - release_launched
    - new_release
    - new_model
    - leaderboard_top3_change
  event_routing:                 # Route events to channels
    leaderboard_new_entry: "leaderboard"
    leaderboard_rank_change: "leaderboard"
    release_announced: "announcements"
    release_launched: "launches"
```

---

## 🐳 Docker Usage

### Start

```bash
# Build and start
docker-compose up -d --build

# View logs
docker-compose logs -f watcher
```

### Stop

```bash
docker-compose down
```

### Check Status

```bash
# Container status
docker-compose ps

# Check database state
sqlite3 data/watcher_state.db "SELECT key FROM watcher_states;"
```

### Reset State

```bash
# Clear all states (will re-detect all events)
docker-compose exec watcher python main.py --clear-state
```

---

## 🖥️ Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Load environment variables
export $(cat .env | xargs)

# Single run
python main.py

# Daemon mode (periodic execution)
python main.py --daemon

# Test Slack connection
python main.py --test
```

---

## 📊 Monitoring Targets

### Supported Event Types

| Source | Event | Description |
|--------|-------|-------------|
| GitHub | `new_commit` | New commit |
| GitHub | `new_release` | New release |
| GitHub | `repo_created` | Repository created |
| Hugging Face | `new_model` | New model registered |
| Hugging Face | `model_update` | Model updated |
| Leaderboard | `leaderboard_new_entry` | New model entry |
| Leaderboard | `leaderboard_rank_change` | Rank change |
| Leaderboard | `leaderboard_top3_change` | Top 3 change |
| arXiv | `new_paper` | New paper |
| News | `news_article` | News article |

---

## 🔧 Troubleshooting

### No Slack Notifications
1. Check Webhook URLs in `.env` file
2. Test connection with `python main.py --test`
3. Verify Slack app is added to the channel

### Empty Leaderboard Data
1. Verify `ARTIFICIAL_ANALYSIS_API_KEY` is set
2. Confirm API key is valid

### GitHub Rate Limit Errors
1. Set `GITHUB_TOKEN` (unauthenticated: 60/hour → authenticated: 5000/hour)

---

## 📄 License

MIT License
