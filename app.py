import zipfile
import os
import logging
from dotenv import load_dotenv
import ipfsApi
import asyncio
from flask import jsonify, request, Flask, send_file
from utils.iota_utils import load_wallet
from utils.registry_utils import initialize_registry
from utils.file_transfer_utils import create_zip, convert_to_bytes, cleanup_files
from utils.voting_utils import ModelVotingManager
from db_models.models import db, ModelRegistry
from nio import AsyncClient
from flask.typing import ResponseReturnValue
import torch
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from model_pipelines.Teacher_Model import TeacherModel
from model_pipelines.Student_Model import StudentModel
from transformers import AutoConfig, AutoModel, AutoTokenizer
from typing import Optional
from io import BytesIO


# Load environment variables
load_dotenv('.env.example')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize teacher and student models
try:
    teacher_model = torch.load('teacher_model.pt')
except Exception as e:
    logger.error(f"Error loading teacher model: {e}")
    teacher_model = TeacherModel()

try:
    student_model = torch.load('student_model.pt')
except Exception as e:
    logger.error(f"Error loading student model: {e}")
    student_model = StudentModel()

# Load wallet for account interaction
ACCOUNT_HOLDER_NAME = os.getenv('ACCOUNT_HOLDER_NAME')
wallet, account = load_wallet(name=ACCOUNT_HOLDER_NAME)

# Initialize IPFS Client
IPFS_SERVER_IP = os.getenv('IPFS_SERVER_IP')
IPFS_SERVER_PORT = int(os.getenv('IPFS_SERVER_PORT', 5001))
ipfs_client = ipfsApi.Client(IPFS_SERVER_IP, IPFS_SERVER_PORT)

# Initialize Matrix Client for Voting
MATRIX_SERVER_URI = os.getenv('MATRIX_SERVER_URI', 'http://socialxmatch.com')
MATRIX_BOT_USERNAME = os.getenv('MATRIX_BOT_USERNAME', '@bot@socialxmatch.com')
matrix_client = AsyncClient(MATRIX_SERVER_URI, MATRIX_BOT_USERNAME)
MATRIX_PASSWORD = os.getenv('MATRIX_PASSWORD')

VOTING_ROOMS = os.getenv('VOTING_ROOMS')
VOTING_DURATION = int(os.getenv('VOTING_DURATION', 300))

# Define IPFS gateway URL
ipfs_gateway_url = os.getenv('IPFS_GATEWAY_URI')

# Flask app initialization
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize voting manager
voting_manager = ModelVotingManager(
    matrix_client=matrix_client,
    ipfs_client=ipfs_client,
    account=account,
    MATRIX_PASSWORD=MATRIX_PASSWORD,
    VOTING_DURATION=VOTING_DURATION,
    VOTING_ROOMS=VOTING_ROOMS,
    db=db
)

# Initialize the database
db.init_app(app)

# Initialize the registry
initialize_registry(app=app, db=db)

# Directory to save uploaded models
MODEL_SAVE_DIR = os.getenv('MODEL_SAVE_DIR', '/models')
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

@app.route("/add_model", methods=["POST"])
async def add_model() -> ResponseReturnValue:
    """API endpoint to add a complete Hugging Face model as a zip file."""
    try:
        # Retrieve form data
        model_name: Optional[str] = request.form.get("model_name")
        task: Optional[str] = request.form.get("task")
        tokenizer_zip = request.files.get("tokenizer.zip")
        model_zip = request.files.get("model.zip")

        # Validate input
        if not all([model_name, model_zip]):
            logger.error("Missing required parameters.")
            return jsonify({"error": "Missing required parameters"}), 400

        # Create directories for the model and tokenizer
        model_dir = os.path.join(MODEL_SAVE_DIR, model_name, 'weights')
        tokenizer_dir = os.path.join(MODEL_SAVE_DIR, model_name, 'tokenizer')
        os.makedirs(model_dir, exist_ok=True)
        os.makedirs(tokenizer_dir, exist_ok=True)


        # Save and extract zip files
        zip_path = os.path.join(MODEL_SAVE_DIR, f"{model_name}.zip")
        model_zip.save(zip_path)
        tokenizer_zip_path = os.path.join(MODEL_SAVE_DIR, f"{model_name}_tokenizer.zip")
        tokenizer_zip.save(tokenizer_zip_path)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(model_dir)

        with zipfile.ZipFile(tokenizer_zip_path, 'r') as zip_ref:
            zip_ref.extractall(tokenizer_dir)

        # Verify the presence of key files
        required_files = ["pytorch_model.bin", "config.json"]
        for required_file in required_files:
            if not os.path.exists(os.path.join(model_dir, required_file)):
                logger.error(f"Missing required file: {required_file}")
                return jsonify({"error": f"Missing required file: {required_file}"}), 400

        # Load model and tokenizer
        config_path = os.path.join(model_dir, "config.json")
        config = AutoConfig.from_pretrained(config_path)
        model = AutoModel.from_pretrained(model_dir, config=config)
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir)

        # Add the model to teacher and student models
        def update_teacher_model():
            teacher_model.add_model(task, model_name, "model", model)
            teacher_model.add_model(task, model_name, "tokenizer", tokenizer)
            return teacher_model

        student_model.add_model(task, "model", model)
        student_model.add_model(task, "tokenizer", tokenizer)

        # Create a new model entry in the database
        model_id = str(uuid4())
        new_model = ModelRegistry( #type : ignore
            model_name=model_name,
            nft_id='pending',
            status='pending'
        )
        db.session.add(new_model)

        # Schedule the voting task in the background
        asyncio.create_task(
            voting_manager.count_votes_for_model(
                model_name,
                model_id,
                student_model,
                update_teacher_model
            )
        )

        logger.info(f"Voting started for model: {model_name}")
        return jsonify({
            "status": "Voting in progress",
            "model_name": model_name
        }), 202

    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Database Integrity Error: {str(e)}")
        return jsonify({"error": "Model with this name already exists"}), 409
    except zipfile.BadZipFile as e:
        logger.error(f"Bad Zip File: {str(e)}")
        return jsonify({"error": "Invalid zip file provided."}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": str(e)}), 500



@app.route("/fetch_model", methods=["GET"])
def fetch_model() -> ResponseReturnValue:
    """
    Fetch approved model files either by name or by NFT ID.
    Fetches the corresponding teacher and student model files from IPFS and sends them as a zip archive.
    """
    model_name: Optional[str] = request.args.get("model_name")
    nft_id: Optional[str] = request.args.get("nft_id")

    # Validate input parameters
    if not model_name and not nft_id:
        logger.error("No model_name or nft_id provided.")
        return jsonify({"error": "Provide either model_name or nft_id"}), 400

    if model_name == 'test_model':
        logger.error("Model name 'test_model' is not allowed.")
        return jsonify({'error': 'Name not allowed'}), 400

    try:
        # Handle the special case for 'test_model'
        if model_name == 'test_model':
            student_file_path = 'student_model_testing.pt'
            teacher_file_path = 'teacher_model_testing.pt'

            # Save models for testing (consider moving model creation elsewhere for production)
            torch.save(student_model, student_file_path)
            torch.save(teacher_model, teacher_file_path)
            zip_path = 'test_model.pt'

            try:
                # Create a ZIP archive containing the two model files
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    zipf.write(student_file_path)
                    zipf.write(teacher_file_path)

                logger.info("Created zip file for test models.")
                # Serve the ZIP file for download
                return send_file(zip_path, as_attachment=True)

            finally:
                # Cleanup temporary files after serving
                cleanup_files([student_file_path, teacher_file_path, zip_path])             
                logger.info(f"Removed file: {zip_path}")

        # Fetch model from the database based on provided name or NFT ID
        model = None
        if model_name:
            model = ModelRegistry.query.filter_by(model_name=model_name, status='approved').first()
        elif nft_id:
            model = ModelRegistry.query.filter_by(nft_id=nft_id, status='approved').first()

        # If model is not found, return a 404 error
        if not model:
            logger.error(f"Model with name '{model_name}' or NFT ID '{nft_id}' not found.")
            return jsonify({"error": "Approved model not found"}), 404

        # Fetch model files from IPFS
        teacher_model_data = ipfs_client.cat(model.teacher_model_cid)
        student_model_data = ipfs_client.cat(model.student_model_cid)

        # Ensure the data is in byte format
        teacher_model_data = convert_to_bytes(teacher_model_data)
        student_model_data = convert_to_bytes(student_model_data)

        # Create in-memory files for the models
        teacher_model_io = BytesIO(teacher_model_data)
        student_model_io = BytesIO(student_model_data)

        # Create a ZIP file containing both models
        zip_file = create_zip(student_model_io, teacher_model_io, model.model_name)

        logger.info(f"Created zip file for model '{model.model_name}'.")
        # Return the ZIP file as a response
        return send_file(
            zip_file,
            as_attachment=True,
            download_name=f"{model.model_name}_model_files.zip",
            mimetype="application/zip"
        )

    except Exception as e:
        logger.exception("Error occurred while fetching model files.")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure database is created
    with app.app_context():
        db.create_all()

    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
