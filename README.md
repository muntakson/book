# BookMaker - AI-Powered Book Prompt Adapter

Transform your book idea into a comprehensive master prompt using Groq AI.

## Overview

BookMaker is a simple web application that helps you create detailed book creation prompts. Enter your book idea, and the app uses Groq's LLM API to adapt a master prompt template specifically for your topic.

### How It Works

1. **Stage 1:** User enters their book idea in a text box
2. **Stage 2:** App sends the book idea + master prompt template to Groq API
3. **Stage 3:** Display the adapted prompt that users can copy and use

## Architecture

```
┌─────────────────────┐
│  React Frontend     │
│  (Vite + TypeScript)│──┐
└─────────────────────┘  │ HTTP POST /api/adapt-prompt
                         ▼
              ┌──────────────────────┐
              │  FastAPI Backend     │
              │  - Groq SDK          │
              │  - python-dotenv     │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Groq API            │
              │  (llama-3.3-70b)     │
              └──────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+
- npm or yarn
- Groq API key ([Get one here](https://console.groq.com))

### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "GROQ_API_KEY=your_api_key_here" > .env

# Run development server
uvicorn main:app --reload --port 8080
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Visit `http://localhost:3000` in your browser.

## Production Deployment

### Build Frontend

```bash
cd frontend
npm run build
```

This creates optimized static files in `frontend/dist/`.

### Run Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8080
```

The backend will automatically serve the frontend static files from `frontend/dist/`.

## API Endpoints

### `POST /api/adapt-prompt`

Adapt the master prompt based on user's book idea.

**Request:**
```json
{
  "book_idea": "A comprehensive guide to building AI-powered hydroponic greenhouses"
}
```

**Response:**
```json
{
  "adapted_prompt": "# Multi-Phase Book Creation...",
  "model": "llama-3.3-70b-versatile",
  "tokens_used": 3542
}
```

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "bookmaker",
  "version": "2.0.0",
  "groq_configured": true
}
```

## Configuration

### Environment Variables

Create `backend/.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
```

### Master Prompt Template

The app uses `BOOK_MASTER_PROMPT.md` in the project root. You can replace this with your own template:

- For codebase-based books: Use `/var/www/aibook/nanochat/BOOK_NANOCHAT_MASTER_PROMPT.md`
- For platform-based books: Use `/var/www/aibook/hydroponic-ai/HYDROPONIC_AI_MASTER_PROMPT.md`

## Groq API Details

**Model:** `llama-3.3-70b-versatile`
- Context length: 128k tokens
- Speed: ~480 tokens/second
- Ideal for long-form content adaptation

**Documentation:** https://console.groq.com/docs

## Project Structure

```
bookmaker/
├── backend/
│   ├── main.py              # FastAPI app with Groq integration
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # Environment variables (create this)
│   └── venv/                # Virtual environment
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Main React component
│   │   ├── App.css          # Styling
│   │   └── main.tsx         # Entry point
│   ├── dist/                # Built static files (after npm run build)
│   ├── package.json
│   └── vite.config.ts       # Vite configuration
├── BOOK_MASTER_PROMPT.md    # Template file
└── README.md                # This file
```

## Features

- ✅ Simple 3-stage workflow
- ✅ Real-time error handling
- ✅ Copy to clipboard functionality
- ✅ Responsive design
- ✅ Loading states with spinner
- ✅ Token usage tracking
- ✅ Modern, gradient UI

## Next Steps After Getting Adapted Prompt

1. Copy the adapted prompt
2. Save it to a file (e.g., `MY_BOOK_PROMPT.md`)
3. Use it with:
   - **Claude Code CLI:** `claude -p "$(cat MY_BOOK_PROMPT.md)"`
   - **Claude.ai:** Paste directly into chat
   - **API integration:** Use with Anthropic API

## Troubleshooting

### Backend won't start

- Check Python version: `python3 --version` (need 3.8+)
- Verify virtual environment is activated
- Check .env file exists with GROQ_API_KEY

### Frontend won't connect to backend

- Ensure backend is running on port 8080
- Check browser console for errors
- Verify proxy configuration in `frontend/vite.config.ts`

### "Groq API error"

- Verify API key is correct in `.env`
- Check Groq API status: https://status.groq.com
- Review rate limits: https://console.groq.com

## Contributing

This is a simple, focused tool. If you want to add features:

- Model selection dropdown
- Temperature control slider
- Multiple template options
- Save/load functionality
- Direct Claude Code CLI integration

## License

MIT

## Links

- Live site: https://book.iotok.org
- Groq Console: https://console.groq.com
- Claude Code: https://claude.ai/code
