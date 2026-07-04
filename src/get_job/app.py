import json
import logging
import os
from decimal import Decimal
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)
table = boto3.resource("dynamodb").Table(os.environ["JOBS_TABLE"])

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json", "access-control-allow-origin": "*"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }

def lambda_handler(event, context):
    job_id = (event.get("pathParameters") or {}).get("job_id")
    if not job_id:
        return response(400, {"error": "job_id is required"})
    try:
        item = table.get_item(Key={"job_id": job_id}).get("Item")
        if not item:
            return response(404, {"error": "job not found"})
        return response(200, item)
    except Exception as exc:
        logger.exception("get_job_failed")
        return response(500, {"error": "internal server error", "detail": str(exc)})
