import os
import base64
import io
import uuid
import asyncio
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

from nio import AsyncClient, RoomMessageText, LoginResponse
import ipfsApi

# Flask App Configuration
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///model_registry.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# IPFS Client
ipfs_client = ipfsApi.Client('179.61.246.8', 5001)

# Matrix Client for Voting
matrix_client = AsyncClient("https://socialxmatch.com", "@bot_user:socialxmatch.com")
VOTING_ROOMS = ["!9E9AMr5kmglYejRW:socialxmatch.com"]
VOTING_DURATION = 300  # 5 minutes

class ModelRegistry(db.Model):
    """Database model for storing registered ML models."""
    __tablename__ = "model_registry"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    model_name = db.Column(db.String(255), unique=True, nullable=False)
    nft_id = db.Column(db.String(255), nullable=False)
    weights_cid = db.Column(db.String(255), nullable=False)
    config_cid = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected


class ModelVote(db.Model):
    """Track votes for model proposals."""
    __tablename__ = "model_votes"
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(255), nullable=False)
    yes_votes = db.Column(db.Integer, default=0)
    no_votes = db.Column(db.Integer, default=0)
    voting_start = db.Column(db.DateTime, default=datetime.utcnow)


def mint_nft_with_ipfs(metadata):
    ...
    return 'nft_id'

import zipfile

# Create a ZIP file in memory
def create_zip(weights_io, config_io, model_name):
    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(f"{model_name}_weights.pth", weights_io.getvalue())
        zipf.writestr(f"{model_name}_config.json", config_io.getvalue())
    zip_io.seek(0)  # Rewind the buffer to the beginning
    return zip_io

import asyncio
from datetime import datetime, timedelta

class ModelVotingManager:
    def __init__(self, matrix_client, db):
        self.matrix_client = matrix_client
        self.db = db
        self.voting_rooms = ["!4JVUuZfXSS0XfgU9:socialxmatch.com"]
        self.voting_duration = 60  # 5 minutes

    async def count_votes_for_model(self, model_name, model_id):
        """
        Count votes for a specific model using Matrix room messages

        Args:
            model_name (str): Name of the model
            model_id (str): Unique identifier for the model proposal

        Returns:
            bool: True if model is approved, False if rejected
        """
        if not matrix_client.logged_in:
            await matrix_client.login("Hosting+123321")
        # Create voting session
        voting_session = ModelVote(
            model_name=model_name,
            yes_votes=0,
            no_votes=0,
            voting_start=datetime.utcnow()
        )
        self.db.session.add(voting_session)
        self.db.session.commit()

        # Broadcast voting proposal
        voting_start_message = await self.broadcast_voting_message({
            'model_name': model_name,
            'model_id': model_id
        })

        # Vote counting loop
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=self.voting_duration)
        import time

        time.sleep(self.voting_duration) 
        
        for room_id in self.voting_rooms:
            try:
                # Retrieve recent room messages
                response = await self.matrix_client.room_messages(
                    room_id, 
                    start=''
                )
                print(response)

                # Process votes in these messages
                for event in response.chunk:
                    # Check if this is a vote for our specific model
                    if self.is_valid_vote(event, model_id):
                        self.process_single_vote(voting_session, event)

            except Exception as e:
                print(f"Error retrieving votes from room {room_id}: {e}")

        # Finalize voting
        return self.finalize_voting(voting_session, model_name)

    def is_valid_vote(self, event, model_id):
        """
        Validate if the message is a valid vote for the model

        Args:
            event (RoomMessageText): Matrix room message event
            model_id (str): Model identifier

        Returns:
            bool: True if valid vote, False otherwise
        """
        # Example vote format: "yes ModelID" or "no ModelID"
        body = event.body.lower().strip()
        return (body.startswith('yes ') or body.startswith('no ')) and \
               body.split()[-1] == model_id

    def process_single_vote(self, voting_session, event):
        """
        Process an individual vote

        Args:
            voting_session (ModelVote): Current voting session
            event (RoomMessageText): Matrix room message event
        """
        body = event.body.lower().strip()

        if body.startswith('yes'):
            voting_session.yes_votes += 1
        elif body.startswith('no'):
            voting_session.no_votes += 1

        self.db.session.commit()

    def finalize_voting(self, voting_session, model_name):
        """
        Finalize voting and process model

        Args:
            voting_session (ModelVote): Voting session details
            model_name (str): Name of the model

        Returns:
            bool: True if model approved, False if rejected
        """
        # Retrieve the model
        model = ModelRegistry.query.filter_by(model_name=model_name).first()

        if not model:
            print(f"Model {model_name} not found")
            return False

        # Determine voting outcome
        is_approved = voting_session.yes_votes > voting_session.no_votes

        if is_approved:
            try:
                # Mint NFT and update model status
                nft_id = mint_nft_with_ipfs(model)
                model.status = 'approved'
                model.nft_id = nft_id
            except Exception as e:
                print(f"Model processing failed: {e}")
                is_approved = False
                model.status = 'rejected'
        else:
            model.status = 'rejected'

        # Clean up voting session
        self.db.session.delete(voting_session)
        self.db.session.commit()

        # Broadcast results
        asyncio.create_task(self.broadcast_approval_result(model_name, is_approved))

        return is_approved

    async def broadcast_voting_message(self, model_data):
        """
        Broadcast model voting message to Matrix rooms

        Args:
            model_data (dict): Model voting details
        """
        voting_message = f"""\
MODEL VOTING PROPOSAL
--------------------
Model Name: {model_data['model_name']}
Model ID: {model_data['model_id']}

VOTING INSTRUCTIONS:
- Reply 'yes {model_data['model_id']}' to approve this model
- Reply 'no {model_data['model_id']}' to reject this model
- Voting closes in 5 minutes
"""
        for room_id in self.voting_rooms:
            try:
                await self.matrix_client.room_send(
                    room_id=room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": voting_message
                    }
                )
            except Exception as e:
                print(f"Failed to broadcast voting message: {e}")

        return voting_message

    async def broadcast_approval_result(self, model_name, approved):
        """
        Broadcast model voting results

        Args:
            model_name (str): Name of the model
            approved (bool): Whether the model was approved
        """
        result_message = f"""\
MODEL VOTING RESULT
------------------
Model: {model_name}
Status: {'APPROVED' if approved else 'REJECTED'}
"""
        for room_id in self.voting_rooms:
            try:
                await self.matrix_client.room_send(
                    room_id=room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": result_message
                    }
                )
            except Exception as e:
                print(f"Failed to broadcast result: {e}")


# Usage in main application
voting_manager = ModelVotingManager(matrix_client, db)


@app.route("/add_model", methods=["POST"])
async def add_model():
    """API endpoint to add a new ML model for community voting."""
    try:
        # Validate input
        model_name = request.form.get("model_name")
        weights_file = request.files.get("weights_file")
        config_file = request.files.get("config_file")

        if not all([model_name, weights_file, config_file]):
            return jsonify({"error": "Missing required parameters"}), 400

        # Save files temporarily
        weights_path = f"/tmp/{weights_file.filename}"
        config_path = f"/tmp/{config_file.filename}"
        weights_file.save(weights_path)
        config_file.save(config_path)

        # Upload to IPFS
        weights_cid = ipfs_client.add(weights_path)[0]['Hash']
        config_cid = ipfs_client.add(config_path)[0]['Hash']

        # Prepare model metadata
        metadata = {
            "model_name": model_name,
            "weights_cid": weights_cid,
            "config_cid": config_cid,
            "timestamp": datetime.now().isoformat()
        }
        model_id = str(uuid.uuid4())

        # Create model registry entry (initially marked as pending)
        new_model = ModelRegistry(
            model_name=model_name,
            nft_id='pending',
            weights_cid=weights_cid,
            config_cid=config_cid,
            status='pending'
        )
        db.session.add(new_model)

        # Create voting record
        vote_record = ModelVote(
            model_name=model_name,
            yes_votes=0,
            no_votes=0
        )
        db.session.add(vote_record)

        # Broadcast for voting
        is_approved = await voting_manager.count_votes_for_model(
            model_name, 
            model_id
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
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

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