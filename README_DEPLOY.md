Deployment notes

gcloud functions deploy start_breaking_monitor \
Cloud Functions (quick):

1. Use the provided `cloud_function.py` which exposes `start_breaking_monitor(request)` as the HTTP entry point.
2. Deploy (example):

```bash
gcloud functions deploy start_breaking_monitor \
  --runtime=python311 \
  --trigger-http \
  --region=us-central1 \
  --entry-point=start_breaking_monitor \
  --allow-unauthenticated \
  --service-account=YOUR_SERVICE_ACCOUNT_EMAIL \
  --set-env-vars OPENAI_API_KEY=${OPENAI_API_KEY}
```

Notes:
- You do not need `functions-framework` for Cloud Functions deployment; the platform handles the HTTP server. Keeping it in `requirements.txt` is harmless for local testing but optional for production deployments.
- Ensure the function's service account has `roles/storage.objectAdmin` (or a narrower object-level role) for the `lahsing-news-contents` bucket.

Cloud Run (container):

1. Build and push image:

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/lahsing-news
```

2. Deploy to Cloud Run:

```bash
gcloud run deploy lahsing-news \
  --image gcr.io/PROJECT_ID/lahsing-news \
  --platform managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --service-account=YOUR_SERVICE_ACCOUNT_EMAIL \
  --set-env-vars OPENAI_API_KEY=${OPENAI_API_KEY}
```

Notes:
- Grant the service account at least `roles/storage.objectAdmin` on the `lahsing-news-contents` bucket.
- For production, store `OPENAI_API_KEY` in Secret Manager and mount or inject via Cloud Run/Functions.
