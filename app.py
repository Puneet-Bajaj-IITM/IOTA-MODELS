
from dotenv import load_dotenv
import base64
import ipfsApi
from flask import jsonify, request, Flask, send_file
from iota_utils import load_wallet, mint_nft_with_ipfs
from datetime import datetime
from registry_utils import initialize_registry, update_registry, nft_id_to_cid
from file_transfer_utils import fix_base64_padding, create_zip
from ipfs_utils import fetch_ipfs_data
import io
from models import db, ModelRegistry

load_dotenv('.env.example')

wallet, account = load_wallet(name='Alice')


# IPFS Client
ipfs_client = ipfsApi.Client('179.61.246.8', 5001)

# Matrix Client for Voting
matrix_client = AsyncClient("https://socialxmatch.com", "@bot_user:socialxmatch.com")
VOTING_ROOMS = ["!4JVUuZfXSS0XfgU9:socialxmatch.com"]
VOTING_DURATION = 300  # 5 minutes

# Define the base IPFS gateway URL
ipfs_gateway_url = "http://179.61.246.8:5001/api/v0/dag/get"

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///model_registry.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Initialize the registry
initialize_registry(app=app, db=db)


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
        cid, nft_id = mint_nft_with_ipfs(
            ipfs_client=ipfs_client, 
            account=account, 
            metadata=metadata
        )

        # Update database registry
        update_registry(
            db=db, 
            model_name=model_name, 
            nft_id=nft_id, 
            weights_cid=weights_cid, 
            config_cid=config_cid, 
            ModelRegistry=ModelRegistry
        )

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
    model = None
    nft_id = request.args.get("nft_id")

    if not model_name and not nft_id:
        return jsonify({"error": "Provide either model_name or nft_id"}), 400

    try:
        # Fetch metadata from the database based on model_name or nft_id
        if model_name:
            model = ModelRegistry.query.filter_by(
                model_name=model_name
            ).first()
            
        elif nft_id:
            model = nft_id_to_cid(
                nft_id=nft_id,
                ModelRegistry=ModelRegistry
            )  # Assuming nft_id_to_cid fetches data by NFT ID
        # If model is not found, return an error
        if not model:
            return jsonify({"error": "Model not found in registry"}), 404

        # Get the CID values from the model metadata
        weights_cid = model.weights_cid
        config_cid = model.config_cid
        
        # Fetch the weights and config files from IPFS using the CIDs
        weights_data = fetch_ipfs_data(
            cid=weights_cid, 
            ipfs_gateway_url=ipfs_gateway_url
        )
        
        config_data = fetch_ipfs_data(
            cid=config_cid, 
            ipfs_gateway_url=ipfs_gateway_url
        )
        
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
        zip_file = create_zip(
            weights_io=weights_io, 
            config_io=config_io, 
            model_name=model_name
        )

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
