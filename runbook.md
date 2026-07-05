# Operational Runbook

## Data Quality Checker Platform

## 1. Purpose

This runbook provides operating, verification, troubleshooting, and recovery procedures for the cloud-native Data Quality Checker Platform.

The platform allows a user to upload a CSV file from a Render-hosted frontend. The browser requests a presigned S3 URL through API Gateway, uploads the file directly to Amazon S3, and the file is processed asynchronously through SQS and a Validation Worker Lambda. Job status and summary metrics are stored in DynamoDB, while full validation reports are stored in S3.

---

## 2. Architecture Overview

Main components:

- Render Static Site — hosts the HTML, CSS, and JavaScript frontend.
- Amazon API Gateway — exposes the application endpoints.
- CreateUpload Lambda — creates a validation job and returns a presigned S3 upload URL.
- Health Lambda — provides a health-check endpoint.
- GetJob Lambda — returns job status and metadata.
- GetReport Lambda — returns the completed validation report and includes a short-lived warm-runtime TTL cache.
- ListJobs Lambda — returns recent validation history.
- Amazon S3 — stores uploaded CSV files and generated JSON reports.
- Amazon SQS Validation Queue — buffers validation jobs.
- Amazon SQS DLQ — stores messages that repeatedly fail processing.
- Validation Worker Lambda — downloads the CSV, runs Pandas validation, writes the report, and updates the job record.
- Amazon DynamoDB — stores job metadata, status, timestamps, and summary metrics.
- Amazon CloudWatch — stores Lambda logs and exposes alarms.
- AWS SAM / CloudFormation — manages infrastructure as code.

Normal flow:

```text
User uploads CSV
    ↓
POST /uploads
    ↓
CreateUpload Lambda
    ↓
DynamoDB: WAITING_UPLOAD
    ↓
Presigned S3 upload URL
    ↓
Browser uploads CSV to S3
    ↓
S3 ObjectCreated event
    ↓
SQS Validation Queue
    ↓
Validation Worker Lambda
    ↓
DynamoDB: PROCESSING
    ↓
Pandas validation
    ↓
Report saved to S3
    ↓
DynamoDB: COMPLETED
    ↓
Frontend retrieves report
```

---

## 3. Starting the Environment

### 3.1 Start AWS Learner Lab

1. Open AWS Academy Learner Lab.
2. Click **Start Lab**.
3. Wait until the AWS indicator becomes green.
4. Do not use **Reset Lab** unless the environment must be rebuilt.

### 3.2 Verify the API

Set the API URL:

```bash
export API_URL="https://szcf8ifdpe.execute-api.us-east-1.amazonaws.com"
```

Run:

```bash
curl "$API_URL/health"
```

Expected response:

```json
{
  "status": "healthy",
  "service": "cloud-data-quality-platform",
  "timestamp": "..."
}
```

### 3.3 Verify the frontend

Open the Render Static Site URL.

Expected frontend status:

```text
ONLINE
```

If the frontend loads but reports `API ERROR`, verify the `/health` endpoint first.

---

## 4. Core Health Checks

### 4.1 Health endpoint

```bash
curl -i "$API_URL/health"
```

Expected result:

```text
HTTP/2 200
```

### 4.2 Job endpoint

Use a completed job:

```bash
export JOB_ID="3c758cc7-6040-4645-8898-ca160125d5e5"
```

Run:

```bash
curl "$API_URL/jobs/$JOB_ID"
```

Expected fields include:

```text
status = COMPLETED
quality_score
completeness_score
uniqueness_score
validity_score
report_key
```

### 4.3 Report endpoint

```bash
curl "$API_URL/reports/$JOB_ID"
```

Expected result:

```text
HTTP 200
```

and a full JSON validation report.

---

## 5. Worker Lambda Logs

Use the SAM logical resource name:

```bash
sam logs   --name ValidationWorkerFunction   --stack-name data-quality-platform   --tail
```

Useful structured log events include:

```json
{
  "event": "validation_started",
  "job_id": "..."
}
```

and:

```json
{
  "event": "validation_completed",
  "job_id": "...",
  "quality_score": 91.11
}
```

These logs should be used to investigate processing failures and long-running jobs.

---

## 6. Common Failure Scenarios

### 6.1 Frontend shows API ERROR

Symptoms:

```text
API ERROR
```

Checks:

```bash
curl "$API_URL/health"
```

Possible causes:

- Learner Lab is not running.
- API Gateway endpoint is unavailable.
- Health Lambda failed.
- AWS environment was reset or credentials expired for CLI operations.

Recovery:

1. Start Learner Lab.
2. Re-test `/health`.
3. Check the Health Lambda logs.
4. Check the CloudFormation stack status.
5. Confirm API Gateway routes are present.

### 6.2 Job remains WAITING_UPLOAD

Meaning:

The job record was created, but the CSV did not reach S3.

Checks:

1. Open the S3 data bucket.
2. Confirm that the expected key exists:

```text
uploads/<job_id>/<file_name>.csv
```

Recovery:

1. Create a new upload job.
2. Use the returned presigned URL.
3. Upload the file again.
4. Confirm the object appears under `uploads/`.

### 6.3 Job remains PROCESSING

Possible causes:

- malformed CSV,
- Pandas parsing failure,
- S3 read failure,
- Lambda exception,
- Lambda timeout.

Checks:

1. Inspect Validation Worker Lambda logs.
2. Inspect the SQS queue.
3. Check the CloudWatch Worker Errors alarm.
4. Inspect the DynamoDB job record.
5. Confirm the input object exists in S3.

Recovery:

1. Fix the CSV or code issue shown in logs.
2. Re-upload the CSV as a new job.
3. Confirm the new job reaches `COMPLETED`.

### 6.4 Message reaches the DLQ

The SQS queue is configured with:

```text
maxReceiveCount = 3
```

Meaning:

The worker failed repeatedly to process the same message.

Procedure:

1. Open the Validation DLQ.
2. Inspect the failed message.
3. Identify the job ID and S3 object key.
4. Review Worker Lambda logs.
5. Fix the root cause.
6. Re-upload the file or redrive the message after verifying the fix.

### 6.5 Worker Errors alarm is active

Procedure:

1. Open CloudWatch.
2. Open the Worker Errors alarm.
3. Note the alarm timestamp.
4. Open Worker Lambda logs for the same time window.
5. Identify the job ID.
6. Inspect the related DynamoDB and S3 records.
7. Correct the problem and re-run the job.

### 6.6 DLQ alarm is active

Procedure:

1. Open CloudWatch Alarms.
2. Open the DLQ Messages alarm.
3. Open the DLQ.
4. Inspect message contents.
5. Review Worker Lambda logs.
6. Fix the cause.
7. Retry safely.

---

## 7. Cache Verification

The GetReport Lambda includes a 60-second warm-runtime TTL cache.

First request:

```bash
curl -i "$API_URL/reports/$JOB_ID"
```

Expected header:

```text
x-report-cache: MISS
```

Second immediate request:

```bash
curl -i "$API_URL/reports/$JOB_ID"
```

Expected header:

```text
x-report-cache: HIT
```

Limitation:

The cache is tied to a warm Lambda execution environment. It is opportunistic and is not a globally shared distributed cache.

---

## 8. Performance Verification

The platform was tested with k6.

Run:

```bash
k6 run load-tests/api-load-tests.js
```

Measured staged-load results:

```text
Maximum virtual users: 10
HTTP requests: 645
Average latency: 107.03 ms
p95 latency: 168.3 ms
HTTP request failure rate: 0.31%
Checks successful: 99.68%
```

Target:

```text
p95 < 700 ms
```

Result:

```text
PASS
```

---

## 9. Deployment Procedure

### 9.1 Validate

```bash
sam validate
```

Expected:

```text
template.yaml is a valid SAM Template
```

### 9.2 Build

```bash
sam build
```

Expected:

```text
Build Succeeded
```

### 9.3 Deploy

```bash
sam deploy
```

Stack:

```text
data-quality-platform
```

Region:

```text
us-east-1
```

---

## 10. Rollback Procedure

If a deployment fails:

1. Do not interrupt CloudFormation rollback.
2. Wait until the stack reaches:

```text
UPDATE_ROLLBACK_COMPLETE
```

3. Confirm:

```bash
aws cloudformation describe-stacks   --stack-name data-quality-platform   --query "Stacks[0].StackStatus"   --output text
```

4. Fix the template or deployment issue.
5. Run:

```bash
sam validate
sam build
sam deploy
```

again.

---

## 11. Backup and Recovery

### 11.1 S3

Persistent data is organized as:

```text
uploads/
reports/
```

Recovery approach:

- use the uploaded CSV in S3 as the source of truth,
- re-run validation,
- regenerate the report,
- update the DynamoDB job record.

### 11.2 DynamoDB

The jobs table stores fields such as:

```text
job_id
status
file_name
object_key
quality_score
report_key
created_at
started_at
completed_at
```

If metadata must be recovered, the original uploaded file in S3 can be reprocessed to recreate the validation report and job summary.

---

## 12. Recovery Objectives

### RTO

```text
30 minutes
```

Rationale:

The application infrastructure is defined in SAM/CloudFormation and uses managed AWS services, allowing the environment to be recreated quickly from source.

### RPO

```text
Less than 5 minutes
```

Rationale:

Uploaded files are stored in S3 and job status is persisted in DynamoDB during the workflow. SQS buffers validation requests.

---

## 13. Security Checks

Verify that:

- S3 Block Public Access is enabled on the data bucket.
- S3 server-side encryption is enabled.
- DynamoDB encryption is enabled.
- SQS server-side encryption is enabled.
- Browser uploads use temporary presigned S3 URLs.
- No AWS credentials are stored in source code.
- No secrets are committed to GitHub.
- Lambda access is provided through the AWS Learner Lab role.

Repository secret scan:

```bash
grep -R "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|AWS_SESSION_TOKEN" . --exclude-dir=.git --exclude-dir=.venv --exclude-dir=.aws-sam
```

Expected result:

```text
no output
```

---

## 14. Pre-Demo Checklist

Before the 1-on-1 demo:

```text
[ ] Start Learner Lab.
[ ] Wait for AWS indicator to turn green.
[ ] Open the Render frontend.
[ ] Confirm the frontend shows ONLINE.
[ ] Test the /health endpoint.
[ ] Upload one sample CSV.
[ ] Confirm the job reaches COMPLETED.
[ ] Open the CloudFormation stack.
[ ] Open Lambda resources.
[ ] Open S3 uploads/ and reports/.
[ ] Open a completed DynamoDB item.
[ ] Open SQS queue and DLQ.
[ ] Open CloudWatch alarms.
[ ] Keep the k6 result screenshot ready.
[ ] Keep the architecture diagram ready.
[ ] Keep the data-flow diagram ready.
```

---

## 15. Quick Recovery Commands

Backend health:

```bash
curl "$API_URL/health"
```

Job history:

```bash
curl "$API_URL/jobs"
```

Job details:

```bash
curl "$API_URL/jobs/$JOB_ID"
```

Report:

```bash
curl "$API_URL/reports/$JOB_ID"
```

Stack status:

```bash
aws cloudformation describe-stacks   --stack-name data-quality-platform   --query "Stacks[0].StackStatus"   --output text
```

Worker logs:

```bash
sam logs   --name ValidationWorkerFunction   --stack-name data-quality-platform   --tail
```
