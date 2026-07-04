import json
import logging
import os
import time
from decimal import Decimal

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

table = boto3.resource("dynamodb").Table(os.environ["JOBS_TABLE"])
s3 = boto3.client("s3")
bucket = os.environ["UPLOAD_BUCKET"]
cache_ttl_seconds = int(os.environ.get("CACHE_TTL_SECONDS", "60"))

# Opportunistic warm-runtime cache.
# This persists only while the Lambda execution environment stays warm.
_report_cache = {}


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def response(status_code, body, cache_status=None):
    headers = {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
    }
    if cache_status:
        headers["x-report-cache"] = cache_status
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def lambda_handler(event, context):
    job_id = (event.get("pathParameters") or {}).get("job_id")

    if not job_id:
        return response(400, {"error": "job_id is required"})

    item = table.get_item(Key={"job_id": job_id}).get("Item")

    if not item:
        return response(404, {"error": "job not found"})

    if item.get("status") != "COMPLETED":
        return response(
            409,
            {
                "error": "report is not ready",
                "status": item.get("status"),
            },
        )

    now = time.time()
    cached = _report_cache.get(job_id)

    if cached and now - cached["cached_at"] < cache_ttl_seconds:
        logger.info(
            json.dumps(
                {
                    "event": "report_cache_hit",
                    "job_id": job_id,
                    "ttl_seconds": cache_ttl_seconds,
                }
            )
        )
        return response(
            200,
            {
                "job_id": job_id,
                "status": item["status"],
                "created_at": item.get("created_at"),
                "completed_at": item.get("completed_at"),
                "report": cached["report"],
            },
            cache_status="HIT",
        )

    logger.info(
        json.dumps(
            {
                "event": "report_cache_miss",
                "job_id": job_id,
                "report_key": item["report_key"],
            }
        )
    )

    obj = s3.get_object(Bucket=bucket, Key=item["report_key"])
    report = json.loads(obj["Body"].read().decode("utf-8"))

    _report_cache[job_id] = {
        "cached_at": now,
        "report": report,
    }

    return response(
        200,
        {
            "job_id": job_id,
            "status": item["status"],
            "created_at": item.get("created_at"),
            "completed_at": item.get("completed_at"),
            "report": report,
        },
        cache_status="MISS",
    )
