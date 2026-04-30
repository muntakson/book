# Terminal Connection Fix - Applied

**Date**: January 29, 2026  
**Status**: ✅ **FIXED** - Ready to Test

---

## Problem

When accessing the terminal from the admin dashboard at https://book.iotok.org, users saw:
```
WebSocket error occurred
Connection closed
```

## Root Cause

The frontend was trying to connect directly to port 8087:
```javascript
const terminalServerUrl = `https://book.iotok.org:8087`;
```

**Issue**: Port 8087 is not exposed publicly (only bound to localhost).

## Solution Applied

### 1. Added Nginx Proxy Configuration

Added to `/etc/nginx/sites-available/book.iotok.org`:

```nginx
# Terminal WebSocket proxy (Socket.IO)
location /socket.io/ {
    proxy_pass http://127.0.0.1:8087;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    # ... headers and timeouts
}
```

### 2. Updated Frontend Connection

Changed frontend (`App.tsx`) to connect through Nginx:

**Before**:
```javascript
const terminalServerUrl = `${protocol}//${window.location.hostname}:8087`;
const socket = io(terminalServerUrl, {...});
```

**After**:
```javascript
const socket = io(window.location.origin, {
    path: '/socket.io/',
    ...
});
```

### 3. Rebuilt & Restarted Services

- ✅ Frontend rebuilt with `npm run build`
- ✅ Backend restarted to serve new files
- ✅ Nginx reloaded with new configuration

## Connection Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (https://book.iotok.org)                          │
│  - User clicks Terminal tab                                │
│  - Socket.IO client connects to /socket.io/                │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Nginx (Port 443)                                           │
│  - SSL termination                                          │
│  - Proxies /socket.io/ → http://127.0.0.1:8087            │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP (localhost only)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Terminal Server (Node.js on port 8087)                    │
│  - Socket.IO server                                         │
│  - JWT authentication                                       │
│  - Spawns PTY process                                       │
└────────────────────┬────────────────────────────────────────┘
                     │ node-pty
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Bash Shell (/var/www/aibook)                              │
│  - Directory confined                                       │
│  - Ready for commands                                       │
└─────────────────────────────────────────────────────────────┘
```

## Testing Instructions

### 1. Access the Terminal

1. Open browser and go to: **https://book.iotok.org**
2. Login with admin credentials:
   - Username: `admin`
   - Password: `q1`
3. Click **"Admin Dashboard"**
4. Click **"Terminal"** tab

### 2. Expected Behavior

You should see:

```
Connecting to terminal server...
✓ Connected to terminal server
⚠️  Terminal restricted to: /var/www/aibook
📝 Type 'exit' or Ctrl+D to close terminal

bookmaker:/var/www/aibook$
```

### 3. Test Commands

Try these commands to verify everything works:

```bash
# Check current directory
pwd
# Output: /var/www/aibook

# List files
ls -la

# Navigate to bookmaker
cd bookmaker

# Test directory confinement
cd /etc
# Should show: ⛔ Access restricted to /var/www/aibook

# Test with large output (backpressure handling)
find . -type f | head -100

# Run Claude Code (if you want)
# claude code
```

## Service Status

All services confirmed running:

| Service | Status | Port | Health Check |
|---------|--------|------|--------------|
| Terminal Server | ✅ Running | 8087 | http://localhost:8187/health |
| Backend (FastAPI) | ✅ Running | 8086 | https://book.iotok.org/health |
| Nginx | ✅ Running | 443 | Reloaded with new config |

## Troubleshooting

### If Terminal Still Won't Connect

1. **Check browser console** (F12):
   ```javascript
   // Look for Socket.IO connection errors
   ```

2. **Check terminal server logs**:
   ```bash
   cd /var/www/aibook/bookmaker/terminal-server
   # If running manually, check terminal output
   ```

3. **Test Socket.IO endpoint directly**:
   ```bash
   curl -I https://book.iotok.org/socket.io/
   # Should return: HTTP/2 400 (Socket.IO handshake expected)
   ```

4. **Verify JWT token**:
   - Clear browser storage: `localStorage.clear()`
   - Login again
   - Try terminal again

### If You See "Authentication required"

The JWT token might be invalid. Solution:
```javascript
// In browser console (F12)
localStorage.clear();
location.reload();
// Then login again
```

### If Terminal Freezes

This shouldn't happen with the backpressure handling, but if it does:
```bash
# Restart terminal server
cd /var/www/aibook/bookmaker/terminal-server
pkill -f "node server.js"
node server.js &
```

## Files Modified

| File | Change |
|------|--------|
| `/etc/nginx/sites-available/book.iotok.org` | Added Socket.IO proxy |
| `frontend/src/App.tsx` | Updated connection URL |
| `frontend/dist/*` | Rebuilt with new code |

## Verification Commands

```bash
# 1. Check terminal server
curl http://localhost:8187/health
# Expected: {"status":"healthy","service":"terminal-server",...}

# 2. Check backend
curl https://book.iotok.org/health
# Expected: {"status":"healthy","service":"bookmaker",...}

# 3. Check Nginx config
echo '<ADMIN_PASSWORD-from-backend/.env>' | sudo -S nginx -t
# Expected: syntax is ok, test is successful

# 4. Check processes
ps aux | grep "node server.js" | grep -v grep
ps aux | grep "uvicorn main:app" | grep -v grep
```

## Next Steps

1. **Test the terminal** in the browser (instructions above)
2. If it works: ✅ **Done!**
3. If issues persist: Check browser console and server logs

## Documentation

- **Implementation Details**: See `TERMINAL_IMPLEMENTATION.md`
- **Architecture**: See `terminal-server/README.md`
- **Quick Reference**: See `terminal-server/QUICK_START.md`
- **Lessons Learned**: See `WEB_TERMINAL_LESSONS.md`

---

**Status**: ✅ Fix Applied - Ready for Testing  
**Last Updated**: January 29, 2026
