# Code Search Enhancement for Orchestration Missions

## Executive Summary

This project aims to enhance the orchestration mission system by adding code search capabilities that enable agents to search through repository files and use in-context learning to answer questions about functionality.

## Background

### Current State

The orchestration mission system (`src/orchestration/`) provides a flexible agent runtime for executing automated tasks via GitHub issues. Currently, the system includes:

- **GitHub Tools**: Issue reading, searching, commenting, labeling, and PR operations
- **Parsing Tools**: Document conversion and preview capabilities  
- **Human Tools**: User interaction prompts

However, the system **lacks** the ability to:
- Search through repository files and code
- Read file contents from the repository
- Understand code structure and functionality programmatically

### Problem Statement

When responding to issues that ask questions about code functionality (e.g., "How does feature X work?"), the orchestration agent cannot:

1. Search for relevant code files in the repository
2. Read and analyze source code to understand implementation
3. Reference specific functions, classes, or modules in responses
4. Provide accurate, code-backed answers about repository functionality

This limitation reduces the agent's effectiveness for:
- Technical Q&A in issues
- Code exploration and documentation
- Context-aware responses about implementation details
- In-context learning from repository contents

## Proposal

### Solution Overview

Add repository code search and file reading capabilities to the orchestration toolkit, enabling agents to:

1. **Search for code patterns** across the repository
2. **Read file contents** to understand implementation
3. **Navigate the codebase** programmatically
4. **Provide informed answers** backed by actual code

### Technical Design

#### 1. New Tool: `search_repository_code`

Search for code patterns, function names, or text across repository files.

**Parameters:**
- `query` (string, required): Search query (text, regex, or code pattern)
- `path` (string, optional): Limit search to specific directory or file pattern
- `language` (string, optional): Filter by programming language
- `max_results` (integer, optional): Maximum results to return (default: 20)
- `repository` (string, optional): Repository in 'owner/name' format (defaults to env)
- `token` (string, optional): GitHub token (defaults to env)

**Returns:**
```json
{
  "success": true,
  "output": {
    "query": "def process_issue",
    "total_count": 3,
    "results": [
      {
        "path": "src/integrations/github/issues.py",
        "line_number": 42,
        "matched_line": "def process_issue(issue_data):",
        "context": "...",
        "score": 0.95
      }
    ]
  }
}
```

**Risk Level:** SAFE (read-only operation)

**Implementation Notes:**
- Use GitHub Code Search API (`GET /search/code`)
- Support basic search syntax: filename, extension, language filters
- Return contextual code snippets (3-5 lines around match)
- Handle pagination for large result sets
- Cache results to minimize API calls

#### 2. New Tool: `read_file_contents`

Read the contents of a file from the repository at a specific commit or branch.

**Parameters:**
- `path` (string, required): File path relative to repository root
- `ref` (string, optional): Branch, tag, or commit SHA (defaults to default branch)
- `repository` (string, optional): Repository in 'owner/name' format (defaults to env)
- `token` (string, optional): GitHub token (defaults to env)

**Returns:**
```json
{
  "success": true,
  "output": {
    "path": "src/orchestration/tools.py",
    "content": "\"\"\"Tool registry for the Copilot agent runtime...",
    "size": 5432,
    "encoding": "utf-8",
    "sha": "abc123...",
    "ref": "main"
  }
}
```

**Risk Level:** SAFE (read-only operation)

**Implementation Notes:**
- Use GitHub Contents API (`GET /repos/{owner}/{repo}/contents/{path}`)
- Decode base64-encoded content automatically
- Support both files and symbolic links
- Return metadata (size, SHA, last modified)
- Handle binary files gracefully (return metadata only)
- Implement reasonable size limits (e.g., 1MB max)

#### 3. New Tool: `list_directory_contents`

List files and directories at a given path in the repository.

**Parameters:**
- `path` (string, optional): Directory path (defaults to root "/")
- `ref` (string, optional): Branch, tag, or commit SHA (defaults to default branch)
- `recursive` (boolean, optional): List contents recursively (default: false)
- `repository` (string, optional): Repository in 'owner/name' format (defaults to env)
- `token` (string, optional): GitHub token (defaults to env)

**Returns:**
```json
{
  "success": true,
  "output": {
    "path": "src/orchestration",
    "entries": [
      {"name": "agent.py", "type": "file", "size": 8234},
      {"name": "toolkit", "type": "directory", "size": 0}
    ],
    "total": 2
  }
}
```

**Risk Level:** SAFE (read-only operation)

### Implementation Plan

#### Phase 1: Core Search Integration (Week 1)
- [ ] Create `src/integrations/github/code_search.py` module
  - [ ] Implement GitHub Code Search API wrapper
  - [ ] Add query parsing and validation
  - [ ] Implement result formatting and deduplication
- [ ] Create `src/integrations/github/repository_contents.py` module
  - [ ] Implement Contents API wrapper for file reading
  - [ ] Add base64 decoding and encoding detection
  - [ ] Implement directory listing functionality
- [ ] Add unit tests for new integration modules
  - [ ] Mock GitHub API responses
  - [ ] Test error handling and edge cases
  - [ ] Validate parameter parsing

#### Phase 2: Tool Registration (Week 1-2)
- [ ] Extend `src/orchestration/toolkit/github.py`
  - [ ] Register `search_repository_code` tool
  - [ ] Register `read_file_contents` tool
  - [ ] Register `list_directory_contents` tool
  - [ ] Implement tool handlers with validation
- [ ] Add tool tests in `tests/orchestration/toolkit/`
  - [ ] Test tool registration
  - [ ] Test parameter validation
  - [ ] Test result formatting

#### Phase 3: Documentation & Examples (Week 2)
- [ ] Update `README.md` with new tool capabilities
- [ ] Create example mission: `config/missions/code_exploration.yaml`
  - [ ] Demonstrate code search usage
  - [ ] Show file reading workflow
  - [ ] Illustrate Q&A with code references
- [ ] Add inline documentation to new modules
- [ ] Create integration test scenarios

#### Phase 4: Testing & Refinement (Week 2-3)
- [ ] End-to-end testing with real GitHub API
- [ ] Performance optimization (caching, rate limits)
- [ ] Security review (ensure read-only, no secrets exposed)
- [ ] User acceptance testing with sample issues

### Success Metrics

1. **Functionality:**
   - All three tools successfully registered and executable
   - Code search returns relevant results for common queries
   - File reading handles various file types and sizes
   - Error handling gracefully manages API failures

2. **Performance:**
   - Average search query completes in < 2 seconds
   - File reads complete in < 1 second for files < 100KB
   - Rate limiting prevents API quota exhaustion

3. **Quality:**
   - 100% test coverage for new integration modules
   - All tests pass in CI/CD pipeline
   - No security vulnerabilities introduced
   - Documentation complete and accurate

4. **User Impact:**
   - Agents can answer code-related questions accurately
   - Responses include specific file references and line numbers
   - Users report improved answer quality in issues

## Use Cases

### Use Case 1: Technical Q&A
**Scenario:** User asks "How does the issue search functionality work?"

**Agent Workflow:**
1. Use `search_repository_code` to find "search" + "issue" implementations
2. Use `read_file_contents` to examine `src/integrations/github/search_issues.py`
3. Post comment with explanation and code references

**Value:** Accurate, code-backed answers without manual code review

### Use Case 2: Feature Discovery
**Scenario:** User asks "What authentication methods are supported?"

**Agent Workflow:**
1. Use `search_repository_code` with query "auth OR authentication"
2. Use `list_directory_contents` on relevant directories
3. Read configuration files to identify auth mechanisms
4. Summarize findings with file paths

**Value:** Comprehensive feature documentation from codebase

### Use Case 3: Debugging Assistance
**Scenario:** User reports "Error in tool execution"

**Agent Workflow:**
1. Search for error message in codebase
2. Read surrounding code context
3. Identify potential root cause
4. Suggest fix with specific line references

**Value:** Faster issue resolution with contextual information

## Risks & Mitigation

### Risk 1: API Rate Limits
**Impact:** High - Could prevent searches during heavy usage
**Probability:** Medium
**Mitigation:**
- Implement intelligent caching (TTL: 1 hour)
- Use conditional requests (ETags) where possible
- Add rate limit monitoring and backoff
- Document rate limit behavior in tool descriptions

### Risk 2: Large File Performance
**Impact:** Medium - Slow responses for large files
**Probability:** Medium
**Mitigation:**
- Enforce 1MB file size limit
- Truncate very large files with warning
- Stream large files in chunks if needed
- Suggest using direct GitHub links for huge files

### Risk 3: Search Result Quality
**Impact:** Medium - Irrelevant results reduce usefulness
**Probability:** Medium
**Mitigation:**
- Support advanced search syntax (filename:, path:, language:)
- Return ranked results with confidence scores
- Limit to top N most relevant results
- Allow path filtering to focus searches

### Risk 4: Security Exposure
**Impact:** High - Could expose sensitive information
**Probability:** Low
**Mitigation:**
- Read-only operations (SAFE risk level)
- Respect repository permissions via token
- No local file system access
- Audit logging for all searches

## Dependencies

### External:
- **GitHub REST API** (Code Search, Contents)
  - Rate limits: 30 searches/minute, 5000 requests/hour
  - Authentication: GitHub token (GITHUB_TOKEN)
  - Documentation: https://docs.github.com/en/rest

### Internal:
- `src/integrations/github/issues.py` (authentication, error handling patterns)
- `src/orchestration/tools.py` (tool registry)
- `src/orchestration/toolkit/github.py` (tool registration patterns)

### Development:
- `pytest` for testing
- `requests` library (already in requirements.txt)
- `responses` library for API mocking (may need to add)

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Core Integration | GitHub API wrappers, unit tests |
| 1-2 | Tool Registration | Tool definitions, handlers, tests |
| 2 | Documentation | README, example mission, docs |
| 2-3 | Testing & Refinement | E2E tests, performance tuning |

**Total Estimated Duration:** 3 weeks

## Alternatives Considered

### Alternative 1: Use GitHub GraphQL API
**Pros:** More flexible queries, single request for multiple resources
**Cons:** More complex implementation, different auth patterns
**Decision:** Rejected - REST API is simpler and sufficient for initial implementation

### Alternative 2: Clone Repository Locally
**Pros:** No API rate limits, faster file access
**Cons:** Requires disk space, security concerns, sync complexity
**Decision:** Rejected - Violates read-only principle, adds infrastructure complexity

### Alternative 3: Use External Code Search Service (Sourcegraph, etc.)
**Pros:** Advanced search features, better performance
**Cons:** External dependency, additional costs, integration complexity
**Decision:** Rejected - GitHub native API is sufficient and has no additional cost

## Future Enhancements

1. **Semantic Code Search:** Use embeddings for intent-based search
2. **Code Graph Analysis:** Understand call graphs and dependencies
3. **Multi-Repository Search:** Search across multiple related repos
4. **Historical Search:** Search code across commits/branches
5. **Syntax-Aware Search:** Parse and search by AST patterns
6. **Code Summarization:** AI-powered code explanations
7. **Interactive Code Navigation:** Multi-step file exploration workflows

## Conclusion

Adding code search and file reading capabilities to the orchestration toolkit will significantly enhance the agent's ability to answer questions about repository functionality. The proposed implementation is:

- **Feasible:** Uses existing GitHub APIs with proven patterns
- **Safe:** Read-only operations with proper permission handling
- **Valuable:** Enables accurate, code-backed responses to technical questions
- **Extensible:** Foundation for future advanced code understanding features

This enhancement directly addresses the gap identified in the original issue and enables the orchestration mission to perform in-context learning from the repository codebase.

## Approval & Sign-off

- **Project Owner:** copilot-orchestrator
- **Technical Lead:** [TBD]
- **Stakeholders:** Repository maintainers, issue triagers
- **Status:** Draft - Pending Review
- **Last Updated:** 2025-11-20
