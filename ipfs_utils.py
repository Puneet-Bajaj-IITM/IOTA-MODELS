import json
import os
import requests

def upload_metadata_to_ipfs(ipfs_client, metadata: dict) -> str:
  """Uploads metadata to IPFS and returns the CID."""
  metadata_json = json.dumps(metadata)
  metadata_file = "metadata.json"
  with open(metadata_file, "w") as f:
      f.write(metadata_json)
  cid = ipfs_client.add(metadata_file)["Hash"]
  os.remove(metadata_file)  # Clean up after upload
  return cid

# Function to fetch data from IPFS using the CID
def fetch_ipfs_data(cid, ipfs_gateway_url):
    # Send a POST request to fetch the CID data from IPFS
    response = requests.post(ipfs_gateway_url, params={'arg': cid})
    response.raise_for_status(
    )  # Raise an error if the response is not successful
    return response.json()  # Return the response JSON
