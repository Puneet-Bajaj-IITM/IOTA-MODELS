# app.py
import zipfile
import os
import logging
from dotenv import load_dotenv
import ipfsApi
import base64
from db_models.models import ModelRegistry, ModelVote
from flask import jsonify, request, Flask, send_file
from utils.iota_utils import load_wallet
from utils.registry_utils import initialize_registry
from utils.file_transfer_utils import create_zip, cleanup_files, fix_base64_padding
from utils.ipfs_utils import fetch_ipfs_data
from utils.voting_utils import ModelVotingManager
from db_models.models import db, ModelRegistry
from nio import AsyncClient
from flask.typing import ResponseReturnValue
import torch    
import asyncio
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from model_pipelines.Teacher_Model import TeacherModel
from model_pipelines.Student_Model import StudentModel
from model_pipelines.Global_Model import GlobalModel
from transformers import AutoConfig, AutoModel, AutoTokenizer
from typing import Optional
from celery import Celery
from datetime import datetime, UTC
from io import BytesIO
from functools import lru_cache
from flask_cors import CORS
import asyncio
import nest_asyncio

nest_asyncio.apply()

# Load environment variables
load_dotenv('.env.example')
VOTING_ROOMS=["!4JVUuZfXSS0XfgU9:socialxmatch.com"]


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
ACCOUNT_HOLDER_NAME = os.getenv('ACCOUNT_HOLDER_NAME')
IPFS_SERVER_IP = os.getenv('IPFS_SERVER_IP')
IPFS_SERVER_PORT = int(os.getenv('IPFS_SERVER_PORT', 5001))
MATRIX_SERVER_URI = os.getenv('MATRIX_SERVER_URI', 'http://socialxmatch.com')
MATRIX_BOT_USERNAME = os.getenv('MATRIX_BOT_USERNAME', '@bot@socialxmatch.com')
MATRIX_PASSWORD = os.getenv('MATRIX_PASSWORD')
VOTING_DURATION = int(os.getenv('VOTING_DURATION', 300))
MODEL_SAVE_DIR = os.getenv('MODEL_SAVE_DIR', '/models')

# Flask app initialization
app = Flask(__name__)
app.config.update(
    SQLALCHEMY_DATABASE_URI=os.getenv('SQLALCHEMY_DATABASE_URI'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    CELERY_BROKER_URL='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0'
)
CORS(app) 


# Client factories
@lru_cache()
def get_matrix_client():
    return AsyncClient(MATRIX_SERVER_URI, MATRIX_BOT_USERNAME)

@lru_cache()
def get_ipfs_client():
    return ipfsApi.Client(IPFS_SERVER_IP, IPFS_SERVER_PORT)

@lru_cache()
def get_wallet():
    return load_wallet(name=ACCOUNT_HOLDER_NAME)

# Model management
class ModelManager:
    @staticmethod
    def load_or_create_model(model_path: str, model_class):
        try:
            return torch.load(model_path, weights_only=True)
        except Exception as e:
            logger.warning(f"Failed to load model from {model_path}: {e}")
            return model_class()

    @staticmethod
    def initialize_models():
        return {
            'teacher': ModelManager.load_or_create_model('teacher_model.pt', TeacherModel),
            'student': ModelManager.load_or_create_model('student_model.pt', StudentModel),
            'global': ModelManager.load_or_create_model('global_model.pt', GlobalModel)
        }

# Initialize components
models = ModelManager.initialize_models()
ipfs_client = get_ipfs_client()
matrix_client = get_matrix_client()

# Initialize registry
initialize_registry(app=app, db=db)
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

from celery import Celery
from inspect import isawaitable


class AsyncCelery(Celery):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.patch_task()

        if 'app' in kwargs:
            self.init_app(kwargs['app'])

    def patch_task(self):
        TaskBase = self.Task

        class ContextTask(TaskBase):
            abstract = True

            async def _run(self, *args, **kwargs):
                result = TaskBase.__call__(self, *args, **kwargs)
                if isawaitable(result):
                    await result

            def __call__(self, *args, **kwargs):
                asyncio.run(self._run(*args, **kwargs))

        self.Task = ContextTask

    def init_app(self, app):
        self.app = app

        conf = {}
        for key in app.config.keys():
            if key[0:7] == 'CELERY_':
                conf[key[7:].lower()] = app.config[key]

        if 'broker_transport_options' not in conf and conf.get('broker_url', '')[0:4] == 'sqs:':
            conf['broker_transport_options'] = {'region': 'eu-west-1'}

        self.config_from_object(conf)


# Initialize Celery
celery = AsyncCelery(
    app.name,
    broker='redis://localhost:6379/0',  # Use Redis as the broker
    backend='redis://localhost:6379/0'  # Optional: Use Redis for results
    )
celery.conf.update(app.config)
celery.conf.update(
    task_always_eager=False,
    worker_pool='gevent',
    worker_concurrency=4,  # Adjust to your needs
)

# Celery task
@celery.task(bind=True)
async def count_votes_for_model_task(self, model_name: str, model_id: str, task: str):
    await _count_votes_for_model_task(model_name, model_id, task)


from textwrap import dedent
async def _count_votes_for_model_task(model_name: str, model_id: str, task: str):
    """Celery task for counting votes on a model."""
    
    # Initialize task-specific instances
    models = ModelManager.initialize_models()
    voting_manager = ModelVotingManager(
        app=app,
        matrix_client=get_matrix_client(),
        ipfs_client=get_ipfs_client(),
        account=get_wallet()[1],
        MATRIX_PASSWORD=MATRIX_PASSWORD,
        VOTING_DURATION=VOTING_DURATION,
        VOTING_ROOMS=VOTING_ROOMS,
        db=db
    )
    with app.app_context():
        try:
            # Load model files
            model_dir = os.path.join(MODEL_SAVE_DIR, model_name, 'weights')
            tokenizer_dir = os.path.join(MODEL_SAVE_DIR, model_name, 'tokenizer')
            
            config = AutoConfig.from_pretrained(os.path.join(model_dir, "config.json"))
            model = AutoModel.from_pretrained(model_dir, config=config)
            tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir)

            print('Done model loading')
            
            # Update student model
            models['student'].add_model(task=task, model_type="model", value=model)
            models['student'].add_model(task=task, model_type="tokenizer", value=tokenizer)

            print('updated student model')

            def update_teacher_model():
                # Update models
                models['teacher'].add_model(task, model_name, "model", model)
                models['teacher'].add_model(task, model_name, "tokenizer", tokenizer)

                models['global'].add_model("model", model)
                models['global'].add_model("tokenizer", tokenizer)

                return models['teacher'], models['global']
            
            # Process voting
            print('starting voting')
        
                    # Create voting session
            voting_session = ModelVote( # type: ignore
                model_name=model_name,
                yes_votes=0,
                no_votes=0,
                voting_start=datetime.now(UTC)
            )

            db.session.add(voting_session)
            db.session.commit()

            # Broadcast voting proposal
            print('Broadcast voting message')
            voting_message = dedent(f"""
                MODEL VOTING PROPOSAL
                --------------------
                Model Name: {model_name}
                Model ID: {model_id}
                
                VOTING INSTRUCTIONS:
                - Reply 'yes {model_id}' to approve this model
                - Reply 'no {model_id}' to reject this model
                - Voting closes in {voting_manager.voting_duration // 60} minutes
            """)

            if voting_manager.voting_rooms is None:
                return jsonify({'Error': 'No Rooms for voting'})
            
            for room_id in voting_manager.voting_rooms:
                try:
                    await voting_manager.matrix_login()  # Ensure the login process is awaited
                    print(f'Attempting to send message to room {room_id}')
                    
                    res = await voting_manager.matrix_client.room_send(
                        room_id=room_id,
                        message_type="m.room.message",
                        content={
                            "msgtype": "m.text",
                            "body": voting_message
                        }
                    )
                    print(f'Sent message to room {room_id}')
                    print(res)

                except TimeoutError:
                    print(f"Timeout while sending message to room {room_id}")
                except Exception as e:
                    print(f"Failed to broadcast voting message: {e}")
                
            import time
            time.sleep(voting_manager.voting_duration) 
            print('Counting votes')
            db.session.refresh(voting_session)

            yes_votes, no_votes = await voting_manager.count_votes_for_model(model_id, voting_session)
            is_approved = voting_manager.finalize_voting(yes_votes, no_votes, model_name, models['student'], update_teacher_model)
                    # Broadcast results
            
            result_message = dedent(f"""
                MODEL VOTING RESULT
                -------------------
                Model: {model_name}
                Status: {"APPROVED" if is_approved else "REJECTED"}
            """)
            
            for room_id in voting_manager.voting_rooms:
                try:
                    await voting_manager.matrix_client.room_send(
                        room_id=room_id,
                        message_type="m.room.message",
                        content={
                            "msgtype": "m.text",
                            "body": result_message
                        }
                    )
                except Exception as e:
                    print(f"Failed to broadcast result: {e}")

            if is_approved:
            
                models['global'].add_model('model', model)
                models['global'].add_model('tokenizer', tokenizer)

                print('added to global')
                
                # Save updated models
                torch.save(models['global'], 'global_model.pt')

                print('saved all')
                
                # Update database status
                with app.app_context():
                    session = db.session()
                    try:
                        model_entry = session.query(ModelRegistry).filter_by(model_id=model_id).first()
                        if model_entry:
                            model_entry.status = 'approved'
                            session.commit()
                    finally:
                        session.close()
                
            
        except Exception as e:
            logger.error(f"Error in count_votes_for_model_task: {str(e)}")
            with app.app_context():
                # Update database status to failed
                session = db.session()
                try:
                    model_entry = session.query(ModelRegistry).filter_by(model_id=model_id).first()
                    if model_entry:
                        model_entry.status = 'failed'
                        session.commit()
                finally:
                    session.close()
                raise

@app.route("/add_model", methods=["POST"])
async def add_model() -> ResponseReturnValue:
    """API endpoint to add a complete Hugging Face model as a zip file."""
    try:
        # Retrieve form data
        model_name: Optional[str] = request.form.get("model_name")
        task: Optional[str] = request.form.get("task")
        tokenizer_zip = request.files.get("tokenizer.zip")
        model_zip = request.files.get("model.zip")

        if not all([model_name, task, model_zip, tokenizer_zip]):
            logger.error("Missing required parameters.")
            return jsonify({"error": "Missing required parameters"}), 400

        # Create directories and save files
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

        # Verify required files
        required_files = ["model.safetensors", "config.json"]
        for required_file in required_files:
            if not os.path.exists(os.path.join(model_dir, required_file)):
                logger.error(f"Missing required file: {required_file}")
                return jsonify({"error": f"Missing required file: {required_file}"}), 400

        # Create database entry
        model_id = str(uuid4())
        new_model = ModelRegistry(
            model_id=model_id,
            model_name=model_name,
            nft_id='pending',
            status='pending'
        )
        db.session.add(new_model)
        db.session.commit()

        # Start the Celery task
        count_votes_for_model_task.apply_async(kwargs={
            "model_name": model_name,
            "model_id": model_id,
            "task": task
        })

        logger.info(f"Voting started for model: {model_name}")
        return jsonify({
            "status": "Voting in progress",
            "model_name": model_name,
            "model_id": model_id
        }), 202

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in add_model: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/approved-models', methods=['GET'])
def get_approved_models():
    """Fetch all models where the status is 'approved'."""
    try:
        # Query models with status 'approved'
        approved_models = ModelRegistry.query.filter_by(status='approved').all()
        
        # Convert the result to a list of dictionaries
        models_list = []
        for model in approved_models:
            models_list.append({
                'model_id': model.model_id,
                'model_name': model.model_name,
                'nft_id': model.nft_id,
                'teacher_model_cid': model.teacher_model_cid,
                'student_model_cid': model.student_model_cid,
                'global_model_cid': model.global_model_cid,
                'created_at': model.created_at,
                'status': model.status
            })
        
        # Return the list of models in JSON format
        return jsonify(models_list), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/fetch_model", methods=["GET"])
def fetch_model() -> ResponseReturnValue:
    """Fetch approved model files."""
    model_name: Optional[str] = request.args.get("model_name")
    nft_id: Optional[str] = request.args.get("nft_id")

    if not model_name and not nft_id:
        return jsonify({"error": "Provide either model_name or nft_id"}), 400

    try:
        # Query the model
        model = None
        if model_name:
            model = ModelRegistry.query.filter_by(model_name=model_name, status='approved').first()
        elif nft_id:
            model = ModelRegistry.query.filter_by(nft_id=nft_id, status='approved').first()

        if not model:
            return jsonify({"error": "Approved model not found"}), 404

        # Fetch IPFS data
        teacher_model_data = fetch_ipfs_data(model.teacher_model_cid, f'http://{IPFS_SERVER_IP}:{IPFS_SERVER_PORT}')
        student_model_data = fetch_ipfs_data(model.student_model_cid, f'http://{IPFS_SERVER_IP}:{IPFS_SERVER_PORT}')
        global_model_data = fetch_ipfs_data(model.global_model_cid, f'http://{IPFS_SERVER_IP}:{IPFS_SERVER_PORT}')
        
        # Process the data
        teacher_model_data = teacher_model_data['Data']['/']['bytes']
        student_model_data = student_model_data['Data']['/']['bytes']
        global_model_data = global_model_data['Data']['/']['bytes']

        teacher_model_data = base64.b64decode(fix_base64_padding(teacher_model_data))
        student_model_data = base64.b64decode(fix_base64_padding(student_model_data))
        global_model_data = base64.b64decode(fix_base64_padding(global_model_data))

        # Create zip file
        teacher_model_io = BytesIO(teacher_model_data)
        student_model_io = BytesIO(student_model_data)
        global_model_io = BytesIO(global_model_data)
        zip_file = create_zip(student_model_io, teacher_model_io, global_model_io, model.model_name)

        return send_file(
            zip_file,
            as_attachment=True,
            download_name=f"{model.model_name}_model_files.zip",
            mimetype="application/zip"
        )

    except Exception as e:
        logger.exception("Error fetching model files")
        return jsonify({"error": str(e)}), 500

@app.route("/model_status/<model_id>", methods=["GET"])
def get_model_status(model_id: str) -> ResponseReturnValue:
    """Get the status of a model."""
    try:
        model = ModelRegistry.query.filter_by(model_id=model_id).first()
        if not model:
            return jsonify({"error": "Model not found"}), 404
        
        return jsonify({
            "model_name": model.model_name,
            "status": model.status,
            "nft_id": model.nft_id
        })
    except Exception as e:
        logger.error(f"Error fetching model status: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False, host='0.0.0.0', port=5000)
