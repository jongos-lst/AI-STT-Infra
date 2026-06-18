# Runbook — on-call handoff

End-of-shift template. Paste into the on-call channel.

```
Handing off to <next-oncall>.

State of the system
- Health: <green / yellow / red>
- DLQ depth: <N> (link to dashboard)
- Open alerts: <list>
- Active incidents: <list of incident channels>

Recent deploys
- <env> <sha> <when> <author> <one-line summary>

What I left in flight
- <PR # / runbook in progress / migration mid-flight>
- Anything that needs eyes within the next 2 hours

What to watch
- <metric>: <expected range>
- <subscription>: <expected backlog>

Known follow-ups
- <issue link>: <short summary, owner>

Nothing else. Pager is yours.
```

## Before you hand off

- Resolve or silence stale alerts (don't bequeath flapping noise).
- Make sure every active incident has an owner explicitly named.
- Run a synthetic upload from the public UI to confirm the platform is green.
