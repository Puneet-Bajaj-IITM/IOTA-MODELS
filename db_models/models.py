
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, UTC
import json

db = SQLAlchemy()

class ModelRegistry(db.Model):
    """Database model for storing registered ML models."""
    __tablename__ = "model_registry"
    model_id = db.Column(db.String(255), primary_key=True)
    model_name = db.Column(db.String(255), unique=False, nullable=False)
    nft_id = db.Column(db.String(255), nullable=False)
    teacher_model_cid = db.Column(db.String(255))
    student_model_cid = db.Column(db.String(255))
    global_model_cid = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.now(UTC))
    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected

    def to_dict(self):
        """Converts the ModelRegistry instance to a dictionary for JSON serialization."""
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "nft_id": self.nft_id,
            "teacher_model_cid": self.teacher_model_cid,
            "student_model_cid": self.student_model_cid,
            "global_model_cid": self.global_model_cid,
            "created_at": self.created_at.isoformat(),  # Convert datetime to ISO format string
            "status": self.status
        }

    def to_json(self):
        """Converts the ModelRegistry instance to JSON."""
        return json.dumps(self.to_dict())

class ModelVote(db.Model):
    """Track votes for model proposals."""
    __tablename__ = "model_votes"
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(255), nullable=False)
    yes_votes = db.Column(db.Integer, default=0)
    no_votes = db.Column(db.Integer, default=0)
    voting_start = db.Column(db.DateTime, default=datetime.now(UTC))