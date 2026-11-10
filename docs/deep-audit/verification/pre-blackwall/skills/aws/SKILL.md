1: ---
2: name: aws
3: description: AWS work. Use for EC2, S3, IAM, CloudWatch, or debugging AWS-hosted services.
4: ---
5: 
6: # AWS
7: 
8: - Consoles: EC2/S3/IAM/CloudWatch in `https://console.aws.amazon.com`.
9: - CLI: `aws` (uses `~/.aws/` profiles/SSO — never paste keys into chat).
10: - Defaults: least-privilege IAM, S3 Block Public Access stays on unless the
11:   bucket is intentionally public, CloudWatch Logs first for failures.
12: - Costs: check Cost Explorer before creating anything new; tag resources
13:   per project. Never leave test instances/volumes running — stop or
14:   terminate at session end unless asked otherwise.
