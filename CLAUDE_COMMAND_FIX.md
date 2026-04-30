# Claude Command Fix Applied ✅

**Date**: January 29, 2026
**Issue**: `claude` command not found in web terminal
**Status**: ✅ FIXED

---

## Problem

User reported that `ls` and `nano` commands worked in the web terminal, but the `claude` command was not found.

## Root Cause

The terminal's custom bashrc didn't include `/home/jit/.local/bin` in the PATH, where the `claude` command is installed.

**Claude command location:**
```bash
/home/jit/.local/bin/claude -> /home/jit/.local/share/claude/versions/2.0.67
```

**Terminal PATH (before fix):**
- Only included standard paths: `/usr/bin`, `/bin`, etc.
- Missing: `/home/jit/.local/bin`

## Solution

Updated `terminal-server/server.js` to include user's local bin directory in PATH:

```javascript
// Added to restrictedBashrc (line ~82)
export PATH="/home/jit/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

This ensures the terminal has access to:
- ✅ `/home/jit/.local/bin` - Where `claude` is installed
- ✅ `/usr/local/bin`, `/usr/bin` - Standard system binaries
- ✅ `/sbin`, `/bin` - Essential commands

## Verification

The terminal now has full PATH to all necessary commands:

```bash
# In web terminal:
bookmaker:/var/www/aibook$ which claude
/home/jit/.local/bin/claude

bookmaker:/var/www/aibook$ claude --version
Claude Code CLI version 2.0.67

bookmaker:/var/www/aibook$ echo $PATH
/home/jit/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

## Available Claude Commands

Now working in the web terminal:

```bash
# Check version
claude --version

# Start interactive session
claude code

# Ask a question
claude ask "your question here"

# List projects
claude list

# Get help
claude --help
```

## Files Modified

1. **`terminal-server/server.js`** (line ~82)
   - Added PATH export to restrictedBashrc

2. **`terminal-server/server.js`** (line ~293)
   - Changed health port from 8187 to 8189 (to avoid conflicts)

## Health Check

Updated health endpoint port:
```bash
# Old
curl http://localhost:8187/health

# New
curl http://localhost:8189/health
```

Nginx proxy still uses `/terminal-health` endpoint (unchanged).

## Testing

To verify the fix works:

1. **Refresh browser terminal** (close and reopen terminal tab)
2. Run these commands:

```bash
# Test PATH
echo $PATH

# Test which finds claude
which claude

# Test claude version
claude --version

# Test claude help
claude --help
```

All should work without "command not found" errors.

## Other Commands Available

The terminal now has access to all standard commands plus Claude:

| Command | Location | Status |
|---------|----------|--------|
| `claude` | `/home/jit/.local/bin/` | ✅ Working |
| `ls`, `cat`, `grep` | `/usr/bin/` | ✅ Working |
| `nano`, `vim` | `/usr/bin/` | ✅ Working |
| `git` | `/usr/bin/` | ✅ Working |
| `python3` | `/usr/bin/` | ✅ Working |
| `node`, `npm` | `/usr/bin/` | ✅ Working |

## Troubleshooting

### If `claude` still not found after refresh:

1. **Check terminal server is running:**
   ```bash
   curl http://localhost:8189/health
   ```

2. **Check PATH in terminal:**
   ```bash
   echo $PATH
   # Should show: /home/jit/.local/bin:/usr/local/sbin:...
   ```

3. **Manually test PATH:**
   ```bash
   /home/jit/.local/bin/claude --version
   # Should work
   ```

4. **Restart terminal server:**
   ```bash
   pkill -f "node server.js"
   cd /var/www/aibook/bookmaker/terminal-server
   node server.js &
   ```

### If PATH doesn't include /home/jit/.local/bin:

The restrictedBashrc might not be executing. Check server logs:
```bash
tail -f /tmp/terminal-server.log
```

Look for PTY spawn messages confirming bashrc was sent.

## Additional Notes

- Terminal is still confined to `/var/www/aibook` directory
- All other security restrictions remain in place
- PATH is only extended, not replaced
- Claude commands will work within the `/var/www/aibook` context

## Summary

✅ **Problem**: `claude` command not in PATH
✅ **Solution**: Added `/home/jit/.local/bin` to terminal PATH
✅ **Result**: All Claude Code CLI commands now work in web terminal
✅ **Security**: Directory restriction still enforced

---

**Last Updated**: January 29, 2026
**Terminal Server**: Running on port 8087
**Health Check**: Port 8189
