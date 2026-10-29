# Query plans on 100,000 synthetic cases

Generated 2026-10-28T11:43:50+00:00 by `scripts/policyguard_query_plans.py` on local PostgreSQL 16 (Apple M2, default settings). Seed time 4.2 s.

Data: 50 tenants, 1,000 institutions, 6,000 policy versions, 100,000 cases, 100,000 idempotency records, 100,000 outbox events (100 pending), 100,000 jobs (100 queued), 100,000 decisions.

Each plan is `EXPLAIN (ANALYZE, BUFFERS)` of the query the application runs. Times are single local runs after ANALYZE, not production measurements.

## Case list for one tenant, newest first (cursor page)

```sql
SELECT case_id, state, created_at FROM cases WHERE tenant_id = 't7' AND (created_at, case_id) < (now() - interval '10 days', 'c999999') ORDER BY created_at DESC, case_id DESC LIMIT 50
```

```
Limit  (cost=0.42..144.76 rows=50 width=24) (actual time=0.010..0.032 rows=50 loops=1)
  Buffers: shared hit=52 read=1
  ->  Index Scan Backward using ix_cases_tenant_id_created_at_case_id on cases  (cost=0.42..5280.39 rows=1829 width=24) (actual time=0.009..0.030 rows=50 loops=1)
        Index Cond: (((tenant_id)::text = 't7'::text) AND (ROW(created_at, (case_id)::text) < ROW((now() - '10 days'::interval), 'c999999'::text)))
        Buffers: shared hit=52 read=1
Planning:
  Buffers: shared hit=35
Planning Time: 0.133 ms
Execution Time: 0.040 ms
```

## Policy snapshot for one institution

```sql
SELECT * FROM policy_versions WHERE tenant_id = 't8' AND institution_id = 'i7' ORDER BY policy_id, valid_from
```

```
Sort  (cost=8.31..8.32 rows=1 width=392) (actual time=0.013..0.013 rows=6 loops=1)
  Sort Key: policy_id, valid_from
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=8
  ->  Index Scan using ix_policy_versions_tenant_id_institution_id_approval_status on policy_versions  (cost=0.28..8.30 rows=1 width=392) (actual time=0.003..0.005 rows=6 loops=1)
        Index Cond: (((tenant_id)::text = 't8'::text) AND ((institution_id)::text = 'i7'::text))
        Buffers: shared hit=8
Planning:
  Buffers: shared hit=100
Planning Time: 0.152 ms
Execution Time: 0.018 ms
```

## Outbox relay batch

```sql
SELECT * FROM outbox_events WHERE status = 'PENDING' AND available_at <= now() ORDER BY available_at LIMIT 100 FOR UPDATE SKIP LOCKED
```

```
Limit  (cost=0.42..158.59 rows=87 width=114) (actual time=0.010..0.042 rows=100 loops=1)
  Buffers: shared hit=105
  ->  LockRows  (cost=0.42..158.59 rows=87 width=114) (actual time=0.010..0.038 rows=100 loops=1)
        Buffers: shared hit=105
        ->  Index Scan using ix_outbox_events_status_available_at on outbox_events  (cost=0.42..157.72 rows=87 width=114) (actual time=0.008..0.020 rows=100 loops=1)
              Index Cond: ((status = 'PENDING'::text) AND (available_at <= now()))
              Buffers: shared hit=5
Planning:
  Buffers: shared hit=45
Planning Time: 0.102 ms
Execution Time: 0.050 ms
```

## Idempotency lookup

```sql
SELECT request_hash, case_id FROM idempotency_requests WHERE tenant_id = 't8' AND idempotency_key = 'k12357'
```

```
Index Scan using uq_idempotency_requests_tenant_id_idempotency_key on idempotency_requests  (cost=0.42..8.44 rows=1 width=39) (actual time=0.005..0.005 rows=1 loops=1)
  Index Cond: (((tenant_id)::text = 't8'::text) AND ((idempotency_key)::text = 'k12357'::text))
  Buffers: shared hit=4
Planning:
  Buffers: shared hit=19
Planning Time: 0.071 ms
Execution Time: 0.006 ms
```

## Job lease candidate

```sql
SELECT job_id FROM jobs WHERE state = 'QUEUED' AND run_after <= now() ORDER BY run_after, job_id LIMIT 1 FOR UPDATE SKIP LOCKED
```

```
Limit  (cost=2.24..4.09 rows=1 width=20) (actual time=0.014..0.014 rows=1 loops=1)
  Buffers: shared hit=6
  ->  LockRows  (cost=2.24..181.42 rows=97 width=20) (actual time=0.014..0.014 rows=1 loops=1)
        Buffers: shared hit=6
        ->  Incremental Sort  (cost=2.24..180.45 rows=97 width=20) (actual time=0.014..0.014 rows=1 loops=1)
              Sort Key: run_after, job_id
              Presorted Key: run_after
              Full-sort Groups: 1  Sort Method: quicksort  Average Memory: 26kB  Peak Memory: 26kB
              Buffers: shared hit=5
              ->  Index Scan using ix_jobs_state_run_after on jobs  (cost=0.42..176.08 rows=97 width=20) (actual time=0.006..0.010 rows=33 loops=1)
                    Index Cond: ((state = 'QUEUED'::text) AND (run_after <= now()))
                    Buffers: shared hit=5
Planning:
  Buffers: shared hit=17
Planning Time: 0.130 ms
Execution Time: 0.018 ms
```

## Decisions of one case

```sql
SELECT * FROM decisions WHERE tenant_id = 't43' AND case_id = 'c4242' ORDER BY created_at, assessment_kind
```

```
Sort  (cost=8.45..8.45 rows=1 width=172) (actual time=0.005..0.006 rows=1 loops=1)
  Sort Key: created_at, assessment_kind
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=4
  ->  Index Scan using ix_decisions_tenant_id_case_id on decisions  (cost=0.42..8.44 rows=1 width=172) (actual time=0.005..0.005 rows=1 loops=1)
        Index Cond: (((tenant_id)::text = 't43'::text) AND ((case_id)::text = 'c4242'::text))
        Buffers: shared hit=4
Planning:
  Buffers: shared hit=71
Planning Time: 0.118 ms
Execution Time: 0.009 ms
```

## Review queue page (needs review) for one tenant

```sql
SELECT c.case_id, (SELECT d.policy_decision FROM decisions d WHERE d.tenant_id = c.tenant_id AND d.case_id = c.case_id ORDER BY d.created_at DESC LIMIT 1) FROM cases c WHERE c.tenant_id = 't7' AND EXISTS (SELECT 1 FROM decisions d WHERE d.tenant_id = c.tenant_id AND d.case_id = c.case_id AND d.policy_decision IN ('REQUIRES_REVIEW', 'INSUFFICIENT_EVIDENCE')) ORDER BY c.created_at DESC, c.case_id DESC LIMIT 50
```

```
Limit  (cost=4727.37..4913.60 rows=22 width=46) (actual time=2.893..2.994 rows=50 loops=1)
  Buffers: shared hit=4218
  ->  Result  (cost=4727.37..4913.60 rows=22 width=46) (actual time=2.893..2.991 rows=50 loops=1)
        Buffers: shared hit=4218
        ->  Sort  (cost=4727.37..4727.42 rows=22 width=17) (actual time=2.886..2.888 rows=50 loops=1)
              Sort Key: c.created_at DESC, c.case_id DESC
              Sort Method: top-N heapsort  Memory: 28kB
              Buffers: shared hit=4018
              ->  Hash Semi Join  (cost=2414.41..4726.87 rows=22 width=17) (actual time=1.921..2.811 rows=1000 loops=1)
                    Hash Cond: ((c.case_id)::text = (d.case_id)::text)
                    Buffers: shared hit=4018
                    ->  Bitmap Heap Scan on cases c  (cost=28.88..2335.48 rows=2140 width=17) (actual time=0.646..1.329 rows=2000 loops=1)
                          Recheck Cond: ((tenant_id)::text = 't7'::text)
                          Heap Blocks: exact=2000
                          Buffers: shared hit=2003
                          ->  Bitmap Index Scan on ix_cases_tenant_id_state  (cost=0.00..28.34 rows=2140 width=0) (actual time=0.505..0.505 rows=2000 loops=1)
                                Index Cond: ((tenant_id)::text = 't7'::text)
                                Buffers: shared hit=3
                    ->  Hash  (cost=2372.53..2372.53 rows=1040 width=9) (actual time=1.273..1.273 rows=1000 loops=1)
                          Buckets: 2048  Batches: 1  Memory Usage: 57kB
                          Buffers: shared hit=2015
                          ->  Bitmap Heap Scan on decisions d  (cost=72.28..2372.53 rows=1040 width=9) (actual time=0.294..1.211 rows=1000 loops=1)
                                Recheck Cond: ((tenant_id)::text = 't7'::text)
                                Filter: (policy_decision = ANY ('{REQUIRES_REVIEW,INSUFFICIENT_EVIDENCE}'::text[]))
                                Rows Removed by Filter: 1000
                                Heap Blocks: exact=2000
                                Buffers: shared hit=2015
                                ->  Bitmap Index Scan on ix_decisions_tenant_id_case_id  (cost=0.00..72.02 rows=2080 width=0) (actual time=0.159..0.159 rows=2000 loops=1)
                                      Index Cond: ((tenant_id)::text = 't7'::text)
                                      Buffers: shared hit=15
        SubPlan 1
          ->  Limit  (cost=8.45..8.45 rows=1 width=22) (actual time=0.002..0.002 rows=1 loops=50)
                Buffers: shared hit=200
                ->  Sort  (cost=8.45..8.45 rows=1 width=22) (actual time=0.002..0.002 rows=1 loops=50)
                      Sort Key: d_1.created_at DESC
                      Sort Method: quicksort  Memory: 25kB
                      Buffers: shared hit=200
                      ->  Index Scan using ix_decisions_tenant_id_case_id on decisions d_1  (cost=0.42..8.44 rows=1 width=22) (actual time=0.001..0.002 rows=1 loops=50)
                            Index Cond: (((tenant_id)::text = (c.tenant_id)::text) AND ((case_id)::text = (c.case_id)::text))
                            Buffers: shared hit=200
Planning:
  Buffers: shared hit=41
Planning Time: 0.137 ms
Execution Time: 3.006 ms
```

## Largest indexes (write cost)

| Table | Index size |
|---|---|
| jobs | 7160 kB |
| outbox_events | 7160 kB |
| cases | 6944 kB |
| decisions | 5080 kB |
| idempotency_requests | 4928 kB |
| outbox_events | 3816 kB |
| jobs | 3816 kB |
| jobs | 3816 kB |
| decisions | 3816 kB |
| cases | 3816 kB |
| jobs | 3816 kB |
| cases | 816 kB |

Every insert into cases, outbox_events, jobs and idempotency_requests updates its B-tree indexes (O(log n) each). No GiST range index was added: interval selection reads at most a few versions per institution through `ix_policy_versions_institution_id_policy_id_valid_from`, so a range index has no measured benefit yet.
