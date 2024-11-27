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