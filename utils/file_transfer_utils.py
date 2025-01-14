
import zipfile
from io import BytesIO
import os

# Create a ZIP file in memory
def create_zip(student_model_io: BytesIO, teacher_model_io: BytesIO, global_model_io: BytesIO, model_name: str) -> BytesIO:
    """
    Create a ZIP archive containing both the student and teacher models in memory.
    Returns a BytesIO object containing the zip file.
    """
    zip_io = BytesIO()
    with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(f"{model_name}_student_model.pt", student_model_io.getvalue())
        zipf.writestr(f"{model_name}_teacher_model.pt", teacher_model_io.getvalue())
        zipf.writestr(f"{model_name}_global_model.pt", global_model_io.getvalue())
    zip_io.seek(0)  # Move to the beginning of the in-memory file
    return zip_io

def convert_to_bytes(data: str) -> bytes:
    """
    Convert a string or bytes data to bytes.
    Ensures the data is in byte format.
    """
    if isinstance(data, bytes):
        return data
    elif isinstance(data, str):
        return data.encode("utf-8")
    else:
        raise TypeError("Expected data to be of type str or bytes.")

def cleanup_files(file_paths: list) -> None:
    """
    Helper function to remove temporary files from disk.
    """
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)

# Fix the padding for base64 (if needed)
def fix_base64_padding(base64_str):
    return base64_str + '=' * (4 - len(base64_str) % 4)  # Add padding to base64 string


