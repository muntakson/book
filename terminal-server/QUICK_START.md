# Terminal Server - Quick Start Guide

## 🚀 Start the Server

```bash
cd /var/www/aibook/bookmaker/terminal-server
./start.sh
```

Or manually:
```bash
node server.js
```

## ✅ Verify It's Running

```bash
curl http://localhost:8187/health
```

Expected output:
```json
{
  "status": "healthy",
  "service": "terminal-server",
  "connections": 0,
  "uptime": 123.45
}
```

## 🌐 Access from Browser

1. Go to https://book.iotok.org
2. Login as **admin** (password: q1)
3. Click **Admin Dashboard**
4. Click **Terminal** tab

You should see:
```
Connecting to terminal server...
✓ Connected to terminal server
⚠️  Terminal restricted to: /var/www/aibook
📝 Type 'exit' or Ctrl+D to close terminal

bookmaker:/var/www/aibook$
```

## 🔧 Troubleshooting

### Port Already in Use

If you get `EADDRINUSE` error:

```bash
# Find what's using the port
lsof -i :8087

# Kill it
sudo kill -9 <PID>

# Or change port in .env
echo "TERMINAL_PORT=8090" >> .env
```

### Authentication Failed

Make sure `SECRET_KEY` matches backend:

```bash
# Copy from backend
grep SECRET_KEY ../backend/.env >> .env
```

### Can't Connect from Browser

Check Nginx configuration:

```bash
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```

## 🛑 Stop the Server

```bash
# If running manually
Ctrl+C

# If running as systemd service
sudo systemctl stop terminal-server
```

## 📊 Monitor Logs

```bash
# Manual run - check terminal output

# Systemd service
sudo journalctl -u terminal-server -f
```

## 🔐 Security Notes

- Only admin users can access terminal
- Terminal is restricted to `/var/www/aibook`
- Attempting `cd /etc` will be blocked
- JWT token required for authentication

## 📚 More Information

- **Full Documentation**: See `README.md`
- **Implementation Details**: See `../TERMINAL_IMPLEMENTATION.md`
- **Lessons Learned**: See `../WEB_TERMINAL_LESSONS.md`
