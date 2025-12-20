import logging
from breaking_monitor import process_breaking_news

# Cloud Functions HTTP entrypoint
def start_breaking_monitor(request):
    """HTTP Cloud Function entry point.

    Deploy with: gcloud functions deploy start_breaking_monitor --runtime=python311 \
      --trigger-http --region=YOUR_REGION --entry-point=start_breaking_monitor \
      --service-account=YOUR_SERVICE_ACCOUNT --set-env-vars OPENAI_API_KEY=${OPENAI_API_KEY}
    """
    logging.basicConfig(level=logging.INFO)
    logging.info("Breaking News Monitor triggered.")

    try:
        process_breaking_news()
        logging.info("Process completed successfully.")
        return ("Breaking News Monitor execution finished.", 200)
    except Exception as e:
        logging.exception("An error occurred during execution")
        return (f"Internal Server Error: {e}", 500)
