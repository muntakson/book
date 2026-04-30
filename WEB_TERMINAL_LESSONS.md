# Web SSH Terminal Implementation - Lessons Learned

**Date**: January 29, 2026
**Project**: BookMaker Admin Dashboard
**Feature**: PuTTY-style Web Terminal
**Status**: ⚠️ Disabled due to backend hanging issue

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Technical Implementation](#technical-implementation)
3. [Problems Encountered](#problems-encountered)
4. [Root Cause Analysis](#root-cause-analysis)
5. [Lessons Learned](#lessons-learned)
6. [Skills & Techniques](#skills--techniques)
7. [⚠️ Critical Cautions](#-critical-cautions)
8. [Future Solutions](#future-solutions)
9. [Code Artifacts](#code-artifacts)

---

## Overview

### Goal
Implement a web-based terminal (similar to PuTTY) in the admin dashboard that allows executing shell commands on the backend server, restricted to `/var/www/aibook` directory.

### Technology Stack
- **Frontend**: xterm.js (@xterm/xterm) + FitAddon for terminal emulation
- **Backend**: FastAPI WebSocket + ptyprocess for pseudo-terminal
- **Communication**: WebSocket for bidirectional data flow
- **Security**: JWT authentication + directory restriction

### Use Case
Enable admin users to run `claude code` commands and other shell operations directly from the web browser without needing SSH client software.

---

## Technical Implementation

### Backend Architecture

#### 1. Dependencies
```python
import ptyprocess
import asyncio
import select
from fastapi import WebSocket, WebSocketDisconnect
```

#### 2. WebSocket Endpoint
```python
@app.websocket("/ws/terminal")
async def terminal_websocket(websocket: WebSocket):
    # Accept connection
    await websocket.accept()

    # Verify JWT token from query params
    token = websocket.query_params.get("token")

    # Spawn bash with restricted bashrc
    pty = ptyprocess.PtyProcess.spawn(
        ['bash', '--rcfile', bashrc_file.name, '-i'],
        cwd='/var/www/aibook',
        dimensions=(24, 80)
    )

    # Bidirectional communication
    await asyncio.gather(read_pty(), write_pty())
```

#### 3. Directory Restriction Mechanism
```bash
# Custom .bashrc that overrides cd command
function cd() {
    local target="$1"
    if [ -z "$target" ]; then
        target="$BASE_DIR"
    fi

    local abs_path=$(readlink -f "$target" 2>/dev/null || echo "$PWD/$target")

    if [[ "$abs_path" == "$BASE_DIR"* ]]; then
        builtin cd "$target"
    else
        echo "Error: Access restricted to /var/www/aibook"
        return 1
    fi
}
```

### Frontend Architecture

#### 1. Dependencies
```json
{
  "@xterm/xterm": "^5.x",
  "@xterm/addon-fit": "^0.x"
}
```

#### 2. Terminal Initialization
```typescript
useEffect(() => {
  if (view === 'terminal' && user?.username === 'admin' && token) {
    // Create xterm instance
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#ffffff',
      },
      rows: 30,
      cols: 100,
    });

    // Connect WebSocket with JWT token
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal?token=${token}`;
    const ws = new WebSocket(wsUrl);

    // Bidirectional data flow
    ws.onmessage = (event) => term.write(event.data);
    term.onData((data) => ws.send(data));
  }
}, [view, user, token]);
```

---

## Problems Encountered

### 1. Backend Hanging (CRITICAL)

**Symptom**:
- Backend process started successfully
- WebSocket connection accepted
- Terminal displayed initial output (prompt)
- **User input not accepted** - terminal appeared frozen
- HTTP requests to backend timed out (504 Gateway Timeout)

**Manifestation**:
```
$ curl https://book.iotok.org/health
# Hangs for 60+ seconds, then returns:
HTTP/2 504 Gateway Timeout
```

**Log Evidence**:
```
INFO: WebSocket /ws/terminal?token=... [accepted]
INFO: connection open
# No further logs, process frozen
```

### 2. Non-blocking I/O Issues

**Attempts Made**:

#### Attempt 1: Direct read/write
```python
async def read_pty():
    while pty.isalive():
        output = pty.read(1024)  # BLOCKS indefinitely
        await websocket.send_text(output.decode('utf-8'))
```
**Result**: Deadlock - blocked entire event loop

#### Attempt 2: Using select.select()
```python
async def read_pty():
    loop = asyncio.get_event_loop()
    while pty.isalive():
        ready, _, _ = await loop.run_in_executor(None, select.select, [pty.fd], [], [], 0.01)
        if ready:
            output = await loop.run_in_executor(None, os.read, pty.fd, 1024)
            await websocket.send_text(output.decode('utf-8'))
```
**Result**: Backend still hung - likely threading issues with uvloop

#### Attempt 3: fcntl non-blocking
```python
import fcntl
fd = pty.fd
flags = fcntl.fcntl(fd, fcntl.F_GETFL)
fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
```
**Result**: OSError on read when no data available

---

## Root Cause Analysis

### Primary Issue: Event Loop Blocking

**The Problem**:
```
┌─────────────────────────────────────┐
│  FastAPI (uvicorn + uvloop)         │
│  Single-threaded async event loop   │
│                                      │
│  ┌────────────────────────────┐     │
│  │ HTTP Request Handler       │◄────┼─── Blocked waiting
│  │ (waiting for response)     │     │
│  └────────────────────────────┘     │
│                                      │
│  ┌────────────────────────────┐     │
│  │ WebSocket Terminal         │     │
│  │ select.select() call       │◄────┼─── Blocks in executor
│  │ (blocking in thread pool)  │     │
│  └────────────────────────────┘     │
│                                      │
└─────────────────────────────────────┘
```

**Why it blocks**:
1. `run_in_executor()` uses ThreadPoolExecutor (default)
2. Thread pool has limited workers (usually 1-5)
3. `select.select()` with PTY fd blocks the thread
4. Other async tasks starve waiting for thread pool
5. Eventually entire event loop freezes

### Secondary Issues

#### 1. PTY File Descriptor Complexity
- PTY is **not** a regular async-friendly file descriptor
- Doesn't work with asyncio's native add_reader/add_writer
- Requires special handling for buffering and line discipline

#### 2. uvloop vs asyncio Compatibility
- uvloop (used by uvicorn) has different threading behavior
- `loop.run_in_executor()` semantics differ from standard asyncio
- Race conditions in reader/writer coroutines

#### 3. WebSocket Connection Management
- WebSocket remained "open" even when backend frozen
- No timeout mechanism to detect hung PTY
- Difficult to recover without killing process

---

## Lessons Learned

### 🎓 Technical Lessons

1. **Async I/O ≠ Thread Pool Executor**
   - Don't use `run_in_executor()` for I/O-intensive blocking calls
   - Thread pool has limited workers - can exhaust quickly
   - Consider dedicated event loop or process instead

2. **PTY Requires Special Handling**
   - PTY file descriptors are **not** regular files
   - Cannot use standard async file I/O patterns
   - Need proper signal handling (SIGWINCH for resize, etc.)

3. **WebSocket + Long-Running Processes = Complex**
   - Need heartbeat/ping-pong to detect dead connections
   - Must handle process cleanup on disconnect
   - Timeout mechanisms essential

4. **FastAPI WebSocket Limitations**
   - Not designed for long-lived PTY connections
   - Better suited for short request/response patterns
   - Consider separate WebSocket server for complex cases

5. **Testing in Production is Dangerous**
   - Terminal hung entire backend (all HTTP endpoints)
   - Lost access to admin dashboard
   - Required SSH to manually kill process

### 💡 Architectural Lessons

1. **Separation of Concerns**
   - Terminal should be separate service/process
   - Don't mix web app logic with PTY management
   - Use IPC (Redis, message queue) for communication

2. **Graceful Degradation**
   - Should have kept terminal as optional feature
   - Backend should handle terminal service failure
   - Need circuit breaker pattern

3. **Security First**
   - Directory restriction via bash function is fragile
   - Can be bypassed with symlinks, `cd -P`, etc.
   - Need OS-level chroot or containers

---

## Skills & Techniques

### ✅ Skills Demonstrated

1. **WebSocket Programming**
   - Bidirectional real-time communication
   - Token-based authentication in query params
   - Proper connection lifecycle management

2. **Terminal Emulation**
   - xterm.js integration
   - ANSI escape code handling
   - Terminal resizing with FitAddon

3. **Process Management**
   - ptyprocess for pseudo-terminal spawning
   - Custom environment setup (bashrc)
   - Signal handling

4. **Async Programming**
   - FastAPI WebSocket handlers
   - asyncio.gather() for concurrent tasks
   - run_in_executor() for blocking I/O (learned limitations)

5. **Security Implementation**
   - JWT token validation in WebSocket
   - Directory restriction mechanisms
   - Admin-only access control

### 📚 Technologies Used

| Category | Technology | Purpose |
|----------|-----------|---------|
| Frontend Terminal | xterm.js (@xterm/xterm) | Browser-based terminal emulator |
| Terminal Addons | @xterm/addon-fit | Auto-resize terminal to container |
| Backend Framework | FastAPI | WebSocket endpoint |
| PTY Management | ptyprocess | Spawn pseudo-terminal |
| Async I/O | asyncio, select | Non-blocking I/O attempts |
| Authentication | JWT (python-jose) | Token verification |

---

## ⚠️ Critical Cautions

### 🚨 DO NOT Do These Things

1. **❌ DO NOT use `run_in_executor()` for continuous I/O loops**
   ```python
   # BAD - Will exhaust thread pool
   while True:
       data = await loop.run_in_executor(None, blocking_read)
   ```

2. **❌ DO NOT block the main event loop**
   ```python
   # BAD - Freezes entire FastAPI server
   output = pty.read(1024)  # Blocks
   ```

3. **❌ DO NOT mix PTY with standard async file I/O**
   ```python
   # BAD - PTY is not a regular file
   loop.add_reader(pty.fd, callback)  # Won't work correctly
   ```

4. **❌ DO NOT run long-lived processes in FastAPI handlers**
   ```python
   # BAD - Ties up worker, no timeout
   @app.websocket("/terminal")
   async def terminal():
       while True:  # Forever loop
           await process_pty()
   ```

5. **❌ DO NOT rely on bash function overrides for security**
   ```bash
   # INSECURE - Can be bypassed
   function cd() { ... }  # User can unset, use builtin cd, etc.
   ```

6. **❌ DO NOT test terminal features in production first**
   - **Always test locally** before deploying
   - Have fallback/rollback plan
   - Monitor for hangs in development

### ⚡ Performance Pitfalls

1. **Thread Pool Exhaustion**
   - Default ThreadPoolExecutor: 5-10 workers
   - One PTY can consume multiple workers
   - No workers left for other async tasks

2. **Memory Leaks**
   - Orphaned PTY processes
   - Unclosed file descriptors
   - Temp files not cleaned up (bashrc files)

3. **CPU Spinning**
   - Tight polling loops with `select()`
   - No proper sleep/backoff
   - High CPU even when idle

### 🔒 Security Risks

1. **Command Injection**
   - Even with directory restriction, can run any command
   - `curl`, `wget` can access external resources
   - `python` can bypass restrictions

2. **Resource Exhaustion**
   - User can run `:(){ :|:& };:` (fork bomb)
   - No CPU/memory limits enforced
   - Can DOS the entire server

3. **Information Disclosure**
   - Can read `/etc/passwd`, `/proc` files
   - Environment variables visible
   - Process list exposed via `ps`

4. **Privilege Escalation**
   - If backend runs as root (DON'T!)
   - Can modify system files
   - Install backdoors

---

## Future Solutions

### ✅ Recommended Approach

#### Option 1: Separate WebSocket Server (BEST)

**Architecture**:
```
┌──────────────┐      ┌──────────────────┐      ┌─────────────┐
│  FastAPI     │      │  Socket.IO       │      │  PTY        │
│  (Port 8086) │◄────►│  Terminal Server │◄────►│  Processes  │
│              │      │  (Port 8087)     │      │             │
└──────────────┘      └──────────────────┘      └─────────────┘
     │ HTTP                │ WebSocket               │
     │                     │                         │
     ▼                     ▼                         ▼
  Web UI              xterm.js                  bash shells
```

**Stack**:
- **node-pty** (Node.js) - Mature PTY library
- **Socket.IO** - Battle-tested WebSocket library
- **Express.js** - Simple HTTP server for health checks
- **Redis** - Share auth state between FastAPI and Terminal Server

**Benefits**:
- ✅ Isolation - Terminal crashes don't affect main app
- ✅ Scalability - Can run on separate machine
- ✅ Mature ecosystem - node-pty is production-ready
- ✅ Better async handling - Node.js event loop designed for I/O

**Example** (Node.js):
```javascript
const pty = require('node-pty');
const io = require('socket.io')(8087);

io.use(async (socket, next) => {
  // Verify JWT token with Redis
  const token = socket.handshake.auth.token;
  const user = await verifyToken(token);
  if (user && user.isAdmin) next();
  else next(new Error('Unauthorized'));
});

io.on('connection', (socket) => {
  const ptyProcess = pty.spawn('bash', [], {
    cwd: '/var/www/aibook',
    env: { ...process.env, RESTRICTED: '1' }
  });

  ptyProcess.onData((data) => socket.emit('output', data));
  socket.on('input', (data) => ptyProcess.write(data));
  socket.on('disconnect', () => ptyProcess.kill());
});
```

#### Option 2: Docker Container with gotty (SIMPLER)

**Gotty** - Turn CLI into web application

```bash
# Install gotty
wget https://github.com/sorenisanerd/gotty/releases/download/v1.5.0/gotty_linux_amd64.tar.gz

# Run with restrictions
gotty --port 8087 \
      --permit-write \
      --credential admin:<ADMIN_PASSWORD-from-backend/.env> \
      --title-format "BookMaker Terminal" \
      bash -c "cd /var/www/aibook && exec bash"
```

**Embed in iframe**:
```html
<iframe src="http://localhost:8087"
        width="100%"
        height="600px"
        style="border:none">
</iframe>
```

**Benefits**:
- ✅ Zero code - Just configure and run
- ✅ Built-in authentication
- ✅ Works out of the box
- ✅ Handles all PTY complexity

#### Option 3: SSH Gateway with Wetty

**Wetty** - SSH over HTTP/WebSocket

```bash
# Install
npm install -g wetty

# Run
wetty --port 8087 \
      --base / \
      --title "BookMaker Terminal" \
      --ssh-host localhost \
      --ssh-user bookmaker
```

**Benefits**:
- ✅ Uses real SSH (proven secure)
- ✅ All SSH features (key auth, forwarding)
- ✅ Audit logs via SSH
- ✅ Standard terminal behavior

#### Option 4: Execute Commands via API (SAFEST)

Instead of full terminal, provide specific command endpoints:

```python
@app.post("/api/admin/execute")
async def execute_command(
    command: str,
    cwd: str = "/var/www/aibook",
    admin: User = Depends(get_admin_user)
):
    # Whitelist allowed commands
    allowed_commands = ["ls", "claude", "git", "cat", "grep"]
    cmd_parts = shlex.split(command)

    if cmd_parts[0] not in allowed_commands:
        raise HTTPException(400, "Command not allowed")

    # Execute with timeout
    process = await asyncio.create_subprocess_exec(
        *cmd_parts,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=60.0
        )
        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": process.returncode
        }
    except asyncio.TimeoutError:
        process.kill()
        raise HTTPException(408, "Command timeout")
```

**Benefits**:
- ✅ No PTY complexity
- ✅ Easy to implement
- ✅ Timeout built-in
- ✅ Command whitelisting

---

## Code Artifacts

### Files Modified

1. **`backend/main.py`** - Terminal WebSocket endpoint (now removed)
2. **`backend/requirements.txt`** - Added ptyprocess, websockets
3. **`frontend/src/App.tsx`** - Terminal view and xterm.js integration
4. **`frontend/src/App.css`** - Terminal styling
5. **`frontend/package.json`** - Added @xterm/xterm, @xterm/addon-fit

### Temp Files Created (Need Cleanup)

```bash
# Bashrc temp files may still exist
ls /tmp/*.bashrc 2>/dev/null

# Clean up
rm /tmp/*.bashrc 2>/dev/null
```

### Current State (Post-Removal)

- Terminal code **commented out** in `main.py` (lines 670-806 deleted)
- Frontend terminal view **still exists** but won't connect
- Dependencies **still installed** in requirements.txt and package.json
- **Can be safely removed** or kept for future reimplementation

---

## References & Resources

### Documentation
- [xterm.js Documentation](https://xtermjs.org/)
- [ptyprocess Documentation](https://ptyprocess.readthedocs.io/)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [asyncio Event Loop](https://docs.python.org/3/library/asyncio-eventloop.html)

### Similar Projects
- [Wetty](https://github.com/butlerx/wetty) - Web-based SSH terminal
- [Gotty](https://github.com/sorenisanerd/gotty) - Share CLI as web application
- [ttyd](https://github.com/tsl0922/ttyd) - Share terminal over web
- [Butterfly](https://github.com/paradoxxxzero/butterfly) - Web terminal in Python (deprecated)

### Alternative Approaches
- [node-pty](https://github.com/microsoft/node-pty) - Node.js PTY bindings (VS Code uses this)
- [Paramiko](https://www.paramiko.org/) - Python SSH library
- [pexpect](https://pexpect.readthedocs.io/) - Python expect-like module

---

## Conclusion

### What Worked ✅
- JWT authentication in WebSocket
- xterm.js frontend integration
- Basic PTY spawning
- Directory restriction concept (bash function override)

### What Failed ❌
- Non-blocking PTY I/O in FastAPI async context
- Thread pool executor for continuous I/O
- Backend stability under PTY load

### Key Takeaway 💡

**Web-based terminals are deceptively complex**. While the frontend (xterm.js) is straightforward, the backend PTY management requires:
- Deep understanding of async I/O
- Proper process isolation
- Robust error handling
- Security hardening

**For production use**, leverage existing battle-tested solutions (Gotty, Wetty, node-pty) rather than building from scratch unless you have specific requirements and expertise in:
- Low-level Linux PTY/TTY subsystem
- Async I/O event loops (select, epoll, kqueue)
- Signal handling (SIGWINCH, SIGCHLD)
- Terminal escape sequences

**The juice wasn't worth the squeeze** for our use case. Consider simpler alternatives like command whitelisting API or embedded Gotty/Wetty.

---

**Document Version**: 1.0
**Last Updated**: January 29, 2026
**Author**: Claude Code Implementation Team
**Status**: Archived - Feature Disabled
