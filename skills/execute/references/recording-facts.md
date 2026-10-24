# Recording what you learned

The repo's instructions file (`CLAUDE.md`, `AGENTS.md` or similar) is the memory the next session starts
with. Put a fact there when someone would otherwise rediscover it the hard way.

## Worth recording

- A setting or behavior that's easy to undo by accident, and what breaks when it is.
- A gotcha that took real time to find: an upgrade that silently reset config, a flag that looks harmless.
- How to check something is still right: the exact command and its expected output.
- A rule with its reason: "never run X without naming services, because Y restarts and Z loses its session".

## Not worth recording

- What the diff or `git log` already says.
- A changelog of what you did today. The issue's Resolution holds that.
- Guesses. Record it once you've confirmed it.

## How to write it

Put it in the section it belongs to, next to the thing it's about, not at the end. A good entry has:

1. **The rule or fact**, first, in bold if it's a must.
2. **Why**: what breaks, and how it shows up (the symptom someone will search for).
3. **When it was verified**, with a date.
4. **Check**: a command that shows it's still true.
5. **Roll back**, if it's a change someone might need to undo.

```markdown
**`--accept-routes` must stay `false` on this host.** Verified broken otherwise (2026-07).
- Why: a peer advertises 192.168.1.0/24, which collides with the local LAN, so replies to LAN clients are
  routed into the tunnel and TCP handshakes hang.
- Onset is delayed: existing connections keep working until a reboot clears conntrack.
- Check: `tailscale debug prefs | grep RouteAll` prints `false`.
```

When a fact changes, edit the old entry. Don't append a contradicting one.
