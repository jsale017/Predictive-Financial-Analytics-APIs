# imports
from google.cloud import secretmanager
from google.cloud import storage
import requests
import json
import datetime
import uuid
import functions_framework
import os

# settings
project_id = 'financial-pipeline-group-6'

def get_finnhub_api_key():
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/FINNHUB_API_KEY/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

finnhub_api_key = get_finnhub_api_key()

secret_id = 'mother_db'
version_id = 'latest'
bucket_name = 'financial-pipeline-group-6-bucket'
finnhub_api_key = os.getenv('FINNHUB_API_KEY')



####################################################### helpers

def upload_to_gcs(bucket_name, job_id, data):
    """Uploads data to a Google Cloud Storage bucket."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob_name = f"jobs/{job_id}/finnhub_data.json"
    blob = bucket.blob(blob_name)

    # Upload the data (here it's a serialized string)
    blob.upload_from_string(data)
    print(f"File {blob_name} uploaded to {bucket_name}.")

    return {'bucket_name': bucket_name, 'blob_name': blob_name}


####################################################### core task

@functions_framework.http
def finnhub_schema_setup(request):  # Rename the function here
    # Generate a unique job ID for tracking
    job_id = datetime.datetime.now().strftime("%Y%m%d%H%M") + "-" + str(uuid.uuid4())

    # Instantiate the secret manager service to retrieve tokens
    sm = secretmanager.SecretManagerServiceClient()

    # Build the resource name of the secret version
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

    # Access the secret version to get the MotherDuck token
    response = sm.access_secret_version(request={"name": name})
    md_token = response.payload.data.decode("UTF-8")

    ####################################### Retrieve data from FinnHub API

    # Define the stock symbol and the API URL
    symbol = "AAPL"
    api_url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from=1672531200&to=1704067200&token={finnhub_api_key}"

    try:
        # Fetch stock data
        response = requests.get(api_url)
        data = response.json()

        if data and 's' in data and data['s'] == 'ok':
            print(f"Data fetched for {symbol}: {len(data['t'])} records")
        else:
            print(f"Error fetching data for {symbol}: {data}")

    except Exception as e:
        print(f"Error accessing FinnHub API: {e}")
        return {"error": str(e)}, 500

    ##################################################### Prepare data and upload to GCS

    # Convert the data to a JSON string
    data_json = json.dumps(data)

    # Upload the data to Google Cloud Storage
    gcs_path = upload_to_gcs(bucket_name, job_id, data_json)

    # Return a response with the job details
    return {
        "num_entries": len(data.get('t', [])),
        "job_id": job_id,
        "bucket_name": gcs_path.get('bucket_name'),
        "blob_name": gcs_path.get('blob_name')
    }, 200