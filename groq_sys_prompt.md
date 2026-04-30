# Groq API System Prompt Documentation

This document explains exactly what prompts are sent to Groq when a user submits a book idea.

## API Call Structure

When a user submits a book idea, the backend sends two messages to Groq:

1. **System Message** - Defines the AI's role and instructions
2. **User Message** - Contains the master prompt template + user's book idea

---

## System Message (Role: "system")

```
You are an expert book creation assistant and instructional designer.

Your task is to adapt a master prompt template for creating educational books. The user will provide:
1. A master prompt template (with structure, phases, and guidelines)
2. A book idea (the topic they want to write about)

You should:
- Analyze the book idea and understand its core concepts
- Adapt the master prompt's project overview, learning objectives, and chapter topics to match the new idea
- Keep the same multi-phase structure (Phase 0-8) and workflow
- Preserve formatting, code blocks, and instructional tone
- Replace example content with content relevant to the new book idea
- Maintain the bilingual (English/Korean) approach if present in the template

Return ONLY the adapted prompt without any additional commentary or explanation.
```

**Purpose:** This sets the context for Groq to act as a book creation expert who adapts templates rather than creating content from scratch.

---

## User Message (Role: "user")

**Template Structure:**

```
Master Prompt Template:

[Full contents of BOOK_MASTER_PROMPT.md - 174 lines]

---

User's Book Idea:
{user's input from frontend}

---

Please adapt the above master prompt template to create a comprehensive educational book about: {user's input}

Specifically:
1. Update the project overview (title, subtitle, description) to match the book idea
2. Adapt chapter topics and learning objectives to the new subject
3. Modify code examples and technical content to be relevant
4. Keep the same phase-based workflow structure
5. Preserve all formatting and instructional guidelines
```

**Variables:**
- `{master_prompt}` - Contents of `/var/www/aibook/bookmaker/BOOK_MASTER_PROMPT.md`
- `{request.book_idea}` - User input from frontend textarea

---

## Groq API Parameters

```python
groq_client.chat.completions.create(
    model="llama-3.3-70b-versatile",  # 128k context window
    messages=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ],
    temperature=0.7,    # Balanced creativity (0.0 = deterministic, 1.0 = creative)
    max_tokens=8000,    # Maximum response length
    top_p=0.9,          # Nucleus sampling parameter
)
```

**Model Details:**
- **Name:** `llama-3.3-70b-versatile`
- **Context Length:** 128k tokens (can handle very long prompts)
- **Speed:** ~480 tokens/second
- **Best for:** Long-form content adaptation and generation

---

## Example: "book theme is hydroponics with AI"

### Input Book Idea
```
book theme is hydroponics with AI
```

### What Gets Sent to Groq

**System Message:** (same as above)

**User Message:**
```
Master Prompt Template:

# Multi-Phase Book Creation Master Prompt (Condensed)

## Project Overview

```yaml
project:
  title: "Voice3D: Transforming Sound into 3D Sculptures"
  subtitle: "A hands-on guide to audio visualization with MFCC, PCA, and ML"
  platform: https://stivibe.iotok.org/p/project-mkol6l3k/
  source_code: ./birdsong/birdsong-app/
  target_pages: 150
  languages: [English, Korean]
  audience: "High school students (STEM interest)"
```

---

# PHASE 0: User Preferences

**Ask these questions before starting:**

| Category | Question | Options |
|----------|----------|---------|
| Structure | Book structure? | A) Chapter-based B) Tutorial-driven C) Hybrid |
| Style | Writing style? | A) Academic B) Practical C) Balanced |
| Math | Mathematics depth? | A) Conceptual B) Essential formulas C) Full derivations |
| Code | Programming depth? | A) No code B) Examples C) Full tutorials |
| Korean | Technical terms? | A) Full Korean B) English + Korean (푸리에 변환) C) English only |

---

# PHASE 1: Planning & Outline

## Chapter Structure (8 Chapters + Projects + Appendices)

**Part I: Foundations (Ch 1-3)**
- Ch1: The Hidden World of Sound - Why visualize sound
- Ch2: Sound as Numbers - Analog to digital, sampling
- Ch3: Frequency - Pitch, harmonics, Fourier intuition

**Part II: Feature Extraction (Ch 4-5)**
- Ch4: FFT and Spectrograms - Time-frequency analysis
- Ch5: MFCC - Mel scale, feature extraction

**Part III: Features to 3D (Ch 6-7)**
- Ch6: PCA - Dimensionality reduction (18D → 3D)
- Ch7: K-Means Clustering - Color mapping

**Part IV: Visualization (Ch 8)**
- Ch8: Building 3D Sound Sculptures - Three.js, animation

**Projects (5)**: Platform exploration, bird comparison, clustering analysis, recording, voice analysis

**Appendices**: Glossary, Math reference, Pipeline, Bird guide, Code reference

[... continues for 174 lines total ...]

---

User's Book Idea:
book theme is hydroponics with AI

---

Please adapt the above master prompt template to create a comprehensive educational book about: book theme is hydroponics with AI

Specifically:
1. Update the project overview (title, subtitle, description) to match the book idea
2. Adapt chapter topics and learning objectives to the new subject
3. Modify code examples and technical content to be relevant
4. Keep the same phase-based workflow structure
5. Preserve all formatting and instructional guidelines
```

### Expected Groq Response (Adapted Prompt)

The response will be a modified version of the master prompt with hydroponics content:

```yaml
project:
  title: "AI-Powered Hydroponics: Growing Smarter with Machine Learning"
  subtitle: "A hands-on guide to building intelligent greenhouse systems with IoT and AI"
  platform: https://shai.iotok.org  # (adapted to relevant platform)
  source_code: ./hydroponics-ai/
  target_pages: 150
  languages: [English, Korean]
  audience: "High school students (STEM interest)"
```

**Adapted Chapters:**
- Ch1: Introduction to Hydroponics - Why grow without soil
- Ch2: Sensor Systems - pH, temperature, humidity, light sensors
- Ch3: IoT Integration - Connecting sensors to data streams
- Ch4: Data Collection & Storage - Time-series databases
- Ch5: Machine Learning Basics - Regression, classification for agriculture
- Ch6: Crop Optimization Models - Predicting optimal conditions
- Ch7: Computer Vision - Plant health monitoring with cameras
- Ch8: Building Your Smart Greenhouse - Putting it all together

---

## How to Test Manually

You can test the prompt by calling the API directly:

```bash
curl -X POST http://localhost:8080/api/adapt-prompt \
  -H "Content-Type: application/json" \
  -d '{"book_idea": "book theme is hydroponics with AI"}'
```

Or use the frontend at `http://localhost:3000` after starting both backend and frontend servers.

---

## Modifying the System Prompt

To change the system prompt, edit `/var/www/aibook/bookmaker/backend/main.py` at line 107:

```python
system_message = """Your new instructions here..."""
```

**Common modifications:**
- Change tone (more formal, more casual)
- Add specific requirements (must include X chapters, must have Y sections)
- Change output format (JSON instead of markdown)
- Add constraints (no code examples, only conceptual content)

---

## Modifying the User Message Template

To change the user message structure, edit `/var/www/aibook/bookmaker/backend/main.py` at line 124:

```python
user_message = f"""Your new template here...
{master_prompt}
{request.book_idea}
"""
```

---

## Changing the Master Prompt Template

The master prompt file is at `/var/www/aibook/bookmaker/BOOK_MASTER_PROMPT.md`.

**To use a different template:**

```bash
# Use the comprehensive nanochat template (941 lines)
cp /var/www/aibook/nanochat/BOOK_NANOCHAT_MASTER_PROMPT.md \
   /var/www/aibook/bookmaker/BOOK_MASTER_PROMPT.md

# Or use the hydroponic-ai template (858 lines)
cp /var/www/aibook/hydroponic-ai/HYDROPONIC_AI_MASTER_PROMPT.md \
   /var/www/aibook/bookmaker/BOOK_MASTER_PROMPT.md
```

After changing, restart the backend server for the changes to take effect.

---

## Token Usage Estimation

**Typical token counts:**
- System message: ~120 tokens
- Master prompt template: ~1,200 tokens (for 174-line version)
- User's book idea: ~5-50 tokens
- Instructions: ~80 tokens
- **Total input:** ~1,400-1,450 tokens

**Response:**
- Adapted prompt: ~1,500-3,000 tokens (depending on complexity)

**Total per request:** ~3,000-4,500 tokens

**Cost:** Groq has generous free tier, check current rates at https://console.groq.com

---

## Troubleshooting

### Response is too short or incomplete

Increase `max_tokens`:
```python
max_tokens=16000,  # Instead of 8000
```

### Response is too generic

Lower `temperature` for more focused output:
```python
temperature=0.3,  # Instead of 0.7
```

### Response doesn't follow format

Make system prompt more explicit:
```python
system_message = """...
IMPORTANT: You must preserve ALL markdown formatting, code blocks, and YAML frontmatter.
Output must be valid markdown that can be saved directly as a .md file.
"""
```

---

## Related Files

- **Backend code:** `/var/www/aibook/bookmaker/backend/main.py` (lines 107-155)
- **Master prompt:** `/var/www/aibook/bookmaker/BOOK_MASTER_PROMPT.md`
- **Environment:** `/var/www/aibook/bookmaker/backend/.env` (contains GROQ_API_KEY)
- **Documentation:** `/var/www/aibook/bookmaker/README.md`

---

## Last Updated

2026-01-29
