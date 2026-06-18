# Runbooks

Short operational playbooks — opened by humans during an incident, not consumed by the platform. Keep each one short enough that an on-call engineer can read it end-to-end under stress.

| File | When |
|---|---|
| [`dlq-replay.md`](./dlq-replay.md) | Tasks have landed in the DLQ |
| [`region-failover.md`](./region-failover.md) | One region is unhealthy and not recovering |
| [`secret-rotation.md`](./secret-rotation.md) | Periodic rotation, or a leaked credential |
| [`rollback.md`](./rollback.md) | A bad deploy needs reverting |
| [`oncall-handoff.md`](./oncall-handoff.md) | End-of-shift handover template |

Every runbook follows the same shape:
1. **When to use** — single sentence trigger
2. **Decision** — what you need to know before acting
3. **Steps** — commands you can paste
4. **Verify** — how to confirm it worked
5. **If this runbook itself fails** — escalation path

If you find yourself doing something that isn't covered here, write a new runbook before you forget.
