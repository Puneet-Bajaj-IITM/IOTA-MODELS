import os
import zipfile
from transformers import AutoModel, AutoTokenizer

# Define model name (use a smaller model to keep the size under 100MB)
model_name = "distilbert-base-uncased"  # Example smaller model

# Define the directory to save the model
save_dir = "/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001"

# Create directory if it doesn't exist
os.makedirs(save_dir, exist_ok=True)

# Download and save the model and tokenizer
model = AutoModel.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

# Save the model and tokenizer locally
model.save_pretrained(save_dir)
tokenizer.save_pretrained(save_dir)

# Now zip the saved model and tokenizer
zip_file = f"/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip"
with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
    # Walk through the saved directory and add all files to the zip
    for folder_name, subfolders, filenames in os.walk(save_dir):
        for filename in filenames:
            file_path = os.path.join(folder_name, filename)
            zipf.write(file_path, os.path.relpath(file_path, save_dir))

print(f"Model saved and zipped as {zip_file}")
