import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from urllib.parse import unquote_plus

import boto3
import pandas as pd

from validator import validate_dataframe

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(os.environ["JOBS_TABLE"])
report_bucket = os.environ["UPLOAD_BUCKET"]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def process_s3_record(s3_record):
    bucket_name = s3_record["s3"]["bucket"]["name"]
    object_key = unquote_plus(s3_record["s3"]["object"]["key"])
    parts = object_key.split("/")
    if len(parts) < 3 or parts[0] != "uploads":
        logger.info(json.dumps({"event": "ignored_object", "object_key": object_key}))
        return

    job_id = parts[1]
    file_name = "/".join(parts[2:])
    started_at = now_iso()

    logger.info(json.dumps({"event": "validation_started", "job_id": job_id, "object_key": object_key}))

    table.update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #s=:s, updated_at=:u, started_at=:st",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "PROCESSING", ":u": started_at, ":st": started_at},
    )

    try:
        obj = s3.get_object(Bucket=bucket_name, Key=object_key)
        df = pd.read_csv(BytesIO(obj["Body"].read()))
        report = validate_dataframe(df, file_name)

        report_key = f"reports/{job_id}/report.json"
        s3.put_object(
            Bucket=report_bucket,
            Key=report_key,
            Body=json.dumps(report).encode("utf-8"),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )

        q = report["quality_metrics"]
        s = report["dataset_summary"]
        i = report["issues"]
        completed_at = now_iso()

        table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=(
                "SET #s=:s, updated_at=:u, completed_at=:c, report_key=:r, "
                "quality_score=:q, completeness_score=:co, uniqueness_score=:un, "
                "validity_score=:va, total_rows=:tr, total_columns=:tc, "
                "duplicate_rows=:dr, total_missing_values=:tm"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "COMPLETED", ":u": completed_at, ":c": completed_at, ":r": report_key,
                ":q": Decimal(str(q["overall_quality_score"])),
                ":co": Decimal(str(q["completeness_score"])),
                ":un": Decimal(str(q["uniqueness_score"])),
                ":va": Decimal(str(q["validity_score"])),
                ":tr": int(s["total_rows"]), ":tc": int(s["total_columns"]),
                ":dr": int(i["duplicate_rows"]), ":tm": int(i["total_missing_values"]),
            },
        )

        logger.info(json.dumps({
            "event": "validation_completed", "job_id": job_id,
            "rows": s["total_rows"], "columns": s["total_columns"],
            "quality_score": q["overall_quality_score"], "report_key": report_key,
        }))

    except Exception as exc:
        failed_at = now_iso()
        table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #s=:s, updated_at=:u, error_message=:e",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "FAILED", ":u": failed_at, ":e": str(exc)[:1000]},
        )
        logger.exception(json.dumps({"event": "validation_failed", "job_id": job_id}))
        raise

def lambda_handler(event, context):
    processed = 0
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        for s3_record in body.get("Records", []):
            process_s3_record(s3_record)
            processed += 1
    return {"processed": processed}
