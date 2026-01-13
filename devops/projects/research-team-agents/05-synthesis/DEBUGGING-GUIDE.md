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

When synthesis runs now, you'll see detailed output in **two places**:

### 1. CLI Pre-Scan (Before synthesis starts)

This happens when you run `synthesis check` or `synthesis run-batch`:

```
🔍 DEBUG: _list_all_checksums for Person
   Directory people: 15 files
      Files: ['abc123def456...', '789ghi012jkl...', ...]
   Total unique checksums: 15

🔍 DEBUG: _gather_unresolved_entities for Person
   Found 15 checksum files
   Alias map has 0 existing Person aliases
   File abc123def456...: 5 entities, 5 unresolved
   File 789ghi012jkl...: 3 entities, 3 unresolved
   File mno345pqr678...: EMPTY (no entities extracted)
   File stu901vwx234...: 2 entities, 2 unresolved
   TOTAL unresolved: 10
```

**What to look for in pre-scan logs:**
- ✅ `Directory people: N files` - Shows JSON files are present
- ✅ `Found N checksum files` - Confirms files are being scanned
- ⚠️ `EMPTY (no entities extracted)` - File exists but has no people
- ✅ `X entities, Y unresolved` - Shows entities found and which are new
- ❌ `Directory people: 0 files` - **NO FILES FOUND - extraction hasn't run**

### 2. Synthesis Toolkit Scan (During synthesis)

This happens inside the agent when it calls `list_pending_entities`:

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

## Diagnosing "Person: All entities resolved ✓" with Zero Files

**Your exact error:**
```
Person: All entities resolved ✓
Total pending: 0

Found 0 unresolved Person entities
```

This means the CLI scan found **0 JSON files** in `knowledge-graph/people/`.

### Step-by-Step Diagnosis

**1. Verify files exist in the repo:**

```bash
# In your test repo (mirror-denver-broncos)
ls -lh knowledge-graph/people/ | head -20

# Count files
ls -1 knowledge-graph/people/*.json 2>/dev/null | wc -l
```

**Expected:** Should show multiple `.json` files  
**If 0:** Files don't exist - extraction hasn't run or failed

**2. Check if files are in a different location:**

```bash
# Search entire repo for extraction files
find . -type f -name "*.json" | grep -E "(people|organizations|concepts)" | head -20

# Check if evidence was parsed
ls -lh evidence/parsed/ | head -10
```

**3. Check extraction workflow status:**

Go to GitHub Actions → Check latest "Extraction: Process Document" workflow
- Did it complete successfully?
- Check logs for any errors
- Verify it committed files to `knowledge-graph/people/`

**4. Manually inspect a sample file (if files exist):**

```bash
# Pick first file
FILE=$(ls knowledge-graph/people/*.json | head -1)
echo "File: $FILE"

# Show file content
cat "$FILE" | jq .

# Expected format:
# {
#   "source_checksum": "abc123...",
#   "people": ["Person 1", "Person 2"],
#   "extracted_at": "...",
#   "metadata": {}
# }
```

### Most Likely Cause

Based on your logs showing **0 files found**, the issue is:

**❌ Extraction has not run on this repo yet**

OR

**❌ Extraction ran but failed silently without creating files**

### Solution

1. **Run extraction on source documents:**
   - Trigger extraction workflow manually, OR
   - Upload/commit source documents that trigger auto-extraction

2. **Verify extraction creates files:**
   ```bash
   # After extraction runs, check:
   ls -lh knowledge-graph/people/
   # Should show: abc123.json, def456.json, etc.
   ```

3. **Once files exist, re-run synthesis:**
   ```bash
   python main.py synthesis run-batch --entity-type Person
   ```

---

### Scenario: "N files found, many entities, but 0 unresolved"

**Your exact logs:**
```
Found 41 checksum files
Alias map has 50 existing Person aliases
File 360d4a657651...: 21 entities, 0 unresolved
File 8b21d1d86d7f...: 7 entities, 0 unresolved
TOTAL unresolved: 0
```

**Diagnosis:** ✅ **Synthesis already completed successfully!**

All extracted people are already in the canonical store. Nothing to do.

**Why this happens:**
- Extraction found people in 41 source files
- Previous synthesis run already resolved all of them
- They're now in `knowledge-graph/canonical/alias-map.json`
- Synthesis is idempotent - won't re-process already-resolved entities

**To verify synthesis worked:**

```bash
# Check canonical people entities
ls -lh knowledge-graph/canonical/people/
# Should show .json files for each resolved person

# Check alias map
cat knowledge-graph/canonical/alias-map.json | jq '.by_type.Person | length'
# Should show 50 (matches "Alias map has 50 existing Person aliases")

# View a sample canonical person
cat knowledge-graph/canonical/people/sean-payton.json | jq .
```

**Expected output:**
```json
{
  "canonical_id": "sean-payton",
  "canonical_name": "Sean Payton",
  "entity_type": "Person",
  "aliases": ["Sean Payton", "Head Coach Sean Payton"],
  "source_checksums": ["abc123...", "def456..."],
  "corroboration_score": 2,
  "attributes": {},
  "associations": [...],
  "metadata": {
    "synthesis_complete": true,
    "confidence": 0.95
  }
}
```

**If you want to re-run synthesis (force reprocessing):**

1. **Option A: Clear canonical store (nuclear option)**
   ```bash
   # ⚠️ WARNING: This deletes all synthesis work!
   rm -rf knowledge-graph/canonical/people/
   rm knowledge-graph/canonical/alias-map.json
   
   # Re-run synthesis
   python main.py synthesis run-batch --entity-type Person
   ```

2. **Option B: Remove specific entities from alias map**
   ```bash
   # Edit alias-map.json manually to remove specific people
   # Then re-run synthesis - those entities will be re-processed
   ```

3. **Option C: Process only new extractions**
   - Just run extraction on new documents
   - Synthesis will automatically pick up only the new entities
   - Already-resolved entities are skipped

---

## Common Issues

### Scenario: "Directory people: 0 files"

**Diagnosis:** The `knowledge-graph/people/` directory has no JSON files.

**Possible Causes:**

1. **Extraction hasn't run yet**
   ```bash
   # Check if extraction has run
   ls -lh knowledge-graph/people/
   # Should show *.json files
   ```

2. **Wrong repository - extraction ran in different repo/fork**
   ```bash
   # Verify you're in correct directory
   pwd
   # Should show path to the test repo
   ```

3. **Files in different location - extraction wrote to different path**
   ```bash
   # Search for extraction files
   find . -name "*.json" -path "*/people/*" 2>/dev/null
   ```

**Solution:**
- Run extraction workflow on source documents first
- Verify extraction completed successfully (check workflow logs)
- Ensure you're in the correct repository

---

### Scenario: "N files found but all EMPTY"

**Diagnosis:** JSON files exist but all have empty entity arrays.

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
