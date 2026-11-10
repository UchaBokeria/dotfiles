1: ---
2: name: gcloud
3: description: Google Cloud work. Use for GCE, GCS, IAM, Cloud Run, or debugging GCP-hosted services.
4: ---
5: 
6: # Google Cloud
7: 
8: - Console: `https://console.cloud.google.com`.
9: - CLI: `gcloud` / `gsutil` (active project via `gcloud config list`;
10:   impersonation and `application-default` creds live in `~/.config/gcloud`).
11: - Defaults: check project + region first (`gcloud config list`), least-
12:   privilege IAM, GCS uniform bucket-level access, Cloud Logging first.
13: - Costs: billing export/Budgets before creating GPUs/large disks; delete
14:   test resources at session end unless asked otherwise.
