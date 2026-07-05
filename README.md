# Cloud-Native Data Quality Validation Platform

A serverless, event-driven data quality platform that validates uploaded CSV datasets and produces quality metrics, issue summaries, and downloadable JSON reports.

The project began as a synchronous FastAPI/Pandas prototype and was re-architected into a cloud-native AWS workflow using API Gateway, Lambda, S3, SQS, DynamoDB, CloudWatch, and AWS SAM.

### Note: This README.md is AI-Generated!!!

---

## Live Application

Frontend: deployed as a static site on Render.

> Replace this placeholder with your final Render URL before submission.

```text
https://cloud-data-quality-platform.onrender.com/
```

The frontend communicates directly with the deployed AWS API Gateway backend.

---

## What the Platform Does

A user can:

- upload a CSV file,
- create an asynchronous validation job,
- track job status,
- view quality metrics,
- inspect missing values and duplicate rows,
- detect custom rule violations,
- review numeric statistics,
- view validation history,
- download the full report as JSON.

The validation engine calculates:

- overall quality score,
- completeness score,
- uniqueness score,
- validity score,
- duplicate row count,
- total missing values,
- missing values by column,
- columns containing missing values,
- custom rule violations,
- numeric min, max, and mean statistics.

The overall quality score is calculated as:

```text
Overall Quality Score
= 40% Completeness
+ 30% Uniqueness
+ 30% Validity
```

---

## Architecture

```text
User Browser
      |
      v
Render Static Frontend
      |
      | HTTPS
      v
Amazon API Gateway
      |
      v
CreateUpload Lambda
      |
      +----------------------+
      |                      |
      v                      v
DynamoDB Job Record      Presigned S3 URL
                              |
                              v
                        S3 Data Bucket
                        uploads/<job_id>/
                              |
                              | ObjectCreated Event
                              v
                      SQS Validation Queue
                              |
                              v
                     Validation Worker Lambda
                              |
                     Pandas Validation Engine
                              |
                    +---------+---------+
                    |                   |
                    v                   v
             S3 report.json        DynamoDB
             reports/<job_id>/     status = COMPLETED
                    |
                    v
             GetReport Lambda
                    |
              TTL Warm Cache
              HIT / MISS
                    |
                    v
                 Frontend
```

The deployed S3 bucket is logically separated with prefixes:

```text
uploads/
reports/
```

The system uses asynchronous processing so CSV upload requests are decoupled from validation execution.

---

## AWS Services Used

### Amazon API Gateway

Exposes the backend HTTP API.

Routes:

```text
POST /uploads
GET  /jobs
GET  /jobs/{job_id}
GET  /reports/{job_id}
GET  /health
```

### AWS Lambda

The application uses separate Lambda functions for:

```text
CreateUploadFunction
GetJobFunction
GetReportFunction
ListJobsFunction
HealthFunction
ValidationWorkerFunction
```

### Amazon S3

Stores:

```text
uploads/<job_id>/<filename>.csv
reports/<job_id>/report.json
```

The browser uploads directly to S3 using a temporary presigned PUT URL.

### Amazon SQS

The Validation Queue decouples file ingestion from processing.

```text
S3 ObjectCreated
      |
      v
Validation Queue
      |
      v
Worker Lambda
```

Failed messages are retried and moved to a Dead Letter Queue after the configured retry limit.

### Amazon DynamoDB

Stores persistent job metadata such as:

```text
job_id
file_name
object_key
status
created_at
started_at
completed_at
quality_score
completeness_score
uniqueness_score
validity_score
duplicate_rows
total_missing_values
report_key
```

### Amazon CloudWatch

Provides:

- Lambda logs,
- structured application logs,
- Worker Lambda error alarm,
- DLQ message alarm.

### AWS SAM / CloudFormation

All AWS infrastructure is defined in:

```text
template.yaml
```

and deployed using AWS SAM.

---

## Repository Structure

```text
.
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── config.js
│   └── styles.css
│
├── src/
│   ├── create_upload/
│   │   └── app.py
│   ├── get_job/
│   │   └── app.py
│   ├── get_report/
│   │   └── app.py
│   ├── health/
│   │   └── app.py
│   ├── list_jobs/
│   │   └── app.py
│   └── worker/
│       ├── app.py
│       └── validator.py
│
├── load-tests/
│   ├── api-load-tests.js
│   └── k6-results.txt
│
├── runbook.md
├── template.yaml
├── samconfig.toml
├── README.md
└── .gitignore
```

---

## Functional Flow

### 1. Create Upload Job

The frontend sends:

```http
POST /uploads
Content-Type: application/json
```

Example body:

```json
{
  "filename": "sample_data.csv",
  "content_type": "text/csv"
}
```

The CreateUpload Lambda:

1. validates the request,
2. creates a unique job ID,
3. writes a `WAITING_UPLOAD` item to DynamoDB,
4. creates an S3 object key,
5. generates a presigned PUT URL,
6. returns the job ID and upload URL.

### 2. Upload CSV Directly to S3

The frontend uploads the file using the presigned URL.

```text
Browser
   |
   | PUT
   v
S3 uploads/<job_id>/<filename>
```

The frontend never receives AWS credentials.

### 3. Asynchronous Validation

The S3 object creation event sends a message to the SQS Validation Queue.

The Worker Lambda:

1. receives the SQS message,
2. extracts the S3 bucket and object key,
3. updates DynamoDB status to `PROCESSING`,
4. downloads the CSV from S3,
5. loads the dataset using Pandas,
6. runs the validation engine,
7. writes `report.json` to S3,
8. updates DynamoDB status to `COMPLETED`.

If processing fails repeatedly, the message is sent to the DLQ.

### 4. Status Polling

The frontend polls:

```http
GET /jobs/{job_id}
```

Typical status progression:

```text
WAITING_UPLOAD
      |
      v
PROCESSING
      |
      v
COMPLETED
```

### 5. Retrieve Report

The frontend requests:

```http
GET /reports/{job_id}
```

The GetReport Lambda uses a 60-second warm-runtime TTL cache.

Possible response headers:

```text
x-report-cache: MISS
```

followed by:

```text
x-report-cache: HIT
```

for repeated requests served from the same warm Lambda environment.

This cache is opportunistic and is not a distributed shared cache.

---

## Performance Results

The deployed API was tested with k6 using a staged load profile that ramped to 10 virtual users.

Measured results:

| Metric | Result |
|---|---:|
| Maximum virtual users | 10 |
| HTTP requests | 645 |
| Average latency | 107.03 ms |
| p95 latency | 168.3 ms |
| HTTP request failure rate | 0.31% |
| Checks successful | 99.68% |

Performance target:

```text
p95 < 700 ms
```

Result:

```text
PASS
```

Run the test with:

```bash
k6 run load-tests/api-load-tests.js
```

---

## Reliability Design

The system includes:

- asynchronous queue-based processing,
- SQS retries,
- DLQ isolation for poison messages,
- persistent job state in DynamoDB,
- durable files and reports in S3,
- CloudWatch worker error alarm,
- CloudWatch DLQ alarm,
- SAM/CloudFormation rollback support.

Configured retry behavior:

```text
Validation Queue
      |
      | processing failure
      v
Retry
      |
      | maxReceiveCount = 3
      v
Validation DLQ
```

Recovery objectives used for the project:

```text
RTO: 30 minutes
RPO: less than 5 minutes
```

See:

```text
docs/runbook.md
```

for operating and recovery procedures.

---

## Security Design

Implemented controls include:

- S3 Block Public Access,
- S3 server-side encryption,
- DynamoDB encryption,
- SQS server-side encryption,
- HTTPS endpoints,
- temporary S3 presigned upload URLs,
- no AWS credentials in application code,
- no credentials committed to the repository.

The application currently exposes public API routes for the class demo. A production implementation would add user authentication and authorization using Cognito or another OIDC-compatible identity provider.

The AWS Academy Learner Lab environment also limits IAM customization. The report documents these limitations separately from the intended production design.

---

## Prerequisites

Install:

- Python 3.12+
- AWS CLI
- AWS SAM CLI
- Git
- k6 for performance testing

macOS examples:

```bash
brew install awscli
brew install aws-sam-cli
brew install k6
```

Verify:

```bash
aws --version
sam --version
k6 version
```

---

## AWS Learner Lab Credentials

Start the AWS Academy Learner Lab and copy the temporary AWS CLI credentials into:

```text
~/.aws/credentials
```

Example format:

```ini
[default]
aws_access_key_id=...
aws_secret_access_key=...
aws_session_token=...
```

Set the region in:

```text
~/.aws/config
```

```ini
[default]
region = us-east-1
output = json
```

Verify:

```bash
aws sts get-caller-identity
```

Do not commit credentials to Git.

---

## Deploy the AWS Backend

From the repository root:

```bash
sam validate
```

Then:

```bash
sam build
```

Then:

```bash
sam deploy --guided
```

For the existing project stack:

```text
Stack name: data-quality-platform
Region: us-east-1
```

The deployment creates and manages:

- API Gateway,
- Lambda functions,
- S3 data bucket,
- DynamoDB Jobs table,
- SQS Validation Queue,
- SQS DLQ,
- CloudWatch alarms.

For later updates:

```bash
sam build
sam deploy
```

---

## Frontend Configuration

The frontend reads the AWS API base URL from:

```text
frontend/config.js
```

Example:

```javascript
window.APP_CONFIG = {
  API_URL: "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com"
};
```

The frontend is deployed separately as a Render Static Site.

Recommended Render settings:

```text
Root Directory: frontend
Build Command: echo "No build required"
Publish Directory: .
Branch: main
```

---

## Run Frontend Locally

For local testing:

```bash
python3 -m http.server 8080 --directory frontend
```

Open:

```text
http://localhost:8080
```

The local frontend still calls the deployed AWS backend.

---

## API Verification

Set:

```bash
export API_URL="https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com"
```

Health:

```bash
curl "$API_URL/health"
```

List jobs:

```bash
curl "$API_URL/jobs"
```

Get one job:

```bash
curl "$API_URL/jobs/$JOB_ID"
```

Get report:

```bash
curl "$API_URL/reports/$JOB_ID"
```

Cache check:

```bash
curl -i "$API_URL/reports/$JOB_ID"
curl -i "$API_URL/reports/$JOB_ID"
```

Look for:

```text
x-report-cache: MISS
```

and:

```text
x-report-cache: HIT
```

---

## Monitoring and Troubleshooting

Worker logs:

```bash
sam logs   --name ValidationWorkerFunction   --stack-name data-quality-platform   --tail
```

Stack status:

```bash
aws cloudformation describe-stacks   --stack-name data-quality-platform   --query "Stacks[0].StackStatus"   --output text
```

For deployment failures, wait for CloudFormation rollback to complete before deploying again.

See the complete operations guide:

```text
docs/runbook.md
```

---

## Example Validation Output

Example summary:

```json
{
  "quality_metrics": {
    "overall_quality_score": 91.11,
    "completeness_score": 92.5,
    "uniqueness_score": 87.5,
    "validity_score": 92.86
  },
  "issues": {
    "duplicate_rows": 1,
    "total_missing_values": 3
  }
}
```

The full report also includes:

- dataset row and column counts,
- column names,
- missing values by column,
- columns with missing values,
- custom validation rule results,
- numeric column statistics.

---

## Project Evolution

### Original Version

```text
Browser
   |
   v
FastAPI
   |
   v
Pandas
   |
   v
JSON Response
```

### Final Version

```text
Render Frontend
   |
   v
API Gateway
   |
   v
Lambda
   |
   +--> DynamoDB
   |
   +--> Presigned S3 Upload
             |
             v
            S3
             |
             v
            SQS
             |
             v
       Worker Lambda
             |
             v
      Pandas Validation
             |
       +-----+-----+
       |           |
       v           v
      S3       DynamoDB
```

The final architecture improves scalability, reliability, observability, and failure isolation while preserving the original validation engine.

---

## Documentation

`runbook.md` contains:

- startup procedures,
- health checks,
- common failure scenarios,
- DLQ troubleshooting,
- alarm response procedures,
- rollback procedure,
- backup and recovery strategy,
- RTO and RPO,
- security checks,
- pre-demo checklist.

The final project report contains the full architecture analysis, NFRs, AWS Well-Architected Framework evaluation, diagrams, screenshots, trade-offs, and measured performance results.

---

## Author

Duren Gouda  
Dalhousie University  
CSCI 4149 Term Project
