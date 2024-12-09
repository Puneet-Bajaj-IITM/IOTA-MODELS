import os
from dotenv import load_dotenv
from iota_sdk import ClientOptions, CoinType, StrongholdSecretManager, Wallet
import os
import json
import base64
from dotenv import load_dotenv
from iota_sdk import MintNftParams, Utils, Wallet, utf8_to_hex
import ipfsApi
from flask import jsonify, request, Blueprint, make_response, abort

load_dotenv('.env.example')
import shutil

# Removes the directory and all its contents
shutil.rmtree('example-walletdb')
os.remove('example.stronghold')

node_url = os.environ.get('NODE_URL', 'https://api.testnet.shimmer.network')
client_options = ClientOptions(nodes=[node_url])

ISSUER_ID = os.getenv('ISSUER_ID')

# Shimmer coin type
coin_type = CoinType.SHIMMER

for env_var in ['STRONGHOLD_PASSWORD', 'MNEMONIC']:
    if env_var not in os.environ:
        raise Exception(f".env {env_var} is undefined, see .env.example")

secret_manager = StrongholdSecretManager(
    os.environ['STRONGHOLD_SNAPSHOT_PATH'], os.environ['STRONGHOLD_PASSWORD'])

try:
    wallet = Wallet(os.environ['WALLET_DB_PATH'], client_options, coin_type,
                    secret_manager)

    wallet.store_mnemonic(os.environ['MNEMONIC'])

    account = wallet.create_account('Alice')
    print("Account created:", account.get_metadata())
except:
    wallet.destroy()
    wallet = Wallet(os.environ['WALLET_DB_PATH'], secret_manager)

    account = wallet.get_account('Alice')
account.sync()

# Load environment variables
load_dotenv()

# IPFS Client Initialization
ipfs_client = ipfsApi.Client('179.61.246.8', 5001)

# account.sync()  # Sync account with the node



# Helper: Upload metadata to IPFS and return CID
def upload_metadata_to_ipfs(metadata: dict) -> str:
    """Uploads metadata to IPFS and returns the CID."""
    metadata_json = json.dumps(metadata)
    metadata_file = "metadata.json"
    with open(metadata_file, "w") as f:
        f.write(metadata_json)
    cid = ipfs_client.add(metadata_file)["Hash"]
    os.remove(metadata_file)  # Clean up after upload
    return cid


# Mint a single NFT with metadata on IPFS
def mint_nft_with_ipfs(metadata: dict):
    """Mint a single NFT with metadata stored on IPFS."""
    print("Uploading metadata to IPFS...")
    cid = upload_metadata_to_ipfs(metadata)
    cid_hex = utf8_to_hex(cid)

    print("Sending NFT minting transaction...")
    params = MintNftParams(immutableMetadata=cid_hex)
    transaction = account.mint_nfts([params])

    # Wait for transaction inclusion
    block_id = account.retry_transaction_until_included(
        transaction.transactionId)
    print(f'Block sent: {os.environ["EXPLORER_URL"]}/block/{block_id}')

    # Extract NFT ID
    essence = transaction.payload["essence"]
    for outputIndex, output in enumerate(essence["outputs"]):
        if output["type"] == 6 and output[
                "nftId"] == '0x0000000000000000000000000000000000000000000000000000000000000000':
            outputId = Utils.compute_output_id(transaction.transactionId,
                                               outputIndex)
            nftId = Utils.compute_nft_id(outputId)
            print(f'New minted NFT ID: {nftId}')
    return cid, nftId


# Mint a collection of NFTs with metadata stored on IPFS
def mint_nft_collection_with_ipfs(metadata_list: list, issuer_nft_id: str):
    """Mint a collection of NFTs with their metadata stored on IPFS."""
    print(f"Starting minting of {len(metadata_list)} NFTs...")
    minted_nft_ids = []
    bech32_hrp = wallet.get_client().get_bech32_hrp()
    issuer = Utils.nft_id_to_bech32(issuer_nft_id, bech32_hrp)

    for metadata in metadata_list:
        cid = upload_metadata_to_ipfs(metadata)
        cid_hex = utf8_to_hex(cid)
        params = MintNftParams(immutableMetadata=cid_hex, issuer=issuer)

        transaction = account.mint_nfts([params])
        block_id = account.retry_transaction_until_included(
            transaction.transactionId)
        print(f'Block sent: {os.environ["EXPLORER_URL"]}/block/{block_id}')

        # Extract NFT ID
        essence = transaction.payload["essence"]
        for outputIndex, output in enumerate(essence["outputs"]):
            if output["type"] == 6 and output["nftId"] == ISSUER_ID:
                outputId = Utils.compute_output_id(transaction.transactionId,
                                                   outputIndex)
                nftId = Utils.compute_nft_id(outputId)
                minted_nft_ids.append({"cid": cid, "nftId": nftId})
                print(f'New minted NFT ID: {nftId}')
    return minted_nft_ids


def initialize_registry(app):
    """Initialize the database and create the model registry table."""
    app.config[
        "SQLALCHEMY_DATABASE_URI"] = "sqlite:///models_registry.db"  # Update for your DB
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()


def update_registry(model_name, nft_id, weights_cid, config_cid):
    """Add or update a model in the registry."""
    try:
        with db.session.begin_nested():  # Use transaction safety
            # Check if the model exists
            model = ModelRegistry.query.filter_by(
                model_name=model_name).first()
            if model:
                model.nft_id = nft_id
                model.weights_cid = weights_cid
                model.config_cid = config_cid
            else:
                # Add a new record
                new_model = ModelRegistry(model_name=model_name,
                                          nft_id=nft_id,
                                          weights_cid=weights_cid,
                                          config_cid=config_cid)
                db.session.add(new_model)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e


import requests, io


def nft_id_to_cid(nft_id):
    """Resolve metadata CIDs from an NFT ID."""
    model = ModelRegistry.query.filter_by(nft_id=nft_id).first()
    if not model:
        raise ValueError("NFT ID not found in registry.")
    return {
        "weights_cid": model.weights_cid,
        "config_cid": model.config_cid,
        "model_name": model.model_name
    }



from flask import send_file
import io
import zipfile

# Create a ZIP file in memory
def create_zip(weights_io, config_io, model_name):
    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(f"{model_name}_weights.pth", weights_io.getvalue())
        zipf.writestr(f"{model_name}_config.json", config_io.getvalue())
    zip_io.seek(0)  # Rewind the buffer to the beginning
    return zip_io



# Define the base IPFS gateway URL
ipfs_gateway_url = "http://179.61.246.8:5001/api/v0/dag/get"

# Function to fetch data from IPFS using the CID
def fetch_ipfs_data(cid):
    # Send a POST request to fetch the CID data from IPFS
    response = requests.post(ipfs_gateway_url, params={'arg': cid})
    response.raise_for_status(
    )  # Raise an error if the response is not successful
    return response.json()  # Return the response JSON



# Fix the padding for base64 (if needed)
def fix_base64_padding(base64_str):
    return base64_str + '=' * (4 - len(base64_str) % 4)  # Add padding to base64 string





from flask import Flask

app = Flask(__name__)

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class ModelRegistry(db.Model):
    __tablename__ = "model_registry"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    model_name = db.Column(db.String(255), unique=True, nullable=False)
    nft_id = db.Column(db.String(255), nullable=False)
    weights_cid = db.Column(db.String(255), nullable=False)
    config_cid = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize the registry
initialize_registry(app)


@app.route("/add_model", methods=["POST"])
def add_model():
    """API endpoint to add a new ML model."""
    try:
        model_name = request.form["model_name"]
        weights_file = request.files["weights_file"]
        config_file = request.files["config_file"]
        print(model_name)

        # Save files locally or process them
        weights_path = f"/tmp/{weights_file.filename}"
        config_path = f"/tmp/{config_file.filename}"
        weights_file.save(weights_path)
        config_file.save(config_path)

        # Upload files to IPFS
        weights_cid = ipfs_client.add(weights_path)[0]['Hash']
        # print(weights_cid)
        config_cid = ipfs_client.add(config_path)[0]["Hash"]

        # Mint NFT
        metadata = {
            "model_name": model_name,
            "weights_cid": weights_cid,
            "config_cid": config_cid,
            "timestamp": datetime.now().isoformat()
        }
        cid, nft_id = mint_nft_with_ipfs(metadata)

        # Update database registry
        update_registry(model_name, nft_id, weights_cid, config_cid)

        return jsonify({
            "status": "success",
            "nft_id": nft_id,
            "weights_cid": weights_cid,
            "config_cid": config_cid
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/fetch_model", methods=["GET"])
def fetch_model():
    """Fetch model files by name or NFT ID."""
    model_name = request.args.get("model_name")
    nft_id = request.args.get("nft_id")

    if not model_name and not nft_id:
        return jsonify({"error": "Provide either model_name or nft_id"}), 400

    try:
        # Fetch metadata from the database based on model_name or nft_id
        if model_name:
            model = ModelRegistry.query.filter_by(
                model_name=model_name).first()
        elif nft_id:
            model = nft_id_to_cid(
                nft_id)  # Assuming nft_id_to_cid fetches data by NFT ID
        # If model is not found, return an error
        if not model:
            return jsonify({"error": "Model not found in registry"}), 404

        # Get the CID values from the model metadata
        weights_cid = model.weights_cid
        config_cid = model.config_cid
        
        # Fetch the weights and config files from IPFS using the CIDs
        weights_data = fetch_ipfs_data(weights_cid)
        config_data = fetch_ipfs_data(config_cid)
        
        # Extract the byte data from the response (base64 encoded)
        weights_base64 = weights_data['Data']['/']['bytes']
        config_base64 = config_data['Data']['/']['bytes']


        # Decode the base64 data into bytes
        weights_base64_fixed = fix_base64_padding(weights_base64)
        config_base64_fixed = fix_base64_padding(config_base64)

        # Decode the base64 data into bytes
        weights_bytes = base64.b64decode(weights_base64_fixed)
        config_bytes = base64.b64decode(config_base64_fixed)

        # Create in-memory files using BytesIO
        weights_io = io.BytesIO(weights_bytes)
        config_io = io.BytesIO(config_bytes)

        # In the fetch_model function
        zip_file = create_zip(weights_io, config_io, model_name)

        # Return the ZIP file
        return send_file(
            zip_file,
            as_attachment=True,
            download_name=f"{model_name}_model_files.zip",
            mimetype="application/zip"
        )


    except Exception as e:
        # Return error details if anything goes wrong
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
