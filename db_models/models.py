
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, UTC

db = SQLAlchemy()

class ModelRegistry(db.Model):
    """Database model for storing registered ML models."""
    __tablename__ = "model_registry"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    model_name = db.Column(db.String(255), unique=True, nullable=False)
    nft_id = db.Column(db.String(255), nullable=False)
    teacher_model_cid = db.Column(db.String(255), nullable=False)
    student_model_cid = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(UTC))
    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected

class ModelVote(db.Model):
    """Track votes for model proposals."""
    __tablename__ = "model_votes"
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(255), nullable=False)
    yes_votes = db.Column(db.Integer, default=0)
    no_votes = db.Column(db.Integer, default=0)
    voting_start = db.Column(db.DateTime, default=datetime.now(UTC))