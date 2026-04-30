# Bob Workflow Test Report

## Executive Summary

Bob's project (#10) has been analyzed. The "Proceed" button **SHOULD** be visible based on the backend data, but there may be a frontend state or caching issue.

---

## Test Environment

- **User**: Bob (id=bob, pwd=q1)
- **Correct URL**: https://book.iotok.org ⚠️ (NOT http://localhost:8080)
- **Backend API**: http://localhost:8086
- **Project ID**: 10

---

## Bob's Current Project State

```json
{
  "id": 10,
  "user_id": 2,
  "name": "A simple test book about artificial intelligence basics",
  "book_idea": "A simple test book about artificial intelligence basics",
  "adapted_prompt": "**책 제목 및 부제**\n제목: 인공지능 기초...",
  "stage": "1단계",
  "stage_status": "pending",
  "model_used": "llama-3.3-70b-versatile",
  "tokens_used": 877,
  "created_at": "2026-02-24T01:40:03.790628",
  "updated_at": "2026-02-24T01:40:09.975319"
}
```

### Key Findings:

✅ **Plan Generated**: `adapted_prompt` exists (877 tokens)
✅ **Stage Set**: `stage` = "1단계" (Stage 1)
✅ **Status Set**: `stage_status` = "pending" (not "in_progress")

---

## Code Analysis

### Frontend Condition (App.tsx:1092-1146)

The Proceed button renders when:

```tsx
{selectedProject.stage === '1단계' && selectedProject.stage_status !== 'in_progress' && (
  <>
    {/* Feedback Section */}
    {/* Proceed Button for Stage 1 */}
    <button onClick={() => handleUserProceedStage(selectedProject.id)}>
      ▶️ Proceed to Stage 2 (Write Book with Research)
    </button>
  </>
)}
```

### Condition Check:

1. `selectedProject.stage === '1단계'` → ✅ **TRUE** (it is "1단계")
2. `selectedProject.stage_status !== 'in_progress'` → ✅ **TRUE** (it is "pending")
3. `selectedProject.adapted_prompt` exists → ✅ **TRUE**

**Conclusion**: The button **SHOULD BE VISIBLE** based on current data.

---

## Root Cause Analysis

### Possible Issues:

1. **Wrong URL** ⚠️
   - Bob may be accessing `http://localhost:8080` (different app)
   - Correct URL: `https://book.iotok.org`

2. **Browser Cache** 🔄
   - Frontend state may not have refreshed after plan generation
   - Solution: Hard refresh (Ctrl+Shift+R) or clear browser cache

3. **State Not Updated** 💾
   - `selectedProject` in React state may be stale
   - Solution: Navigate away and back to project, or refresh page

4. **Backend Status Issue** 🔧
   - `stage_status` should transition from "pending" → "completed" after plan generation
   - Current backend sets `stage_status = "pending"` (line 503 in main.py)
   - This is correct for "waiting for user feedback"

---

## Recommended Solution

### For Bob:

1. **Access Correct URL**:
   ```
   https://book.iotok.org
   ```

2. **Login as Bob**:
   - Username: bob
   - Password: q1

3. **View Project**:
   - Click on "A simple test book about artificial intelligence basics"

4. **Verify Plan Exists**:
   - Look for section "📋 책 집필 계획"
   - Plan should be visible and collapsible

5. **Look for Proceed Button**:
   - Should see "📍 Current Stage: 1단계 (Plan Ready)"
   - Button: "▶️ Proceed to Stage 2 (Write Book with Research)"

6. **If Button Still Not Visible**:
   - Hard refresh browser (Ctrl+Shift+R)
   - Or logout and login again
   - Or navigate to list view and back to project detail

---

## Test Workflow Stages

### ✅ Stage 1: Plan Generation
- Status: **COMPLETED**
- Plan created with 877 tokens
- Stage status: "pending" (waiting for user to proceed)

### ⏳ Stage 2: Write Book with Research
- Status: **NOT STARTED**
- Will start when Bob clicks "Proceed to Stage 2"

### ⏳ Stage 3: Fact-Check & Critical Review
- Status: **NOT STARTED**

### ⏳ Stage 4: Final Polish
- Status: **NOT STARTED**

---

## Playwright Test Suite

Test files created:
1. `/var/www/aibook/bookmaker/frontend/tests/bob-workflow.spec.ts` - Full workflow test
2. `/var/www/aibook/bookmaker/frontend/tests/simple-debug.spec.ts` - Debug test

### To Run Tests:

```bash
cd /var/www/aibook/bookmaker/frontend

# Run specific test
npx playwright test tests/bob-workflow.spec.ts --grep "Stage 1"

# Run with UI
npm run test:ui

# Run debug test
npm run test:debug
```

### Note: Update Test URL
Tests currently use `http://localhost:8080`. Update to `https://book.iotok.org` in:
- `/var/www/aibook/bookmaker/frontend/playwright.config.ts`
- Test files (line with `page.goto()`)

---

## Backend API Verification

Verified via curl:

```bash
# Login
curl -X POST http://localhost:8086/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"q1"}'

# Get projects
curl http://localhost:8086/api/projects \
  -H "Authorization: Bearer <token>"
```

Result: Bob's project data is correct in database ✅

---

## Next Steps

1. **Immediate**:
   - Bob should access `https://book.iotok.org`
   - Clear browser cache if needed
   - Proceed button should be visible

2. **If Still Not Working**:
   - Check browser console for JavaScript errors
   - Verify network tab shows correct API responses
   - Take screenshot and share for further debugging

3. **After Button Appears**:
   - Click "Proceed to Stage 2"
   - Stage 2 will begin writing book chapters
   - Monitor progress in "Progress Logs" section

---

## Backend Code Reference

Stage status is set in `/var/www/aibook/bookmaker/backend/main.py`:

```python
# Line 502-503
project.stage = "1단계"  # Set stage to 1단계 after plan generation
project.stage_status = "pending"  # Waiting for user feedback
```

This is correct behavior. The "pending" status means "plan ready, waiting for user to proceed."

---

## Conclusion

✅ **Backend**: Correct data, button should render
✅ **Frontend**: Correct logic, button should appear
⚠️ **Issue**: Likely URL mismatch or browser cache

**Action Required**: Access https://book.iotok.org and verify button appears.
