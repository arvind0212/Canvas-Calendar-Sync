# Canvas Calendar Sync

Automatically sync assignment deadlines from KTH and Karolinska Institutet Canvas to Google Calendar.

## Features

- Syncs assignments from multiple Canvas universities (KTH and KI)
- Creates calendar events 30 minutes before assignment due dates
- Prevents duplicates using assignment ID tracking
- Updates existing events when assignment details change
- Comprehensive logging and error handling
- Bi-weekly automated sync via cron

## Setup

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Canvas Access Tokens

Generate personal access tokens for both universities:

**KTH Canvas:**
1. Go to https://canvas.kth.se/
2. Click profile → Settings → "New Access Token"
3. Purpose: "Personal assignment calendar sync"
4. Expires: Never
5. Copy the token

**KI Canvas:**
1. Go to https://ki.instructure.com/
2. Follow same steps as above

### 3. Google Calendar API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Calendar API
4. Create OAuth2 credentials (Desktop application)
5. Download `credentials.json` to project directory

### 4. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your Canvas tokens:
# KTH_CANVAS_TOKEN=your_kth_token_here
# KI_CANVAS_TOKEN=your_ki_token_here
```

### 5. First Run

```bash
python main.py
```

On first run, you'll be prompted to authenticate with Google Calendar in your browser.

## Usage

### Manual Sync
```bash
source venv/bin/activate
python main.py
```

### Automated Sync (Cron)

Add to crontab for bi-weekly sync (Mondays and Thursdays at 8 AM):

```bash
crontab -e
# Add this line:
0 8 * * 1,4 /path/to/canvas-calendar-sync/venv/bin/python /path/to/canvas-calendar-sync/main.py >> /path/to/logs/sync.log 2>&1
```

## Event Format

Calendar events are created with:
- **Title**: `[University] Course: Assignment Name`
- **Time**: 30 minutes before due date
- **Description**: Assignment details and direct link to Canvas
- **Metadata**: Assignment ID for deduplication

## Configuration

Edit `config.py` to modify:
- `SYNC_WEEKS_AHEAD`: How far ahead to sync (default: 12 weeks)
- `LOG_LEVEL`: Logging verbosity (default: INFO)
- University configurations

## Troubleshooting

### No Events Created
- Verify Canvas tokens have correct permissions
- Check you're enrolled in courses with assignments
- Ensure assignments have due dates set

### Authentication Errors
- Regenerate Canvas tokens if expired
- Re-run Google OAuth flow by deleting `token.json`

### Sync Failures
- Check `sync.log` for detailed error messages
- Verify network connectivity to Canvas and Google APIs

## File Structure

```
canvas-calendar-sync/
├── main.py              # Entry point
├── config.py            # Configuration management
├── canvas_client.py     # Canvas API client
├── calendar_client.py   # Google Calendar API client
├── sync_engine.py       # Core sync logic
├── requirements.txt     # Dependencies
├── .env                 # Environment variables (create from .env.example)
├── credentials.json     # Google OAuth credentials (download from Google Cloud)
├── token.json          # Generated after first Google auth
└── sync.log            # Sync logs
```