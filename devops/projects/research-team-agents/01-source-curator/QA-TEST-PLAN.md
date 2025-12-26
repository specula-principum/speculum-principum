# Source Curator QA Test Plan

## Overview

This document provides step-by-step testing procedures for the Source Curator Agent's Discussions-First Workflow. All testing occurs on GitHub.com via Discussions, Issues, and Actions.

**Feature Summary:** Sources are proposed via Discussions, assessed by the agent, approved/rejected via slash commands, and implemented through Issues assigned to Copilot.

---

## Prerequisites

### Environment Setup
- [ ] Repository has GitHub Discussions enabled
- [ ] "Sources" category exists in Discussions
- [ ] Required labels exist (created automatically by setup workflow):
  - `setup` - Repository setup and configuration
  - `question` - Question requiring agent response
  - `source-approved` - Approved source pending implementation
  - `source-proposal` - Proposed source under review
  - `wontfix` - This will not be worked on
- [ ] GitHub Actions workflows are enabled
- [ ] `GH_TOKEN` secret is configured with appropriate permissions
- [ ] Python environment is set up with `requirements.txt` installed

> **Note:** Labels are automatically created when running `python -m main setup --repo <owner/repo>`. If labels are missing, re-run the setup workflow.

### Required Workflows
Verify these workflow files exist in `.github/workflows/`:
- [ ] `2-op-assess-source.yml` - Triggers on Discussion create/edit in Sources category
- [ ] `2-op-curate-sources.yml` - Triggers on Discussion comments with `/approve-source` or `/reject-source`
- [ ] `2-op-implement-source.yml` - Triggers on Issues with `source-approved` label assigned to copilot

### Test Data Preparation
Prepare these URLs for testing:

| URL Type | Example | Expected Score |
|----------|---------|----------------|
| Government (.gov) | `https://www.usa.gov/` | High (≥0.7) |
| Education (.edu) | `https://www.mit.edu/` | High (≥0.7) |
| Organization (.org) | `https://www.wikipedia.org/` | Medium (0.5-0.7) |
| Commercial (.com) | `https://example.com/` | Lower (0.3-0.5) |
| Unreachable | `https://this-domain-does-not-exist-12345.gov/` | N/A (accessibility fail) |

---

## Test Scenarios

### Scenario 1: Happy Path - Full Approval Flow

**Objective:** Verify complete workflow from proposal to source registration.

#### Step 1.1: Create Source Proposal Discussion

1. Navigate to repository Discussions
2. Click "New discussion"
3. Select "Sources" category
4. Enter title: `[QA Test] Propose: USA.gov`
5. Enter body:
   ```markdown
   ## Source Proposal: USA.gov

   **URL**: https://www.usa.gov/
   **Discovery Method**: manual_proposal

   ### Why This Source?
   Official U.S. government portal - authoritative source for federal information.
   ```
6. Click "Start discussion"

**Expected Result:**
- [ ] Discussion is created in Sources category
- [ ] GitHub Action `2-op-assess-source.yml` triggers automatically
- [ ] Within ~2 minutes, agent posts a credibility assessment reply

#### Step 1.2: Verify Agent Assessment Reply

1. Wait for workflow to complete (check Actions tab)
2. Return to the Discussion

**Expected Result:**
- [ ] Agent reply contains "Credibility Assessment" header
- [ ] Reply includes credibility score (should be ≥0.7 for .gov)
- [ ] Reply includes domain type: "government"
- [ ] Integrity indicators table is present with:
  - Official domain: ✅
  - Accessible: ✅
  - Valid SSL: ✅
  - Content parseable: ✅
- [ ] Recommendation section is present

#### Step 1.3: Approve the Source

1. In the Discussion, add a new comment:
   ```
   /approve-source
   ```
2. Submit the comment

**Expected Result:**
- [ ] GitHub Action `2-op-curate-sources.yml` triggers
- [ ] Agent creates a new Issue titled similar to "Implement Source: USA.gov"
- [ ] Issue has `source-approved` label
- [ ] Issue is assigned to `copilot`
- [ ] Discussion is updated with link to the implementation Issue

#### Step 1.4: Verify Implementation

1. Navigate to the created Issue
2. Wait for `2-op-implement-source.yml` workflow to complete

**Expected Result:**
- [ ] Source is registered in `knowledge-graph/sources/`
- [ ] Discussion is updated with "Approved" status
- [ ] Issue is closed with implementation summary
- [ ] Source entry JSON file contains correct data:
  - `source_type`: "derived" or "reference"
  - `status`: "active"
  - `proposal_discussion`: matches Discussion number
  - `implementation_issue`: matches Issue number
  - `credibility_score`: ≥0.7

---

### Scenario 2: Rejection Flow

**Objective:** Verify sources can be rejected with documented reasons.

#### Step 2.1: Create Source Proposal

1. Create a new Discussion in "Sources" category
2. Title: `[QA Test] Propose: Example Commercial Site`
3. Body:
   ```markdown
   ## Source Proposal: Example.com

   **URL**: https://example.com/
   **Discovery Method**: manual_proposal

   ### Why This Source?
   Testing rejection flow.
   ```

#### Step 2.2: Wait for Assessment

1. Wait for agent assessment reply

**Expected Result:**
- [ ] Agent posts credibility assessment
- [ ] Score should be lower for commercial domain

#### Step 2.3: Reject the Source

1. Add comment:
   ```
   /reject-source Not an authoritative source for research purposes
   ```

**Expected Result:**
- [ ] GitHub Action triggers
- [ ] Discussion is marked as rejected
- [ ] Agent posts rejection summary with the provided reason
- [ ] No Issue is created
- [ ] Source is NOT added to registry

---

### Scenario 3: CLI Discovery Command

**Objective:** Verify `discover-sources` CLI creates Discussions for discovered URLs.

#### Step 3.1: Dry Run Discovery

1. Ensure `evidence/parsed/` contains markdown files with external URLs
2. Run in terminal:
   ```bash
   python -m main discover-sources --dry-run
   ```

**Expected Result:**
- [ ] Command lists discovered URLs without creating Discussions
- [ ] Output shows credibility scores for each candidate
- [ ] Already-registered sources are excluded

#### Step 3.2: Execute Discovery with Limit

1. Run:
   ```bash
   python -m main discover-sources --limit 1
   ```

**Expected Result:**
- [ ] One Discussion is created in "Sources" category
- [ ] Discussion follows the proposal template
- [ ] Agent assessment workflow triggers

#### Step 3.3: Domain Filter Test

1. Run:
   ```bash
   python -m main discover-sources --domain-filter "\.gov$" --dry-run
   ```

**Expected Result:**
- [ ] Only .gov URLs are listed
- [ ] Other domain types are excluded

---

### Scenario 4: Edge Cases

#### Test 4.1: Duplicate Source Proposal

1. Attempt to propose a URL that is already registered
2. Create Discussion with a URL from `knowledge-graph/sources/`

**Expected Result:**
- [ ] Agent assessment notes the URL is already registered
- [ ] Recommendation advises against duplicate registration

#### Test 4.2: Unreachable Source

1. Create Discussion proposing `https://this-domain-does-not-exist-12345.gov/`

**Expected Result:**
- [ ] Agent assessment shows:
  - Accessible: ❌
  - Assessment includes warning about unreachable URL
  - Recommendation advises against approval

#### Test 4.3: Approval Without Assessment

1. Create Discussion in Sources category
2. Immediately comment `/approve-source` before agent posts assessment

**Expected Result:**
- [ ] Agent warns that no assessment was performed
- [ ] Issue creation proceeds (or is blocked based on implementation)
- [ ] Behavior is documented and consistent

#### Test 4.4: Command in Wrong Category

1. Create Discussion in a non-Sources category (e.g., "General")
2. Comment `/approve-source`

**Expected Result:**
- [ ] Workflow does not trigger (check Actions tab)
- [ ] No Issue is created
- [ ] Source is not registered

#### Test 4.5: Malformed URL

1. Create Discussion proposing `not-a-valid-url`

**Expected Result:**
- [ ] Agent assessment flags invalid URL format
- [ ] Recommendation is to reject

---

### Scenario 5: Primary Source Registration (Setup Flow)

**Objective:** Verify `source_url` from manifest is registered during repo setup.

#### Step 5.1: Check Manifest

1. Verify `config/manifest.json` contains a `source_url` field

#### Step 5.2: Run Setup

1. Run the setup_repo mission or `python -m main setup`

**Expected Result:**
- [ ] Primary source is registered in `knowledge-graph/sources/`
- [ ] Source entry has `source_type`: "primary"
- [ ] Initial Discussion is created documenting the primary source

---

## Verification Checklist

### Registry Verification

After approval flows, verify the source entry file:

```bash
# List all registered sources
ls -la knowledge-graph/sources/

# View a specific source entry (replace with actual hash)
cat knowledge-graph/sources/{url_hash}.json
```

**Required Fields in Source Entry:**
- [ ] `url` - Canonical URL
- [ ] `name` - Human-readable name
- [ ] `source_type` - "primary", "derived", or "reference"
- [ ] `status` - "active"
- [ ] `last_verified` - ISO timestamp
- [ ] `added_at` - ISO timestamp
- [ ] `added_by` - GitHub username
- [ ] `proposal_discussion` - Discussion number
- [ ] `implementation_issue` - Issue number
- [ ] `credibility_score` - Float 0.0-1.0

### Workflow Verification

Check GitHub Actions tab for each workflow execution:

| Workflow | Trigger | Expected Status |
|----------|---------|-----------------|
| `2-op-assess-source.yml` | Discussion created in Sources | ✅ Success |
| `2-op-curate-sources.yml` | `/approve-source` comment | ✅ Success |
| `2-op-curate-sources.yml` | `/reject-source` comment | ✅ Success |
| `2-op-implement-source.yml` | Issue with `source-approved` + copilot | ✅ Success |

---

## Cleanup

After testing, clean up test artifacts:

1. Close/delete test Discussions created with `[QA Test]` prefix
2. Close any orphaned test Issues
3. Remove test source entries from `knowledge-graph/sources/` if needed:
   ```bash
   # Identify test entries
   grep -l "usa.gov\|example.com" knowledge-graph/sources/*.json
   
   # Remove if needed
   rm knowledge-graph/sources/{test_entry_hash}.json
   ```

---

## Known Issues / Notes

- Discussion category templates are not supported by GitHub; template content is in the Discussion creation logic
- Workflows may take 1-2 minutes to complete; refresh the page to see updates
- Agent must have write permissions to create Issues and post comments

---

## Sign-Off

| Tester | Date | Scenarios Passed | Notes |
|--------|------|------------------|-------|
| | | /5 | |

---

*Document Version: 1.0*  
*Created: 2025-12-25*  
*Based on: PLAN.md (Implementation Complete status)*
