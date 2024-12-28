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









import asyncio
from datetime import datetime, timedelta

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