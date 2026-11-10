#!/usr/bin/env python3
"""Container entrypoint for running the harness as a Kubernetes Job on EKS.

1. Fetches the LLM API key from AWS Secrets Manager, so no secret is stored
   in the image, the manifest or on disk.
2. Runs the harness with the arguments passed to the container.
3. Uploads the results file to S3, so results survive after the pod exits.

Environment:
  LLM_SECRET_ID   Secrets Manager secret holding the Gemini API key (optional)
  RESULTS_BUCKET  S3 bucket for results (optional)
  RUN_ID          Name for this run; defaults to a UTC timestamp
"""
import datetime
import os
import pathlib
import subprocess
import sys

import boto3


def main() -> int:
    secret_id = os.environ.get("LLM_SECRET_ID")
    if secret_id and not os.environ.get("GEMINI_API_KEY"):
        secrets = boto3.client("secretsmanager")
        value = secrets.get_secret_value(SecretId=secret_id)["SecretString"]
        os.environ["GEMINI_API_KEY"] = value
        print(f"fetched API key from Secrets Manager ({secret_id})", flush=True)

    run_id = os.environ.get("RUN_ID") or datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    args = sys.argv[1:]
    if "--out" in args:
        out = pathlib.Path(args[args.index("--out") + 1])
    else:
        out = pathlib.Path("/app/results") / f"{run_id}.jsonl"
        args += ["--out", str(out)]

    rc = subprocess.call([sys.executable, "-m", "harness.runner", *args])

    bucket = os.environ.get("RESULTS_BUCKET")
    if bucket and out.exists():
        key = f"runs/{run_id}/{out.name}"
        boto3.client("s3").upload_file(str(out), bucket, key)
        print(f"uploaded results to s3://{bucket}/{key}", flush=True)

    return rc


if __name__ == "__main__":
    sys.exit(main())
