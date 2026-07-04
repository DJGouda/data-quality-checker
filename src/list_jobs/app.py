import json
import os
from decimal import Decimal
import boto3

table = boto3.resource("dynamodb").Table(os.environ["JOBS_TABLE"])

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def lambda_handler(event, context):
    items = table.scan().get("Items", [])
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    jobs = [{
        "job_id": x.get("job_id"), "file_name": x.get("file_name"),
        "status": x.get("status"), "created_at": x.get("created_at"),
        "completed_at": x.get("completed_at"), "quality_score": x.get("quality_score")
    } for x in items[:50]]
    return {"statusCode": 200, "headers": {"content-type": "application/json", "access-control-allow-origin": "*"}, "body": json.dumps(jobs, cls=DecimalEncoder)}
