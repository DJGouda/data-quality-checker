import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["JOBS_TABLE"])
bucket = os.environ["UPLOAD_BUCKET"]

def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json", "access-control-allow-origin": "*"},
        "body": json.dumps(body),
    }

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        filename = str(body.get("filename", "")).strip()
        content_type = str(body.get("content_type", "text/csv")).strip()

        if not filename:
            return response(400, {"error": "filename is required"})
        if not filename.lower().endswith(".csv"):
            return response(400, {"error": "only CSV files are supported"})

        job_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        object_key = f"uploads/{job_id}/{filename}"

        table.put_item(Item={
            "job_id": job_id,
            "file_name": filename,
            "object_key": object_key,
            "status": "WAITING_UPLOAD",
            "created_at": created_at,
            "updated_at": created_at,
        })

        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": object_key, "ContentType": content_type},
            ExpiresIn=900,
            HttpMethod="PUT",
        )

        logger.info(json.dumps({"event": "upload_job_created", "job_id": job_id}))
        return response(201, {
            "job_id": job_id,
            "status": "WAITING_UPLOAD",
            "upload_url": upload_url,
            "object_key": object_key,
            "expires_in_seconds": 900,
        })
    except Exception as exc:
        logger.exception("create_upload_failed")
        return response(500, {"error": "internal server error", "detail": str(exc)})
