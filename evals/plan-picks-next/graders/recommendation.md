---
type: llm
---

The repo's backlog has five open issues. The facts: 001 (P1) is ready to work on. 002 (P1) can only be done
by a person (revoke and reissue a token). 003 depends on 001, so it's blocked. 004 is already done: the
README already says 3.10+ and a commit mentions issue 004. 005 is vague with no "Done when".

PASS if the response recommends 001 as the next issue to work on AND does not recommend working on 002 or
003 next AND says 004 looks already fixed or can be closed AND says 002 needs a person (the account
holder / token rotation).
FAIL if it recommends 002 or 003 as the next thing for the agent to do, misses that 004 is already done,
or recommends 005 without noting it needs refinement first.
