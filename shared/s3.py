import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from shared.config import settings

# When s3_endpoint_url is set (e.g. a local MinIO instance) boto3 talks to it
# instead of AWS. MinIO requires path-style addressing.
_client = boto3.client(
    "s3",
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region,
    endpoint_url=settings.s3_endpoint_url or None,
    config=Config(s3={"addressing_style": "path"}) if settings.s3_endpoint_url else None,
)

BUCKET = settings.aws_bucket_name


def upload(data: bytes, key: str, content_type: str = "application/octet-stream") -> None:
    _client.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def download(key: str) -> bytes:
    response = _client.get_object(Bucket=BUCKET, Key=key)
    return bytes(response["Body"].read())


def exists(key: str) -> bool:
    try:
        _client.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def delete(key: str) -> None:
    _client.delete_object(Bucket=BUCKET, Key=key)


def list_keys(prefix: str) -> list[str]:
    paginator = _client.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys
