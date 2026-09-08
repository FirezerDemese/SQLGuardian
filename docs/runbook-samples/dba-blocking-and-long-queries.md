# Platform DBA Runbook - Contention

Owner: Platform Data Engineering
Escalation: #db-oncall, then the Data Platform duty manager after 20 minutes.
Last reviewed: 2026-06-14

## Blocking chain on a production OLTP instance

Conditions: BLOCKING_CHAIN

This procedure applies to SQLPROD01 and SQLPROD02 during trading hours
(07:00-19:00 UK). Outside trading hours, follow the overnight batch procedure
instead - the head blocker is almost always the warehouse load and must not be
killed.

1. Confirm the head blocker is still live and still running the same statement before acting on anything the alert showed you.
2. Record the head blocker session id, login, host and program name in the incident channel. The alert is a snapshot; the incident record needs the values you saw.
3. If program_name is OrderSync or WMS-Bridge, page the Fulfilment on-call before doing anything else. Those two open long transactions by design and killing them leaves partial picks that have to be reconciled by hand.
4. If the head blocker is idle with an open transaction, it is an application problem. Ask Fulfilment to release it. Do not kill it while they are still investigating.
5. If the chain is longer than 8 sessions, or any session has waited over 300 seconds, declare a P2 in #incident and continue.
6. Kill the head blocker only with duty manager approval, and only after steps 1-5. Note in the channel that the rollback may hold the locks for as long again.
7. After the chain clears, capture the blocking statement into the incident record so the owning team can fix the query.

Rollback: there is no rollback for a kill. If the transaction is lost, Fulfilment
replays the affected orders from the outbox table.

## Long-running query with no blocking

Conditions: LONG_RUNNING_REQUEST

1. Check whether the session belongs to a scheduled Agent job before anything else. Index maintenance and the nightly reconciliation both run long by design.
2. Get the live plan and the wait type. A query waiting on PAGEIOLATCH is a storage problem, not a query problem, and killing it fixes nothing.
3. If the session is an ad-hoc query from the Reporting group, contact the analyst directly on #data-analysts. We do not kill analyst queries without telling them.
4. If it holds no locks and blocks nothing, leave it and record it for the weekly tuning review.

Rollback: killing a maintenance task starts a rollback that runs longer than the
statement did. If it is an index rebuild, let it finish.
