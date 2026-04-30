# Stage 3 Issue Resolution - Bob's Project

## Problem
Bob's project completed Stage 3 (fact-checking and critical review) successfully:
- Logs showed: "🎉 Stage 3 (Fact Check & Review) completed!" at 2:07:49 AM
- But frontend still showed: "⏳ Fact-checking and critical review in progress..."
- Proceed button was not visible

## Root Cause
**Timing + Caching Issue**

The fact-checking runs in a background thread (lines 780-785 in main.py):
```python
thread = threading.Thread(
    target=fact_check_and_review,
    args=(request.project_id, db.bind)
)
thread.daemon = True
thread.start()
```

The background thread:
1. Performs fact-checking (lines 1324-1377)
2. Updates `stage_status = "completed"` (line 1385)
3. Commits to database (line 1386)
4. Writes completion log (lines 1388-1390)

However, the **frontend may have cached the old `stage_status = "in_progress"` value** from before the background thread finished.

## Database Verification

**Before fix:**
```
Stage: 3단계
Status: in_progress ❌
```

**After waiting for background thread:**
```
Stage: 3단계
Status: completed ✅
```

## Solution

### For Bob (User):

**Just refresh the page!**

1. Go to https://book.iotok.org
2. Hard refresh browser:
   - **Windows/Linux**: Ctrl + Shift + R
   - **Mac**: Cmd + Shift + R
3. View project
4. The "▶️ Proceed to Stage 4" button should now appear

### Why This Works:
The hard refresh forces the browser to fetch fresh data from the backend, bypassing any cached `stage_status` value.

## Frontend Polling Solution (Future Enhancement)

To avoid this issue in the future, we could add automatic polling when `stage_status === "in_progress"`:

```typescript
// In App.tsx - automatically refresh project data every 3 seconds during processing
useEffect(() => {
  if (selectedProject?.stage_status === 'in_progress') {
    const interval = setInterval(async () => {
      // Fetch fresh project data
      const res = await fetch(`/api/projects/${selectedProject.id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const updatedProject = await res.json();
        setSelectedProject(updatedProject);
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }
}, [selectedProject?.stage_status]);
```

This would automatically detect when the backend finishes and update the UI without requiring a manual refresh.

## Verification Steps

After Bob refreshes the page, verify:

1. ✅ Stage badge shows "3단계"
2. ✅ Section header shows "📋 Fact-Check & Critical Review Report"
3. ✅ Review report is visible (formatted markdown)
4. ✅ Revision chatbox is visible
5. ✅ "▶️ Proceed to Stage 4 (Final Polish)" button appears

## Expected Stage 3 Completed UI

When Stage 3 is completed, Bob should see:

```
📋 Fact-Check & Critical Review Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Formatted markdown review report]

✏️ Make Revisions Based on Review
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use the review report above to improve your book.

[Chat history (if any)]

[Text input for revision requests]

[✍️ Revise Chapter button]

📍 Ready to Finalize?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When you're satisfied with all revisions, proceed to Stage 4.

[▶️ Proceed to Stage 4 (Final Polish) button]
```

## Next Steps After Proceeding to Stage 4

When Bob clicks "Proceed to Stage 4":
1. Confirmation dialog appears
2. Backend sets `stage = "4단계"` and `stage_status = "completed"`
3. UI shows completion message and all artifacts from Stages 1-4
4. Book creation process is complete!

## Conclusion

✅ **Issue Resolved**: Database has been updated correctly
✅ **Action Required**: Bob just needs to refresh the browser
✅ **Future Enhancement**: Add automatic polling for real-time updates
