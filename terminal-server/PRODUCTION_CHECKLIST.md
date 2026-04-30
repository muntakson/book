# Production Deployment Checklist

## ✅ Pre-Deployment

- [x] Node.js dependencies installed (`npm install`)
- [x] Frontend dependencies installed (`npm install socket.io-client`)
- [x] `.env` file configured with SECRET_KEY
- [x] Terminal server tested locally
- [x] Health check endpoint responding

## 🔧 Nginx Configuration

Add to `/etc/nginx/sites-available/book.iotok.org`:

```nginx
# Terminal WebSocket proxy
location /socket.io/ {
    proxy_pass http://127.0.0.1:8087;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Long timeouts for terminal sessions
    proxy_connect_timeout 7d;
    proxy_send_timeout 7d;
    proxy_read_timeout 7d;
}

# Terminal health check
location /terminal-health {
    proxy_pass http://127.0.0.1:8187/health;
    access_log off;
}
```

Then:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 🎯 Systemd Service Setup

```bash
# Copy service file
sudo cp terminal-server.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable terminal-server

# Start service
sudo systemctl start terminal-server

# Check status
sudo systemctl status terminal-server
```

## 🏗️ Build Frontend

```bash
cd /var/www/aibook/bookmaker/frontend
npm run build
```

This rebuilds the React app with the new Socket.IO client code.

## 🔥 Restart Backend

```bash
sudo systemctl restart bookmaker
# or
sudo systemctl restart uvicorn@bookmaker
# (depending on your service name)
```

## 🧪 Testing

### 1. Test Terminal Server Directly

```bash
curl http://localhost:8187/health
```

Expected:
```json
{
  "status": "healthy",
  "service": "terminal-server",
  "connections": 0,
  "uptime": 123.45
}
```

### 2. Test Through Nginx

```bash
curl https://book.iotok.org/terminal-health
```

Should return same JSON.

### 3. Test WebSocket Connection

From browser console (after logging in):
```javascript
const socket = io('https://book.iotok.org', {
  auth: { token: localStorage.getItem('token') }
});

socket.on('connect', () => console.log('Connected:', socket.id));
socket.on('connect_error', (err) => console.error('Error:', err.message));
```

### 4. Full End-to-End Test

1. Go to https://book.iotok.org
2. Login as `admin` / `q1`
3. Click "Admin Dashboard"
4. Click "Terminal" tab
5. Wait for connection message
6. Type `pwd` and press Enter
7. Should show: `/var/www/aibook`
8. Type `ls -la` to list files
9. Try `cd bookmaker` (should work)
10. Try `cd /etc` (should be blocked)

## 🔍 Monitoring

### Check Logs

```bash
# Terminal server logs
sudo journalctl -u terminal-server -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log | grep socket.io

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Check Processes

```bash
# Terminal server process
ps aux | grep "node server.js"

# Active PTY processes (when users connected)
ps aux | grep bash | grep /var/www/aibook
```

### Check Resources

```bash
# Memory usage
top -p $(pgrep -f "node server.js")

# Open connections
netstat -an | grep 8087
```

## 🚨 Troubleshooting

### Terminal Won't Connect

**Symptom**: "Connection failed" in browser

**Checks**:
```bash
# 1. Is server running?
sudo systemctl status terminal-server

# 2. Is port open?
netstat -tuln | grep 8087

# 3. Check logs
sudo journalctl -u terminal-server -n 50

# 4. Test directly
curl http://localhost:8187/health
```

### Authentication Errors

**Symptom**: "Authentication required" or "Admin access required"

**Fix**:
```bash
# Verify SECRET_KEY matches
diff <(grep SECRET_KEY backend/.env) <(grep SECRET_KEY terminal-server/.env)

# If different, copy from backend
cd terminal-server
echo "SECRET_KEY=$(grep SECRET_KEY ../backend/.env | cut -d= -f2)" >> .env

# Restart
sudo systemctl restart terminal-server
```

### High Memory Usage

**Symptom**: Terminal server using >500 MB RAM

**Cause**: Multiple PTY processes not cleaned up

**Fix**:
```bash
# Check for orphaned processes
ps aux | grep bash | grep /var/www/aibook

# Kill orphans
pkill -f "bash.*var/www/aibook"

# Restart server
sudo systemctl restart terminal-server
```

### Backpressure Issues

**Symptom**: Terminal freezes during large output (e.g., `cat large-file.txt`)

**Check logs** for:
```
⚠️  Socket buffer full (xxxxx bytes), pausing PTY
✅ Socket buffer drained, resuming PTY
```

If you see "pausing" but never "resuming", there's a bug. Report this!

## 🔐 Security Hardening

### Optional: Docker Container

For stronger isolation, run terminal server in Docker:

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY server.js .
EXPOSE 8087
CMD ["node", "server.js"]
```

### Optional: Command Whitelisting

Edit `server.js` to restrict commands:

```javascript
const ALLOWED_COMMANDS = ['ls', 'cat', 'grep', 'claude', 'git', 'npm'];

socket.on('input', (data) => {
  const cmd = data.trim().split(' ')[0];
  if (!ALLOWED_COMMANDS.includes(cmd)) {
    socket.emit('output', `\r\n⛔ Command not allowed: ${cmd}\r\n`);
    return;
  }
  ptyProcess.write(data);
});
```

## 📊 Performance Tuning

### Increase File Descriptor Limit

If supporting many concurrent terminals:

```bash
# Edit systemd service
sudo systemctl edit terminal-server

# Add:
[Service]
LimitNOFILE=65536

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart terminal-server
```

### Adjust Node.js Memory

For high load:

```bash
# Edit start.sh or systemd service
node --max-old-space-size=512 server.js
```

## ✅ Post-Deployment Verification

- [ ] Terminal server running as systemd service
- [ ] Nginx proxy configured and tested
- [ ] Frontend rebuilt and deployed
- [ ] Backend restarted
- [ ] Health check responding through Nginx
- [ ] Can login and access terminal
- [ ] Directory confinement working
- [ ] Logs show no errors
- [ ] Auto-restart enabled (systemd)
- [ ] Monitoring in place

## 🎉 Success Criteria

✅ Admin can access terminal from browser
✅ Terminal restricted to `/var/www/aibook`
✅ No hanging or freezing with large output
✅ Connections auto-cleanup on disconnect
✅ Health check returns "healthy"
✅ Logs show normal operation
✅ Service auto-restarts on failure

## 📞 Support

If issues persist:

1. Check `TERMINAL_IMPLEMENTATION.md` for detailed architecture
2. Review `WEB_TERMINAL_LESSONS.md` for common pitfalls
3. Check systemd logs: `sudo journalctl -u terminal-server -n 100`
4. Verify all dependencies installed
5. Test with `curl` and browser console

---

**Last Updated**: January 29, 2026
**Status**: Production Ready ✅
