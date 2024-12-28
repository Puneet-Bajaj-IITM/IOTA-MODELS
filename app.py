
import zipfile
import os
from dotenv import load_dotenv
import ipfsApi
from flask import jsonify, request, Flask, send_file
from utils.iota_utils import load_wallet
from utils.registry_utils import initialize_registry
from utils.file_transfer_utils import create_zip
import io
from utils.voting_utils import ModelVotingManager
from models.models import db, ModelRegistry, ModelVote
from nio import AsyncClient
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from model_pipelines.Teacher_Model import TeacherModel
from model_pipelines.Student_Model import StudentModel
from transformers import AutoConfig, AutoModel, AutoTokenizer

load_dotenv('.env.example')

teacher_model = TeacherModel()
student_model = StudentModel()

wallet, account = load_wallet(name='Alice')

# IPFS Client
ipfs_client = ipfsApi.Client('179.61.246.8', 5001)

# Matrix Client for Voting
matrix_client = AsyncClient("https://socialxmatch.com", "@bot_user:socialxmatch.com")
MATRIX_PASSWORD = "Hosting+123321"

VOTING_ROOMS = ["!4JVUuZfXSS0XfgU9:socialxmatch.com"]

VOTING_DURATION = 300  # 5 minutes

# Define the base IPFS gateway URL
ipfs_gateway_url = "http://179.61.246.8:5001/api/v0/dag/get"

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///model_registry.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Usage in main application
voting_manager = ModelVotingManager(
    matrix_client=matrix_client,
    ipfs_client=ipfs_client,
    account=account,
    MATRIX_PASSWORD=MATRIX_PASSWORD,
    VOTING_DURATION=VOTING_DURATION, 
    VOTING_ROOMS=VOTING_ROOMS,
    db=db
)

db.init_app(app)

# Initialize the registry
initialize_registry(app=app, db=db)

# Directory to save uploaded models
MODEL_SAVE_DIR = "uploaded_model"
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

@app.route("/add_model", methods=["POST"])
async def add_model():
    """API endpoint to add a complete Hugging Face model as a zip file."""
    try:
        # Retrieve form data
        model_name = request.form.get("model_name")
        task = request.form.get("task")

        tokenizer_zip = request.files.get("tokenizer.zip")
        
        model_zip = request.files.get("model_zip")

        # Validate input
        if not all([model_name, model_zip]):
            return jsonify({"error": "Missing required parameters"}), 400

        # Create a directory for the new model
        model_dir = os.path.join(MODEL_SAVE_DIR, model_name, 'weights')
        tokenizer_dir = os.path.join(MODEL_SAVE_DIR, model_name, 'tokenizer')
        os.makedirs(model_dir, exist_ok=True)

        # Save and extract the zip file
        zip_path = os.path.join(MODEL_SAVE_DIR, f"{model_name}.zip")
        model_zip.save(zip_path)
        tokenizer_zip = os.path.join(MODEL_SAVE_DIR, f"{model_name}_tokenizer.zip")
        tokenizer_zip.save(tokenizer_zip)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(model_dir)

        with zipfile.ZipFile(tokenizer_zip, 'r') as zip_ref:
            zip_ref.extractall(tokenizer_dir)

        # Optionally, verify the presence of key files
        required_files = ["pytorch_model.bin", "config.json"]
        for required_file in required_files:
            if not os.path.exists(os.path.join(model_dir, required_file)):
                return jsonify(
                    {"error": f"Missing required file: {required_file}"}
                ), 400


        config_path = os.path.join(model_dir, "config.json")
        config = AutoConfig.from_pretrained(config_path)
        model = AutoModel.from_pretrained(model_dir, config=config)
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir)

        teacher_model.add_model(task, model_name, "model", model)
        teacher_model.add_model(task, model_name, "tokenizer", tokenizer)

        student_model.add_model(task, "model", model)
        student_model.add_model(task, "tokenizer", tokenizer)

        # # Save files locally or process them
        # weights_path = f"/tmp/{weights_file.filename}"
        # config_path = f"/tmp/{config_file.filename}"
        # weights_file.save(weights_path)
        # config_file.save(config_path)

        model_id = str(uuid4())


        new_model = ModelRegistry(# type: ignore
            model_name=model_name,
            nft_id='pending',
            status='pending'
        )
        db.session.add(new_model)

        # Create voting record
        vote_record = ModelVote(# type: ignore
            model_name=model_name,
            yes_votes=0,
            no_votes=0
        )
        db.session.add(vote_record)

        # Broadcast for voting
        is_approved = await voting_manager.count_votes_for_model(
            model_name, 
            model_id,
            zip_path
        )

        if is_approved:
            db.session.commit()

        return jsonify({
            "status": "Voting in progress",
            "model_name": model_name
        }), 202

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Model with this name already exists"}), 409
    except zipfile.BadZipFile:
        return jsonify({"error": "Invalid zip file provided."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
        

# @app.route("/fetch_model", methods=["GET"])
# def fetch_model():
#     """Fetch model files by name or NFT ID."""
#     model_name = request.args.get("model_name")
#     model = None
#     nft_id = request.args.get("nft_id")

#     if not model_name and not nft_id:
#         return jsonify({"error": "Provide either model_name or nft_id"}), 400

#     try:
#         # Fetch metadata from the database based on model_name or nft_id
#         if model_name:
#             model = ModelRegistry.query.filter_by(
#                 model_name=model_name, status='approved').first()
#         else:
#             model = ModelRegistry.query.filter_by(
#                 nft_id=nft_id, status='approved').first()

#         if not model:
#             return jsonify({"error": "Approved model not found"}), 404

#         # Get the CID values from the model metadata
#         weights_cid = model.weights_cid
#         config_cid = model.config_cid
        
#         # Fetch the weights and config files from IPFS using the CIDs
#         weights_data = fetch_ipfs_data(
#             cid=weights_cid, 
#             ipfs_gateway_url=ipfs_gateway_url
#         )
        
#         config_data = fetch_ipfs_data(
#             cid=config_cid, 
#             ipfs_gateway_url=ipfs_gateway_url
#         )
        
#         # Extract the byte data from the response (base64 encoded)
#         weights_base64 = weights_data['Data']['/']['bytes']
#         config_base64 = config_data['Data']['/']['bytes']


#         # Decode the base64 data into bytes
#         weights_base64_fixed = fix_base64_padding(weights_base64)
#         config_base64_fixed = fix_base64_padding(config_base64)

#         # Decode the base64 data into bytes
#         weights_bytes = base64.b64decode(weights_base64_fixed)
#         config_bytes = base64.b64decode(config_base64_fixed)

#         # Create in-memory files using BytesIO
#         weights_io = io.BytesIO(weights_bytes)
#         config_io = io.BytesIO(config_bytes)

#         # In the fetch_model function
#         zip_file = create_zip(
#             weights_io=weights_io, 
#             config_io=config_io, 
#             model_name=model_name
#         )

#         # Return the ZIP file
#         return send_file(
#             zip_file,
#             as_attachment=True,
#             download_name=f"{model_name}_model_files.zip",
#             mimetype="application/zip"
#         )


#     except Exception as e:
#         # Return error details if anything goes wrong
#         return jsonify({"error": str(e)}), 500


@app.route("/fetch_model", methods=["GET"])
def fetch_model():
    """Fetch approved model files by name or NFT ID."""
    model_name = request.args.get("model_name")
    nft_id = request.args.get("nft_id")

    if not model_name and not nft_id:
        return jsonify({"error": "Provide either model_name or nft_id"}), 400

    try:
        # Find the model
        if model_name:
            model = ModelRegistry.query.filter_by(
                model_name=model_name, status='approved').first()
        else:
            model = ModelRegistry.query.filter_by(
                nft_id=nft_id, status='approved').first()

        if not model:
            return jsonify({"error": "Approved model not found"}), 404

        # Fetch files from IPFS
        weights_data = ipfs_client.cat(model.weights_cid)
        config_data = ipfs_client.cat(model.config_cid)
        
        if not isinstance(weights_data, bytes):
            weights_data = weights_data.encode("utf-8")  # Convert to bytes if it's a string
        if not isinstance(config_data, bytes):
            config_data = config_data.encode("utf-8")  # Convert to bytes if it's a string

        # Create in-memory files
        weights_io = io.BytesIO(weights_data)
        config_io = io.BytesIO(config_data)

        # Create and return ZIP
        zip_file = create_zip(weights_io, config_io, model.model_name)
        return send_file(
            zip_file,
            as_attachment=True,
            download_name=f"{model.model_name}_model_files.zip",
            mimetype="application/zip"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure database is created
    with app.app_context():
        db.create_all()

    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)