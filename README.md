# Stock News API

AI-powered stock news aggregation and analysis system with local-first LLM processing.

## Features

- 📰 Automated news scraping from websites and YouTube videos
- 🤖 Local LLM analysis using Ollama (sentiment, entity extraction)
- 📊 Stock-specific sentiment analysis
- ⏰ Configurable scheduling for data sources
- 🔄 Real-time WebSocket updates
- 🎯 REST API for external integrations
- 💻 Modern React + TypeScript web interface

## Technology Stack

### Backend
- **FastAPI** - Python web framework
- **LangGraph** - Agent orchestration
- **Ollama** - Local LLM inference
- **Playwright** - Web scraping
- **yt-dlp** - YouTube processing
- **SQLite** - Database
- **APScheduler** - Task scheduling

### Frontend
- **React 18** with TypeScript
- **Vite** - Build tool
- **TanStack Query** - Server state
- **Zustand** - Client state
- **Tailwind CSS** - Styling
- **Recharts** - Data visualization

## Quick Start

### Prerequisites
- Docker and Docker Compose
- At least 8GB RAM (for running LLMs locally)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd NewsAPI
```

2. Start the services:
```bash
docker-compose up -d
```

3. Pull required Ollama models:
```bash
docker exec -it newsapi-ollama-1 ollama pull llama3.1
docker exec -it newsapi-ollama-1 ollama pull whisper
```

4. Access the application:
- Frontend UI: http://localhost:3000
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/v1/health

5. Create your first data source:
```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bloomberg Tech",
    "url": "https://www.bloomberg.com/technology",
    "source_type": "website",
    "fetch_frequency_minutes": 60
  }'
```

The scheduler will automatically start fetching news every hour!

## API Endpoints

### Data Sources
- `GET /api/v1/sources` - List all sources
- `POST /api/v1/sources` - Create new source
- `GET /api/v1/sources/{id}` - Get source details
- `PUT /api/v1/sources/{id}` - Update source
- `DELETE /api/v1/sources/{id}` - Delete source
- `PATCH /api/v1/sources/{id}/status` - Update status
- `POST /api/v1/sources/{id}/test` - Test source

### Health & Status
- `GET /api/v1/health` - Health check
- `GET /api/v1/status` - System status

### Processing
- `POST /api/v1/process/url` - Process a URL through full workflow
- `POST /api/v1/process/trigger/{source_id}` - Trigger processing for a source

### Testing (Development)
- `POST /api/v1/test/scrape` - Test web scraping or YouTube processing
- `GET /api/v1/test/ollama` - Test Ollama connection

### Articles (Coming Soon)
- `GET /api/v1/articles` - List articles with filtering
- `GET /api/v1/articles/{id}` - Get article details
- `GET /api/v1/articles/{id}/stocks` - Get stock mentions

### Scheduler
- `GET /api/v1/scheduler/status` - Get scheduler status
- `GET /api/v1/scheduler/jobs` - List all scheduled jobs
- `GET /api/v1/scheduler/jobs/{source_id}` - Get job info
- `POST /api/v1/scheduler/pause` - Pause/resume all fetching
- `POST /api/v1/scheduler/trigger/{source_id}` - Trigger immediate run

### Stocks (Coming Soon)
- `GET /api/v1/stocks` - List all mentioned stocks
- `GET /api/v1/stocks/{ticker}` - Get stock details
- `GET /api/v1/stocks/{ticker}/sentiment` - Sentiment trend

## Development

### Backend Setup (Local)

1. Create virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Initialize database:
```bash
python -m app.init_db
```

5. Run development server:
```bash
uvicorn app.main:app --reload
```

### Frontend Setup (Local)

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Run development server:
```bash
npm run dev
```

The frontend will be available at http://localhost:3000 with hot reload.

**Note**: The frontend automatically proxies API requests to http://localhost:8000 in development mode.

## Project Structure

```
NewsAPI/
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── api/             # API routes
│   │   ├── agents/          # LangGraph agents (coming soon)
│   │   ├── services/        # Business logic (coming soon)
│   │   └── scheduler/       # Task scheduling (coming soon)
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # React frontend
│   ├── src/
│   │   ├── components/      # Reusable components
│   │   ├── pages/           # Page components
│   │   ├── api/             # API client
│   │   ├── store/           # State management
│   │   └── types/           # TypeScript types
│   ├── Dockerfile
│   └── nginx.conf
├── data/                    # SQLite database
├── downloads/               # Temporary video storage
└── docker-compose.yml
```

## Configuration

Key configuration options in `.env`:

```env
# Ollama models
OLLAMA_MODEL_ANALYSIS=llama3.1
OLLAMA_MODEL_NER=llama3.1
OLLAMA_MODEL_WHISPER=whisper

# Processing
MAX_CONCURRENT_FETCHES=3
DATA_RETENTION_DAYS=30
AUTO_DISABLE_THRESHOLD=5
```

## Implementation Status

### Phase 1: Core Backend Infrastructure ✅
- [x] FastAPI project structure
- [x] SQLite database schema
- [x] SQLAlchemy models
- [x] Pydantic schemas
- [x] CRUD endpoints for data sources
- [x] Health check endpoints
- [x] Docker configuration

### Phase 2: Web Scraping & YouTube Processing ✅
- [x] Playwright web scraping service
- [x] Cookie banner detection and handling
- [x] HTML content extraction
- [x] YouTube download with yt-dlp
- [x] Whisper transcription integration
- [x] Content hashing for duplicates
- [x] Retry logic and error handling
- [x] Test endpoints for scraping

### Phase 3: LangGraph Agent Pipeline ✅
- [x] LangGraph workflow setup
- [x] Scraper agent node (integrates Phase 2 services)
- [x] Analyzer agent (LLM content extraction with caching)
- [x] NER agent (stock extraction with sentiment separation)
- [x] Supervisor agent (workflow routing)
- [x] Finalizer agent (database persistence)
- [x] Error handler agent
- [x] Processing logs and timings
- [x] End-to-end workflow testing

### Phase 4: Task Scheduling ✅
- [x] APScheduler setup with SQLAlchemy jobstore
- [x] Dynamic job management (add/remove/update)
- [x] Cron expression support
- [x] Global pause functionality
- [x] Auto-disable failed sources (5 consecutive failures)
- [x] Concurrent fetch limiting (semaphore-based)
- [x] Data retention cleanup (daily job)
- [x] LLM cache cleanup (daily job)
- [x] Integration with CRUD operations
- [x] Scheduler management endpoints

### Phase 5: Frontend Development ✅
- [x] React + TypeScript setup with Vite
- [x] TanStack Query integration
- [x] Zustand state management
- [x] Layout components (Header, Sidebar)
- [x] Dashboard with news feed and article cards
- [x] Data source management UI with add/edit/delete
- [x] Stock analysis pages with sentiment display
- [x] Frontend Dockerfile and nginx configuration
- [x] Docker Compose integration
- [ ] Real-time WebSocket updates (future enhancement)

### Phase 6-8: Coming Soon
- Advanced analytics and charts
- Settings and configuration UI
- Help documentation
- Production deployment

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.
# NewsAPI
