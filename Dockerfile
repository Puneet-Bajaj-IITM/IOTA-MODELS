# Use the official Python 3.10 image as the base image
FROM python:3.10

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file to the container
COPY requirements.txt /app/

# Install the required dependencies from the requirements.txt file
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the Flask app code into the container
COPY . /app/

# Ensure directories for volumes exist
RUN mkdir -p /app/instance /app/example-walletdb /app/uploaded_model

# Expose port 5000 for the Flask app
EXPOSE 5000

# Command to run the Flask application
CMD ["python", "app.py"]  # Adjust this if your entry point is different
