# Agent Operations Runbook

## Overview

This runbook provides operational guidance for the Copilot Agentic Orchestrator, including monitoring, troubleshooting, and remediation procedures for common failure modes.

## Quick Reference

### Health Check
```bash
python -m main agent status --lookback-hours 24
```

### View Recent Missions
```bash
python -m main agent history --limit 10
```

### List Available Missions
```bash
python -m main agent list-missions
```

### Run Mission (Dry-Run)
```bash
python -m main agent run --mission <mission-file> --dry-run
```

---

## Monitoring

### Health Status Levels

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| **HEALTHY** | Success rate ≥90%, <3 failures | None - normal operation |
| **DEGRADED** | Success rate 70-90% or 3-5 failures | Monitor closely, investigate failures |
| **UNHEALTHY** | Success rate <70% or ≥5 failures | Immediate investigation required |

### Key Metrics

Monitor these metrics in `agent_metrics.db`:

1. **Mission Success Rate** - Percentage of successfully completed missions
2. **Average Duration** - Time per mission execution
3. **Tool Call Count** - Number of tool invocations per mission
4. **Token Usage** - LLM token consumption (cost tracking)
5. **Failure Rate** - Percentage of failed/blocked missions

### Accessing Metrics

```bash
# Health summary
python -m main agent status --format json

# Weekly performance report
python -m main agent status --lookback-hours 168 --format json

# Mission history
python -m main agent history --limit 50 --format table
```

### GitHub Actions Monitoring

- **Workflow**: `.github/workflows/agent-continuous.yml`
- **Schedule**: Hourly (configurable)
- **Artifacts**: Execution transcripts and metrics database
- **Summary**: Performance report in workflow summary

---

## Common Failure Modes

### 1. High Failure Rate (Multiple Consecutive Failures)

**Symptoms:**
- Circuit breaker state: OPEN
- Health status: UNHEALTHY
- Multiple failed missions in history

**Possible Causes:**
- GitHub API rate limit exceeded
- Missing or invalid credentials
- Mission configuration errors
- Tool execution failures

**Diagnosis:**
```bash
# Check recent failures
python -m main agent history --limit 20 | grep FAILED

# Review health recommendations
python -m main agent status --lookback-hours 24

# Examine specific failure transcript
python -m main agent explain --mission-id <id> --transcript transcript_<id>.json
```

**Remediation:**

1. **Check GitHub API quota:**
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" \
        https://api.github.com/rate_limit
   ```

2. **Verify credentials:**
   ```bash
   # Ensure GITHUB_TOKEN is set and valid
   echo $GITHUB_TOKEN | wc -c  # Should be >40 characters
   ```

3. **Reset circuit breaker:**
   ```python
   from src.orchestration.deployment import AgentDeployment, CircuitBreaker
   breaker = CircuitBreaker()
   breaker.reset()
   ```

4. **Review mission definitions:**
   - Check for syntax errors in YAML files
   - Validate tool names and parameters
   - Ensure allowed_tools match registered tools

---

### 2. Circuit Breaker Stuck in OPEN State

**Symptoms:**
- Missions being requeued without execution
- Circuit breaker state: OPEN
- No recent successful missions

**Causes:**
- Exceeded failure threshold (default: 3 consecutive failures)
- Recovery timeout not elapsed (default: 300s)

**Diagnosis:**
```bash
# Check circuit breaker state
python -m main agent status --format json | jq '.circuit_breaker'
```

**Remediation:**

1. **Wait for automatic recovery (5 minutes default)**
2. **Manual reset if issue resolved:**
   ```python
   from src.orchestration.deployment import AgentDeployment
   deployment = AgentDeployment(...)  # Initialize with runtime
   deployment.reset_circuit_breaker()
   ```

3. **Investigate root cause before resetting**

---

### 3. Slow Mission Execution

**Symptoms:**
- Average duration >60 seconds
- Health warnings about slow execution
- Missions timing out

**Causes:**
- Large document parsing operations
- Network latency (GitHub API)
- Inefficient tool sequences
- LLM response delays

**Diagnosis:**
```bash
# Review execution transcripts
python -m main agent explain --mission-id <id> --transcript transcript.json

# Check tool execution times in transcript
jq '.steps[] | {tool: .tool_call.name, duration: .duration}' transcript.json
```

**Remediation:**

1. **Optimize mission definitions:**
   - Reduce max_steps if unnecessarily high
   - Use more specific tool selection
   - Add caching where appropriate

2. **Review tool performance:**
   - Identify slow tools in transcripts
   - Consider tool optimization or replacement

3. **Adjust timeout settings:**
   - Update `max_steps` in mission definition
   - Configure GitHub Actions timeout

---

### 4. Mission Queue Full

**Symptoms:**
- "Queue full" warnings in logs
- Missions being rejected
- Backlog of pending work

**Causes:**
- High mission submission rate
- Slow mission execution
- Circuit breaker blocking execution

**Diagnosis:**
```bash
# Check queue status
python -m main agent status --format json | jq '.queue_size, .queue_capacity'
```

**Remediation:**

1. **Increase queue capacity:**
   ```python
   deployment = AgentDeployment(
       runtime=runtime,
       monitor=monitor,
       max_queue_size=200  # Increased from default 100
   )
   ```

2. **Add priority-based queueing:**
   ```python
   deployment.enqueue_mission(
       mission=mission,
       context=context,
       priority=MissionPriority.HIGH  # Process sooner
   )
   ```

3. **Scale horizontally** (future enhancement)

---

### 5. LLM Token/Cost Budget Exceeded

**Symptoms:**
- High token usage in metrics
- Cost estimates exceeding budget
- LLM API errors

**Causes:**
- Complex missions with many steps
- Inefficient prompt engineering
- High mission frequency

**Diagnosis:**
```bash
# Review token usage
python -m main agent status --lookback-hours 168 --format json | \
    jq '.costs'
```

**Remediation:**

1. **Review high-token missions:**
   ```bash
   # Find missions with high token usage
   sqlite3 agent_metrics.db \
       "SELECT mission_type, AVG(token_usage), COUNT(*) 
        FROM mission_metrics 
        GROUP BY mission_type 
        ORDER BY AVG(token_usage) DESC;"
   ```

2. **Optimize mission definitions:**
   - Use simpler, more direct goals
   - Reduce unnecessary context
   - Consider using deterministic planner for simple missions

3. **Implement budget controls:**
   - Set cost alerts in monitoring
   - Reduce mission frequency
   - Use dry-run mode for testing

---

### 6. GitHub API Rate Limiting

**Symptoms:**
- 403 Forbidden errors
- "rate limit exceeded" messages
- Failed GitHub tool calls

**Causes:**
- Too many API requests in short period
- Shared token across multiple services
- Missing authentication

**Diagnosis:**
```bash
# Check rate limit status
curl -H "Authorization: token $GITHUB_TOKEN" \
     https://api.github.com/rate_limit | jq '.rate'
```

**Remediation:**

1. **Wait for rate limit reset** (shown in API response)

2. **Reduce mission frequency:**
   - Adjust GitHub Actions schedule
   - Implement backoff strategy
   - Batch operations where possible

3. **Use authenticated requests** (5000/hour vs 60/hour):
   ```bash
   # Ensure GITHUB_TOKEN is set
   export GITHUB_TOKEN=ghp_...
   ```

4. **Request rate limit increase** (for high-volume use cases)

---

### 7. Mission Approval Timeout

**Symptoms:**
- Missions stuck in BLOCKED status
- Approval prompts unanswered
- Interactive mode hanging

**Causes:**
- Human approval required but not provided
- Approval callback not configured
- Timeout not set appropriately

**Diagnosis:**
```bash
# Check blocked missions
python -m main agent history --limit 50 | grep BLOCKED
```

**Remediation:**

1. **Review and respond to approval prompts:**
   - Check terminal/CLI for pending approvals
   - Review mission transcript for approval requests

2. **Configure approval callback:**
   ```python
   def approval_callback(tool_call, mission, context, risk):
       # Custom approval logic
       return ApprovalDecision.approved_decision(risk=risk)
   
   validator = SafetyValidator(approval_callback=approval_callback)
   ```

3. **Adjust approval requirements:**
   - Set `requires_approval: false` for low-risk missions
   - Use auto-approve for testing

---

## Operational Procedures

### Starting the Agent

**Manual Start:**
```bash
python -m main agent run --mission <mission-file>
```

**Continuous Operation:**
```python
from src.orchestration.deployment import AgentDeployment

deployment = AgentDeployment(runtime=runtime, monitor=monitor)
deployment.run_continuously()  # Blocks until shutdown
```

**Via GitHub Actions:**
- Automatic: Hourly schedule
- Manual: Workflow dispatch with custom parameters

### Stopping the Agent

**Graceful Shutdown:**
```bash
# Send SIGTERM (Ctrl+C in terminal)
kill -TERM <pid>
```

**Programmatic:**
```python
deployment.shutdown()  # Initiates graceful shutdown
```

**Emergency Stop:**
```bash
# Force kill (not recommended)
kill -9 <pid>
```

### Backup and Recovery

**Backup Metrics Database:**
```bash
# Copy database file
cp agent_metrics.db backups/agent_metrics_$(date +%Y%m%d).db

# Export to JSON
sqlite3 agent_metrics.db ".dump" > agent_metrics_backup.sql
```

**Restore from Backup:**
```bash
# Restore database
cp backups/agent_metrics_<date>.db agent_metrics.db

# Or import SQL dump
sqlite3 agent_metrics.db < agent_metrics_backup.sql
```

**Export Execution Transcripts:**
```bash
# Transcripts are saved with --output flag
python -m main agent run --mission <file> --output transcript_<timestamp>.json
```

---

## Troubleshooting Checklist

When investigating issues:

- [ ] Check agent health status
- [ ] Review recent mission history
- [ ] Examine failure transcripts
- [ ] Verify GitHub API quota
- [ ] Confirm credentials are valid
- [ ] Check circuit breaker state
- [ ] Review mission queue size
- [ ] Analyze token/cost metrics
- [ ] Check GitHub Actions workflow runs
- [ ] Review mission definition syntax

---

## Performance Tuning

### Optimize Mission Execution

1. **Reduce max_steps for simple missions**
2. **Use specific tool whitelists** (allowed_tools)
3. **Implement caching for repeated queries**
4. **Batch similar operations**

### Improve Success Rate

1. **Add retry logic for transient failures**
2. **Implement better error handling in tools**
3. **Use more specific mission constraints**
4. **Test missions in dry-run mode first**

### Control Costs

1. **Use deterministic planner for predictable missions**
2. **Reduce LLM context size**
3. **Implement token usage limits per mission**
4. **Monitor and alert on budget thresholds**

---

## Emergency Contacts

| Issue Type | Contact | SLA |
|------------|---------|-----|
| Circuit Breaker Stuck | DevOps Team | 2 hours |
| High Failure Rate | Engineering Team | 4 hours |
| Cost Overrun | Finance + Engineering | 1 business day |
| Security Incident | Security Team | Immediate |

---

## Maintenance Schedule

| Task | Frequency | Owner |
|------|-----------|-------|
| Review metrics and health | Daily | Operations |
| Clean old transcripts | Weekly | Automated |
| Database backup | Daily | Automated |
| Performance tuning review | Monthly | Engineering |
| Mission library audit | Quarterly | Product Team |

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-11-03 | Initial runbook creation | System |

---

## Related Documentation

- [Project Plan](../projects/copilot-orchestrator-plan.md)
- [Progress Log](../projects/copilot-orchestrator-progress.md)
- [Mission Authoring Guide](../../config/missions/README.md) (to be created)
- [Tool Development Guide](../../src/orchestration/toolkit/README.md) (to be created)
