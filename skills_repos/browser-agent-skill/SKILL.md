# Authorized Browser Automation Skill

## Goal
Complete browser research and permitted actions with observable evidence.
## Execution contract
- Input: target URL or search goal, permitted action scope, authentication constraints, desired output.
- DOM & Element Finder: identify elements from current page/DOM or screenshots; never guess selectors.
- Action Executor: use the configured browser tool only. Default to read-only. Require explicit approval before publishing, sending messages, purchases, account changes, or destructive actions.
- Visual Verification Agent: re-read the resulting page and verify the expected state.
- Session & Cookie Manager: diagnose authorized session expiry; never bypass login, CAPTCHA, paywalls or anti-bot controls.
- Save evidence as URLs, extracted text and action results in the shared artifact state.
## Completion criteria
Return completed only when a page/result confirms the requested outcome. Otherwise return blocked/partial with exact error and next step.
## Output
Findings, source URLs, actions attempted, verification evidence, limitations and artifact references.