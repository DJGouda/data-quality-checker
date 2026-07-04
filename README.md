# Phase 5 Lite — Frontend + Lambda Report Cache

This version keeps the working Phase 4 AWS backend and adds:

1. A browser frontend connected to the AWS API.
2. A 60-second warm-runtime TTL cache inside `GetReportFunction`.
3. Structured `report_cache_hit` and `report_cache_miss` logs.
4. An `x-report-cache: HIT|MISS` response header.

CloudFront OAC was not used because the AWS Academy Learner Lab permission boundary blocks `cloudfront:CreateOriginAccessControl`.

## Backend update

Copy your deployment config:

```bash
cp ../data-quality-project-phase4/samconfig.toml .
```

Then:

```bash
sam validate
sam build
sam deploy
```

This deployment only updates `GetReportFunction`; it does not add CloudFront resources.

## Verify cache

Use an existing completed job ID:

```bash
curl -i "$API_URL/reports/$JOB_ID"
curl -i "$API_URL/reports/$JOB_ID"
```

The first request should normally include:

```text
x-report-cache: MISS
```

A repeated request routed to the same warm Lambda execution environment should include:

```text
x-report-cache: HIT
```

Because Lambda execution environments are ephemeral, this is an opportunistic application cache and not a globally consistent distributed cache.

## Run frontend locally

From the project root:

```bash
python3 -m http.server 8080 --directory frontend
```

Open:

```text
http://localhost:8080
```

The frontend will:

1. POST `/uploads`
2. Receive the job ID and presigned S3 URL
3. PUT the CSV directly to S3
4. Poll `/jobs/{job_id}`
5. Render `/reports/{job_id}`
6. Show validation history from `/jobs`

## Report wording for CloudFront limitation

The production design proposed CloudFront in front of a private S3 origin using Origin Access Control. The AWS Academy Learner Lab permission boundary denied `cloudfront:CreateOriginAccessControl`, so the lab deployment used an external/static frontend while preserving the fully cloud-native AWS backend. The report retrieval path includes a small warm-runtime TTL cache for repeated recently requested reports.
