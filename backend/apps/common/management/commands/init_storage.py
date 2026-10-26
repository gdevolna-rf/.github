import json

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.common.s3 import internal_client


class Command(BaseCommand):
    help = "Создаёт бакет объектного хранилища и политику публичного чтения для префикса public/."

    def handle(self, *args, **options):
        client = internal_client()
        bucket = settings.S3_BUCKET
        existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)
            self.stdout.write(f"created bucket {bucket}")
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/{settings.MEDIA_PUBLIC_PREFIX}*"],
                }
            ],
        }
        client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        self.stdout.write(self.style.SUCCESS("storage ready"))
