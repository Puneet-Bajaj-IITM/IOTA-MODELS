
import zipfile
import io

# Create a ZIP file in memory
def create_zip(weights_io, config_io, model_name):
    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(f"{model_name}_weights.pth", weights_io.getvalue())
        zipf.writestr(f"{model_name}_config.json", config_io.getvalue())
    zip_io.seek(0)  # Rewind the buffer to the beginning
    return zip_io

# Fix the padding for base64 (if needed)
def fix_base64_padding(base64_str):
    return base64_str + '=' * (4 - len(base64_str) % 4)  # Add padding to base64 string


