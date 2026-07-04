import json
from datetime import datetime, timezone

def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json", "access-control-allow-origin": "*"},
        "body": json.dumps({
            "status": "healthy",
            "service": "cloud-data-quality-platform",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
    }
