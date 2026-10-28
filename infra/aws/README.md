# infra/aws (D7: target A, later)

**Nothing is implemented here yet.** D7 = single box now (D), Fargate + SQS later (A).

| Option | Shape | Notes |
|---|---|---|
| **A: Fargate + SQS (target)** | ECS Fargate services for the API and workers, SQS `runs` queue (+ DLQ), RDS PostgreSQL 17, ElastiCache Redis (rate limiter + cache), S3 (raw archive, documents), EventBridge Scheduler for jobs | Closest to production. Workers scale on queue depth |
| B: Lambda + Step Functions | Step Functions models the pipeline. Lambda per agent | 15 min limit, cold starts, ONRC 675 MB bulk load is awkward |
| C: SQS + Lambda | Lambda consumers on SQS | Cheapest, same bulk-ingest problems as B, no orchestration view |
| **D: single box (now)** | See `infra/local/README.md` | Fastest for the hackathon |

Region: `eu-central-1` (data stays in the EU; Bedrock is available there too if `LLM_PROVIDER=bedrock`).
Code changes for A are limited to the `impl_cloud` stubs (`SqsQueue`, `S3ObjectStore`, `RedisCache`, `RedisRateLimiter`) and env vars. The ports make this a configuration switch.
