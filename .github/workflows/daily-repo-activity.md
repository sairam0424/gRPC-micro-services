---
on:
  schedule:
    - cron: '0 9 * * *'

permissions:
  contents: read
  issues: read  # Write operations are handled through safe-outputs for security
  pull-requests: read

safe-outputs:
  create-issue:
    title-prefix: "[Daily Report] "
    labels: [report, daily]

tools:
  github: null
---

# Daily Repository Activity Report

Generate a comprehensive daily report on recent activity in the gRPC microservices repository. This report should be delivered as a GitHub issue.

## Report Contents

Include the following sections:

### 1. Recent Activity Summary
- **Issues**: Count of opened, closed, and in-progress issues from the last 24 hours
- **Pull Requests**: Status of open PRs, recently merged PRs, and any failing CI checks
- **Commits**: Summary of recent commits with author count and key changes
- **Branches**: Active branches and development focus areas

### 2. Repository Status
- Architecture status (microservices health)
- Test coverage indicators if available
- Build status summary
- Deployment status

### 3. Key Highlights
- Notable merged features or fixes
- Critical issues or blockers
- Performance improvements or optimizations
- Documentation updates

### 4. Metrics Overview
- Total open issues count
- Total open PRs count
- Repository statistics (forks, stars, watchers)
- Commit frequency trends

### 5. Actionable Next Steps
- High-priority issues awaiting attention
- PRs pending review
- Upcoming milestones or releases
- Maintenance tasks required

## Format Requirements

- Keep the report concise and scannable
- Use bullet points and clear section headers
- Include direct links to relevant issues, PRs, and commits
- Focus on the last 24 hours of activity
- Highlight only critical or status-changing items
- Add context for non-obvious items
- Use a professional but friendly tone suitable for a development team

## Additional Notes

- Filter out duplicate or related issues
- Prioritize recent community contributions
- Include both successes and areas needing attention
- Make the report easy to share with stakeholders
