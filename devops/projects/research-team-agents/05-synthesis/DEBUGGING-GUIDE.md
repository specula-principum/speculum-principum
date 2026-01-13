# Synthesis Agent Debugging Guide

**Issue:** Synthesis returns no pending entities for People despite having extracted data.

---

## Root Cause Analysis

### Potential Issue #1: Fallback JSON Parsing Bug ✅ FIXED

**Problem:** The fallback code that reads JSON files directly was only handling simple list format:

```python
# BEFORE (broken for ExtractedPeople format)
if isinstance(data, list):
    entity_list = data
```

**Fix:** Now handles both formats:

```python
# AFTER (handles both formats)
if isinstance(data, list):
    # Simple list format (backward compatibility)
    entity_list = data
elif isinstance(data, dict):
    # ExtractedPeople/Organizations/Concepts format
    if entity_type == "Person" and "people" in data:
        entity_list = data["people"]
    elif entity_type == "Organization" and "organizations" in data:
        entity_list = data["organizations"]
    elif entity_type == "Concept" and "concepts" in data:
        entity_list = data["concepts"]
```

### Potential Issue #2: Silent Error Swallowing

**Problem:** Bare `except Exception:` blocks were swallowing errors without logging, making debugging impossible.

**Fix:** Added comprehensive logging to show:
- What files are being scanned
- Whether primary or fallback loading is used
- Any errors encountered
- How many entities are found in each file

---

## Enhanced Logging

When synthesis runs now, you'll see detailed output like this:

```
🔍 Scanning Person directory: /path/to/knowledge-graph/people

  ✓ Loaded abc123def456... via KnowledgeGraphStorage: 5 entities
  ⚠ KnowledgeGraphStorage failed for 789ghi012...: KeyError
  ✓ Loaded 789ghi012... from dict['people']: 3 entities
  ✗ Unrecognized dict format for jkl345mno...: keys=['data', 'timestamp']
  ✗ Fallback failed for pqr678stu...: JSONDecodeError: Expecting value: line 1 column 1 (char 0)

📊 Summary for Person:
   Total pending entities: 8
   Existing aliases in canonical store: 0
   Sample pending entities:
     • John Smith (from abc123def456...)
     • Jane Doe (from abc123def456...)
     • Bob Johnson (from 789ghi012...)
```

This will help identify:
- ✅ Files that load successfully
- ⚠️ Files that need fallback parsing (possible format issues)
- ✗ Files that fail completely (malformed JSON, unexpected format)

---

## How to Use This for Debugging

### Step 1: Run Synthesis Manually

```bash
cd /path/to/your/repo
source .venv/bin/activate

# Run synthesis for People
python main.py synthesis run-batch \
  --entity-type Person \
  --batch-size 50 \
  --model gpt-4o-mini
```

### Step 2: Check the Logs

Look for the `🔍 Scanning` section in the output. This will show:

1. **How many files are found** - If 0, the directory is empty or files are elsewhere
2. **Which files load successfully** - `✓ Loaded ...`
3. **Which files fail** - `✗ ...` with error details
4. **Total pending count** - If 0, all entities are already in canonical store

### Step 3: Diagnose Based on Output

| Scenario | Diagnosis | Solution |
|----------|-----------|----------|
| **Directory not found** | `knowledge-graph/people/` doesn't exist | Run extraction first |
| **No files in directory** | No `*.json` files | Run extraction first |
| **Files found, all fail to load** | JSON format mismatch | Check file format below |
| **Files load, 0 pending** | All entities already resolved | Check `knowledge-graph/canonical/alias-map.json` |
| **Files load, some entities skipped** | Entities already in alias map | Normal - only new entities are synthesized |

---

## Expected File Formats

### Format 1: ExtractedPeople Object (Current Standard)

```json
{
  "source_checksum": "abc123...",
  "people": [
    "John Smith",
    "Jane Doe",
    "Bob Johnson"
  ],
  "extracted_at": "2026-01-12T10:30:00+00:00",
  "metadata": {}
}
```

**Status:** ✅ Supported (primary path via `KnowledgeGraphStorage.get_extracted_people()`)

### Format 2: Simple List (Legacy/Tests)

```json
[
  "John Smith",
  "Jane Doe",
  "Bob Johnson"
]
```

**Status:** ✅ Supported (fallback path)

### Format 3: Unrecognized Dict

```json
{
  "data": ["John Smith"],
  "source": "abc123..."
}
```

**Status:** ❌ Not supported - will fail with "Unrecognized dict format"

---

## Common Issues

### Issue: "Total pending entities: 0" but files exist

**Possible Causes:**

1. **All entities already in canonical store**
   - Check `knowledge-graph/canonical/alias-map.json`
   - Search for normalized names (lowercase, collapsed spaces)
   - Example: "John Smith" → "john smith" in alias map

2. **Empty entity lists**
   - Files exist but `people` array is empty: `{"people": []}`
   - Check extraction logs to see why extraction returned no results

3. **JSON format mismatch**
   - Check logs for "Unrecognized dict format" or "Fallback failed"
   - Inspect file manually: `cat knowledge-graph/people/abc123.json | jq`

### Issue: "Unrecognized dict format"

**Diagnosis:** JSON is a dict but doesn't have expected fields.

**Solution:** 
1. Check the actual file format
2. If it's a valid custom format, update the fallback code
3. Or re-run extraction to regenerate files in correct format

### Issue: All files fail to load

**Diagnosis:** JSON is malformed or encoding issues.

**Solution:**
1. Check file encoding: `file knowledge-graph/people/*.json`
2. Validate JSON: `jq empty knowledge-graph/people/*.json`
3. Look for BOM or special characters
4. Re-run extraction if files are corrupted

---

## Verification Steps

### 1. Check extraction files exist

```bash
ls -lh knowledge-graph/people/
# Should show *.json files
```

### 2. Inspect a sample file

```bash
cat knowledge-graph/people/abc123.json | jq .
```

Expected output:
```json
{
  "source_checksum": "abc123...",
  "people": ["Name 1", "Name 2"],
  "extracted_at": "...",
  "metadata": {}
}
```

### 3. Check canonical store

```bash
cat knowledge-graph/canonical/alias-map.json | jq '.by_type.Person'
```

This shows which people are already resolved.

### 4. Run synthesis with logs

```bash
python main.py synthesis run-batch --entity-type Person 2>&1 | grep -A 20 "🔍 Scanning"
```

This will show the detailed scanning and loading process.

---

## Next Steps

If the enhanced logging still doesn't reveal the issue:

1. **Capture full logs** - Run with `2>&1 | tee synthesis-debug.log`
2. **Share sample file** - Provide a sanitized example of a failing JSON file
3. **Check Python version** - Ensure Python 3.10+ is being used
4. **Verify dependencies** - Run `pip install -r requirements.txt` to ensure packages are up to date

---

**File Modified:** `src/orchestration/toolkit/synthesis.py`  
**Changes:**
- Fixed fallback JSON parsing to handle dict format
- Added comprehensive debug logging
- Added summary output showing counts and samples

**Status:** Ready for testing with real data
