---
name: gcloud
description: Google Cloud work. Use for GCE, GCS, IAM, Cloud Run, or debugging GCP-hosted services.
---

# Google Cloud

- Console: `https://console.cloud.google.com`.
- CLI: `gcloud` / `gsutil` (active project via `gcloud config list`;
  impersonation and `application-default` creds live in `~/.config/gcloud`).
- Defaults: check project + region first (`gcloud config list`), least-
  privilege IAM, GCS uniform bucket-level access, Cloud Logging first.
- Costs: billing export/Budgets before creating GPUs/large disks; delete
  test resources at session end unless asked otherwise.
