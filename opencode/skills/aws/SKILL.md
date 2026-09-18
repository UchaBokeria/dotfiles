---
name: aws
description: AWS work. Use for EC2, S3, IAM, CloudWatch, or debugging AWS-hosted services.
---

# AWS

- Consoles: EC2/S3/IAM/CloudWatch in `https://console.aws.amazon.com`.
- CLI: `aws` (uses `~/.aws/` profiles/SSO — never paste keys into chat).
- Defaults: least-privilege IAM, S3 Block Public Access stays on unless the
  bucket is intentionally public, CloudWatch Logs first for failures.
- Costs: check Cost Explorer before creating anything new; tag resources
  per project. Never leave test instances/volumes running — stop or
  terminate at session end unless asked otherwise.
