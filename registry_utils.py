
def initialize_registry(app):
    """Initialize the database and create the model registry table."""
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///models_registry.db"  # Update for your DB
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()

def update_registry(model_name, nft_id, weights_cid, config_cid):
    """Add or update a model in the registry."""
    try:
        with db.session.begin_nested():  # Use transaction safety
            # Check if the model exists
            model = ModelRegistry.query.filter_by(model_name=model_name).first()
            if model:
                model.nft_id = nft_id
                model.weights_cid = weights_cid
                model.config_cid = config_cid
            else:
                # Add a new record
                new_model = ModelRegistry(
                    model_name=model_name,
                    nft_id=nft_id,
                    weights_cid=weights_cid,
                    config_cid=config_cid
                )
                db.session.add(new_model)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e


