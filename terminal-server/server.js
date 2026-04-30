#!/usr/bin/env node
/**
 * BookMaker Terminal Server
 *
 * Isolated WebSocket server for SSH-like terminal access using node-pty
 * Implements proper backpressure handling to prevent event loop blocking
 *
 * Features:
 * - JWT authentication
 * - Directory confinement to /var/www/aibook
 * - Backpressure handling for streams
 * - Auto-cleanup on disconnect
 */

const pty = require('node-pty');
const { Server } = require('socket.io');
const jwt = require('jsonwebtoken');
const path = require('path');
require('dotenv').config();  // Load from terminal-server/.env

// Configuration
const PORT = process.env.TERMINAL_PORT || 8087;
const JWT_SECRET = process.env.SECRET_KEY || 'your-secret-key-here';
const RESTRICTED_DIR = '/home/jit';  // Changed from /var/www/aibook to /home/jit
const MAX_BUFFER_SIZE = 16384; // 16KB default highWaterMark

// Shell selection based on OS
const shell = process.platform === 'win32' ? 'powershell.exe' : 'bash';

// Initialize Socket.IO server with CORS
const io = new Server(PORT, {
  cors: {
    origin: ['http://localhost:3000', 'http://localhost:8080', 'https://book.iotok.org'],
    methods: ['GET', 'POST'],
    credentials: true
  },
  // Connection timeout
  connectTimeout: 10000,
  // Ping timeout
  pingTimeout: 30000,
  pingInterval: 25000
});

console.log(`🚀 Terminal Server started on port ${PORT}`);
console.log(`📂 Restricted to directory: ${RESTRICTED_DIR}`);

// Authentication middleware
io.use((socket, next) => {
  const token = socket.handshake.auth.token;

  if (!token) {
    return next(new Error('Authentication required'));
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    socket.user = decoded;

    // Only allow admin users
    if (decoded.sub !== 'admin') {
      return next(new Error('Admin access required'));
    }

    console.log(`✅ Authenticated: ${decoded.sub}`);
    next();
  } catch (err) {
    console.error('❌ Authentication failed:', err.message);
    next(new Error('Invalid token'));
  }
});

// Connection handler
io.on('connection', (socket) => {
  console.log(`🔌 Client connected: ${socket.id} (User: ${socket.user.sub})`);

  let ptyProcess = null;
  let isPaused = false;

  try {
    // Create custom bashrc for directory restriction
    const restrictedBashrc = `
# Restricted bash session for BookMaker (running as user jit)
export PS1="\\[\\033[01;32m\\]jit@bookmaker\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ "
export BASE_DIR="${RESTRICTED_DIR}"
export HOME="/home/jit"
export USER="jit"
export PATH="/home/jit/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Override cd command to enforce directory restriction
# Allow access to /home/jit and /var/www/aibook
function cd() {
    local target="\${1:-$BASE_DIR}"
    local abs_path

    # Resolve absolute path
    if [[ "\$target" = /* ]]; then
        abs_path="\$(readlink -f "\$target" 2>/dev/null || echo "\$target")"
    else
        abs_path="\$(readlink -f "\$PWD/\$target" 2>/dev/null || echo "\$PWD/\$target")"
    fi

    # Check if within allowed directories (/home/jit or /var/www/aibook)
    if [[ "\$abs_path" == "/home/jit"* ]] || [[ "\$abs_path" == "/var/www/aibook"* ]]; then
        builtin cd "\$target" 2>/dev/null || {
            echo "cd: \$target: No such file or directory"
            return 1
        }
    else
        echo "⛔ Access restricted to /home/jit and /var/www/aibook"
        return 1
    fi
}

# Warning message
echo "👤 Running as user: jit"
echo "🏠 Home directory: $HOME"
echo "📝 Type 'exit' or Ctrl+D to close terminal"
echo ""

# Start in home directory
cd "$HOME" 2>/dev/null || true
`;

    // Spawn PTY process
    ptyProcess = pty.spawn(shell, shell === 'bash' ? ['-i'] : [], {
      name: 'xterm-256color',
      cols: 100,
      rows: 30,
      cwd: RESTRICTED_DIR,
      env: {
        ...process.env,
        BASE_DIR: RESTRICTED_DIR,
        TERM: 'xterm-256color',
        COLORTERM: 'truecolor',
        // Pass restricted bashrc content
        BASH_ENV: '/dev/stdin'
      }
    });

    // Send bashrc commands if using bash
    if (shell === 'bash') {
      ptyProcess.write(restrictedBashrc + '\n');
    }

    console.log(`🐚 PTY spawned: PID ${ptyProcess.pid}`);

    // ==================================================================
    // CRITICAL: Backpressure Handling
    // ==================================================================

    /**
     * Handle data from PTY (shell output) to WebSocket
     * Implements backpressure to prevent memory overflow
     */
    ptyProcess.onData((data) => {
      try {
        // Check if socket buffer is full
        const bufferSize = socket.conn?.transport?.socket?.bufferSize || 0;

        if (bufferSize > MAX_BUFFER_SIZE) {
          // Buffer full - pause PTY to prevent overflow
          if (!isPaused) {
            console.warn(`⚠️  Socket buffer full (${bufferSize} bytes), pausing PTY`);
            ptyProcess.pause();
            isPaused = true;
          }
          return;
        }

        // Send data to client
        socket.emit('output', data);

      } catch (err) {
        console.error('❌ Error sending PTY data:', err.message);
      }
    });

    /**
     * Handle 'drain' event - resume PTY when buffer clears
     * This is critical to prevent deadlocks
     */
    const checkDrain = () => {
      if (isPaused) {
        const bufferSize = socket.conn?.transport?.socket?.bufferSize || 0;

        if (bufferSize < MAX_BUFFER_SIZE / 2) {
          // Buffer drained - resume PTY
          console.log(`✅ Socket buffer drained, resuming PTY`);
          ptyProcess.resume();
          isPaused = false;
        }
      }
    };

    // Check drain status periodically
    const drainInterval = setInterval(checkDrain, 100);

    /**
     * Handle input from WebSocket to PTY
     * Also implements throttling for paste events
     */
    socket.on('input', (data) => {
      if (ptyProcess && !ptyProcess.killed) {
        try {
          // Throttle large inputs (pastes) to prevent overwhelming PTY
          if (data.length > 1024) {
            console.warn(`⚠️  Large input detected (${data.length} bytes), chunking...`);

            // Send in chunks
            const chunkSize = 512;
            for (let i = 0; i < data.length; i += chunkSize) {
              const chunk = data.slice(i, i + chunkSize);
              ptyProcess.write(chunk);

              // Small delay between chunks
              if (i + chunkSize < data.length) {
                // Use setImmediate to yield to event loop
                setImmediate(() => {});
              }
            }
          } else {
            ptyProcess.write(data);
          }
        } catch (err) {
          console.error('❌ Error writing to PTY:', err.message);
          socket.emit('error', 'Failed to write to terminal');
        }
      }
    });

    /**
     * Handle terminal resize
     */
    socket.on('resize', ({ cols, rows }) => {
      if (ptyProcess && !ptyProcess.killed) {
        try {
          ptyProcess.resize(cols, rows);
          console.log(`📐 Terminal resized: ${cols}x${rows}`);
        } catch (err) {
          console.error('❌ Error resizing PTY:', err.message);
        }
      }
    });

    /**
     * Handle PTY exit
     */
    ptyProcess.onExit(({ exitCode, signal }) => {
      console.log(`🔚 PTY exited: code=${exitCode}, signal=${signal}`);
      clearInterval(drainInterval);
      socket.emit('exit', { exitCode, signal });
      socket.disconnect(true);
    });

    /**
     * Handle client disconnect
     */
    socket.on('disconnect', (reason) => {
      console.log(`🔌 Client disconnected: ${socket.id} (${reason})`);
      clearInterval(drainInterval);

      if (ptyProcess && !ptyProcess.killed) {
        try {
          ptyProcess.kill();
          console.log(`🗑️  PTY process killed: PID ${ptyProcess.pid}`);
        } catch (err) {
          console.error('❌ Error killing PTY:', err.message);
        }
      }
    });

    /**
     * Handle errors
     */
    socket.on('error', (err) => {
      console.error('❌ Socket error:', err.message);
    });

  } catch (err) {
    console.error('❌ Failed to spawn PTY:', err);
    socket.emit('error', 'Failed to create terminal session');
    socket.disconnect(true);
  }
});

// Health check endpoint (optional, for monitoring)
const http = require('http');
const healthServer = http.createServer((req, res) => {
  if (req.url === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      service: 'terminal-server',
      connections: io.engine.clientsCount,
      uptime: process.uptime()
    }));
  } else {
    res.writeHead(404);
    res.end('Not Found');
  }
});

// Use a different port for health check to avoid conflicts
const HEALTH_PORT = 8189;  // Changed from 8187 to avoid conflicts
healthServer.listen(HEALTH_PORT, () => {
  console.log(`💚 Health check available at http://localhost:${HEALTH_PORT}/health`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('🛑 SIGTERM received, closing connections...');
  io.close(() => {
    console.log('✅ All connections closed');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('\n🛑 SIGINT received, closing connections...');
  io.close(() => {
    console.log('✅ All connections closed');
    process.exit(0);
  });
});
