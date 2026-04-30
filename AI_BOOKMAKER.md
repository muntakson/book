# AI BookMaker: Lessons Learned

This document captures key insights, challenges, and best practices discovered while building the BookMaker web application - a system that orchestrates book creation using Claude Code CLI.

---

## 1. Claude Code CLI Integration

### Key Discovery: Print Mode (`-p`) Limitations

Claude Code's `-p` (print) mode is designed for non-interactive scripting. Critical constraints:

```bash
# Basic non-interactive usage
claude -p "your query" --output-format json

# Streaming output (NDJSON)
claude -p "query" --output-format stream-json

# Skip permission prompts (dangerous but necessary for automation)
claude -p "query" --dangerously-skip-permissions
```

**Limitation**: The `-p` flag disables interactive stdin. You cannot pipe responses back mid-execution in the traditional sense.

### Workaround: Stream-JSON with Subprocess

The solution is to use `asyncio.create_subprocess_exec` with stdin/stdout pipes:

```python
self.process = await asyncio.create_subprocess_exec(
    "claude", "-p", prompt,
    "--output-format", "stream-json",
    "--dangerously-skip-permissions",
    "--add-dir", codebase_path,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
```

Then parse NDJSON events from stdout and write responses to stdin when needed.

### Important Flags

| Flag | Purpose |
|------|---------|
| `--output-format stream-json` | Get NDJSON events for real-time streaming |
| `--dangerously-skip-permissions` | Auto-approve file operations (use carefully) |
| `--add-dir {path}` | Grant access to specific directories |
| `--max-budget-usd N` | Limit API costs (production safety) |

---

## 2. Question Detection Challenge

### The Problem

Claude Code doesn't have a built-in "question" event type. When Claude asks the user a question (e.g., Phase 0 preferences), it just outputs text. The web app must detect these questions in the stream.

### Solution: Pattern Matching

```python
PREFERENCE_PATTERNS = [
    r"\*\*Book structure\*\*",
    r"\*\*Writing style\*\*",
    r"\*\*Mathematics depth\*\*",
    # ... more patterns from master prompt
]

OPTION_PATTERN = r"([A-D])\)\s*(.+?)(?=\s*[A-D]\)|$|\n)"
```

**Key insight**: Accumulate text in a buffer and search for patterns. Extract A), B), C) options using regex. Use a hash to avoid duplicate detections.

### Alternative: Structured Prompting

Tell Claude to use a specific format when asking questions:

```
When you need user input, format your question as:
QUESTION: [question text]
OPTIONS:
A) [option]
B) [option]
...
```

This makes detection more reliable than pattern matching against natural language.

---

## 3. WebSocket Architecture

### Why WebSocket over Polling

- Real-time streaming output (no 1-second polling delay)
- Bidirectional communication (questions can push to client)
- Lower server load
- Better user experience with live progress

### Event Protocol Design

```typescript
// Server → Client events
type ServerEvent =
  | { type: "stream_output"; content: string; source: string }
  | { type: "question"; question_id: string; text: string; options: string[] }
  | { type: "phase_change"; phase: number; name: string }
  | { type: "book_complete"; paths: OutputPaths }
  | { type: "error"; message: string }

// Client → Server events
type ClientEvent =
  | { type: "user_response"; question_id: string; response: string }
  | { type: "cancel" }
```

### Lesson: Dual Channel Reliability

Use both WebSocket AND REST for critical operations:

```typescript
// Send via WebSocket for real-time
send({ type: 'user_response', question_id, response });
// Also via REST for reliability
await api.respondToQuestion(question_id, response);
```

---

## 4. State Management

### Session State Machine

```
idle → analyzing → editing → running ⟷ waiting_input → completed
                      ↓                      ↓
                   failed ←─────────────────┘
```

### Persistence for Recovery

Store session state to JSON for server restart recovery:

```python
@dataclass
class SessionState:
    status: SessionStatus
    codebase_path: str
    master_prompt: str
    current_phase: int
    pending_question: Optional[Question]
    output_paths: dict

async def save(self):
    async with aiofiles.open("session_state.json", "w") as f:
        await f.write(json.dumps(self.state.to_dict()))
```

### Lesson: Phase Tracking

Claude's output doesn't explicitly announce phase transitions. Solutions:

1. **Pattern matching**: Look for "PHASE N COMPLETE" or "Moving to Phase N"
2. **Structured prompts**: Tell Claude to output `[PHASE_COMPLETE: N]` markers
3. **Heuristic detection**: Detect based on output content (e.g., "Korean" → Phase 7)

---

## 5. Prompt Adaptation

### The Challenge

The master prompt is specific to one codebase (nanochat). For other codebases, it needs adaptation:
- Different directory structure
- Different module names
- Different chapter topics

### Solution: Codebase Analysis

```python
def _analyze_codebase(self, path: str) -> dict:
    analysis = {
        "name": path.name,
        "python_files": list(path.rglob("*.py")),
        "main_modules": [],  # Dirs with __init__.py
        "readme": None,
        "claude_md": None,
    }
    # ... detection logic
    return analysis
```

Then perform string replacements and add adaptation notes to the prompt.

### Lesson: Let Claude Do Heavy Lifting

For complex adaptation, run Claude once to analyze and suggest changes:

```bash
claude -p "Analyze this codebase and suggest how to adapt the book prompt" \
  --output-format json --add-dir {path}
```

This is more flexible than hardcoded regex replacements.

---

## 6. Frontend Architecture

### Step-Based Workflow

The UI follows a linear flow matching the backend states:

```typescript
type AppStep = 'path' | 'prompt' | 'progress' | 'results';
```

Each step has a dedicated component. The App component manages transitions based on WebSocket events.

### Terminal-Style Output

For streaming output, use:
- Monospace font
- Dark background (terminal aesthetic)
- Auto-scroll with manual override
- Accumulate lines in state array

```tsx
const [outputLog, setOutputLog] = useState<string[]>([]);

// On new output
setOutputLog(prev => [...prev, event.content]);

// Auto-scroll
useEffect(() => {
  if (shouldAutoScroll.current) {
    outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }
}, [outputLog]);
```

### Modal for Questions

Questions interrupt the flow and require immediate attention. Use a modal overlay:
- Blocks background interaction
- Shows question prominently
- Radio buttons for A/B/C options
- Custom input fallback

---

## 7. Error Handling

### Graceful Degradation

| Error Type | Handling |
|------------|----------|
| Claude process crash | Detect via exit code, show error, allow retry |
| WebSocket disconnect | Auto-reconnect after 3s, maintain state |
| Invalid path | Validate before starting, show clear error |
| Question timeout | Keep waiting (Claude is patient) |

### Process Termination

```python
async def stop(self):
    self._running = False
    if self.process:
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self.process.kill()
```

---

## 8. Security Considerations

### Path Validation

Always validate user-provided paths:

```python
ALLOWED_ROOTS = ["/var/www/aibook", "/home", os.path.expanduser("~")]

def validate(path: str) -> bool:
    resolved = Path(path).resolve()
    return any(str(resolved).startswith(root) for root in ALLOWED_ROOTS)
```

### Command Injection Prevention

Never interpolate user input into shell commands. Use subprocess with argument lists:

```python
# Good
subprocess.run(["claude", "-p", user_prompt])

# Bad - command injection risk
subprocess.run(f"claude -p '{user_prompt}'", shell=True)
```

### Cost Control

For production, always set budget limits:

```bash
claude -p "..." --max-budget-usd 5.00
```

---

## 9. Performance Optimizations

### Reduce Context Usage

- Stream output incrementally (don't buffer entire response)
- Keep output log capped (last 1000 lines)
- Use efficient WebSocket binary protocol if needed

### Parallel Processing

Phase 6 (images) and Phase 7 (translation) can theoretically run in parallel. The master prompt supports this with agent orchestration.

### Frontend Bundle Size

- Use Vite for efficient tree-shaking
- Tailwind CSS purges unused styles
- React production build: ~53KB gzipped

---

## 10. Lessons for Future Improvements

### 1. Structured Output Mode

Claude Code could benefit from a `--structured-questions` flag that outputs questions in a machine-readable format instead of natural language.

### 2. Session Resumption

Currently, if the browser closes mid-execution, the session continues but the frontend loses context. Improvement: Store full output log in session state for replay.

### 3. Multi-Session Support

The current design is single-session. For multi-user:
- Use session IDs in WebSocket routing
- Database instead of JSON file
- Process pool for concurrent Claude executions

### 4. Progress Estimation

Claude's phases have variable duration. Could estimate progress by:
- Counting output tokens
- Tracking file creation events
- Using historical timing data

### 5. Webhook Integration

The user asked about webhooks. While Claude Code CLI doesn't natively support webhooks, you could:
- Set up a polling endpoint that the frontend calls
- Use Server-Sent Events (SSE) as an alternative to WebSocket
- Implement a callback URL that receives POST on completion

---

## Summary

Building a web wrapper around Claude Code CLI requires:

1. **Understanding CLI limitations** - No native webhook, limited interactivity
2. **Creative detection** - Pattern matching for questions in stream
3. **Robust state management** - Persist state, handle crashes gracefully
4. **Real-time UX** - WebSocket streaming, terminal-style output
5. **Security mindfulness** - Path validation, command injection prevention

The resulting architecture (FastAPI + WebSocket + React) provides a solid foundation for orchestrating long-running Claude Code tasks with human-in-the-loop interaction.
