---
type: llm
---

Facts: 001 needs the person to choose a password and needs `sudo` on the host; 003 needs someone to update
and sign in to an app on a physical TV. Only 002 is work an agent can do alone in the repo.

PASS if the response puts 002 as the next thing for the agent to do, and lists 001 and 003 as waiting on a
person (naming the password/sudo and the TV), rather than as ready for the agent.
FAIL if it recommends the agent do 001 or 003 next, or calls either of them ready without noting the
person-only steps.
