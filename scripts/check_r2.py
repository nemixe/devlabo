#!/usr/bin/env python3
"""Quick script to list and read files from R2."""

import os
import sys

import boto3

# Load from environment or prompt
endpoint_url = os.environ.get("R2_ENDPOINT_URL")
access_key = os.environ.get("R2_ACCESS_KEY_ID")
secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
bucket_name = os.environ.get("R2_BUCKET_NAME", "devlabo")

if not all([endpoint_url, access_key, secret_key]):
    print("Set environment variables: R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY")
    sys.exit(1)

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint_url,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
)

prefix = sys.argv[1] if len(sys.argv) > 1 else "test/test/"

print(f"Listing files in s3://{bucket_name}/{prefix}\n")

response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

if "Contents" not in response:
    print("No files found.")
    sys.exit(0)

for obj in response["Contents"]:
    print(f"  {obj['Key']} ({obj['Size']} bytes)")

# If a specific file is requested, read it
if len(sys.argv) > 2:
    file_key = sys.argv[2]
    print(f"\n--- Contents of {file_key} ---")
    obj = s3.get_object(Bucket=bucket_name, Key=file_key)
    print(obj["Body"].read().decode("utf-8"))
