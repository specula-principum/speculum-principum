# Knowledge Graph

This directory stores extracted entities from parsed documents.

## Structure

- `people/` - Contains extracted person names from documents, stored as JSON files keyed by source document checksum

## Extraction Status

### prince01mach_1.pdf (The Prince by Niccolò Machiavelli)

**Document Checksum:** `1327a866df4a9ac3dc17963ca19ce7aa033bbd10debc9d073319e72c523a3ed3`

**Parsing Status:** ✅ Completed
- Successfully parsed 158-page PDF
- Generated 150 page-level markdown artifacts
- Output: `evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/`

**Extraction Status:** ⚠️ Pending API Credentials

Person name extraction requires GitHub Models API access via a GitHub token with appropriate permissions.

To complete extraction, run:
```bash
export GITHUB_TOKEN=<your-github-token>
python -m main extract
```

### Expected Persons

Based on the document title and historical context, this edition of "The Prince" by Niccolò Machiavelli likely contains references to numerous historical figures including:

- Niccolò Machiavelli (author)
- Cesare Borgia
- Pope Alexander VI
- Various Italian princes and rulers
- Historical Roman figures
- European monarchs

The actual extraction will identify all person names mentioned throughout the text using AI-powered entity recognition.
