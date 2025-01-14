import unittest
import requests
import os

class TestAddModelAPI(unittest.TestCase):
    BASE_URL = "http://localhost:5000/add_model"

    # def test_missing_model_name(self):
    #     """Test if model_name is missing."""
    #     with open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as model_zip, \
    #          open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as tokenizer_zip:
    #         files = {
    #             "model.zip": model_zip,
    #             "tokenizer.zip": tokenizer_zip
    #         }
    #         data = {
    #             "task": "ner"
    #         }
    #         response = requests.post(self.BASE_URL, data=data, files=files)
    #         self.assertEqual(response.status_code, 400)
    #         self.assertIn("Missing required parameters", response.json()["error"])

    # def test_missing_model_zip(self):
    #     """Test if model.zip is missing."""
    #     with open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as tokenizer_zip:
    #         files = {
    #             "tokenizer.zip": tokenizer_zip
    #         }
    #         data = {
    #             "model_name": "my_model_name1",
    #             "task": "ner"
    #         }
    #         response = requests.post(self.BASE_URL, data=data, files=files)
    #         self.assertEqual(response.status_code, 400)
    #         self.assertIn("Missing required parameters", response.json()["error"])

    # def test_invalid_zip_files(self):
    #     """Test with invalid zip files."""
    #     with open("model.zip", "rb") as model_zip, open("tokenizer.zip", "rb") as tokenizer_zip:
    #         files = {
    #             "model.zip": model_zip,
    #             "tokenizer.zip": tokenizer_zip
    #         }
    #         data = {
    #             "model_name": "my_model_name2",
    #             "task": "ner"
    #         }
    #         response = requests.post(self.BASE_URL, data=data, files=files)
    #         self.assertEqual(response.status_code, 400)
    #         self.assertIn("Invalid zip file provided", response.json()["error"])

    # def test_missing_required_files_in_zip(self):
    #     """Test missing required files in the model zip."""
    #     # Simulate a zip file that doesn't contain pytorch_model.bin or config.json
    #     with open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as model_zip, \
    #          open("tokenizer.zip", "rb") as tokenizer_zip:
    #         files = {
    #             "model.zip": model_zip,
    #             "tokenizer.zip": tokenizer_zip
    #         }
    #         data = {
    #             "model_name": "my_model_name3",
    #             "task": "ner"
    #         }
    #         response = requests.post(self.BASE_URL, data=data, files=files)
    #         self.assertEqual(response.status_code, 400)
    #         self.assertIn("Missing required file", response.json()["error"])

    # def test_valid_input(self):
    #     """Test with valid inputs."""
    #     with open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as model_zip, \
    #          open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as tokenizer_zip:
    #         files = {
    #             "model.zip": model_zip,
    #             "tokenizer.zip": tokenizer_zip
    #         }
    #         data = {
    #             "model_name": "my_model_name4",
    #             "task": "ner"
    #         }
    #         response = requests.post(self.BASE_URL, data=data, files=files)
    #         self.assertEqual(response.status_code, 202)
    #         self.assertIn("Voting in progress", response.json()["status"])

    # def test_model_already_exists(self):
    #     """Test when the model already exists."""
    #     with open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as model_zip, \
    #          open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as tokenizer_zip:
    #         files = {
    #             "model.zip": model_zip,
    #             "tokenizer.zip": tokenizer_zip
    #         }
    #         data = {
    #             "model_name": "my_model_name4",
    #             "task": "ner"
    #         }
    #         response = requests.post(self.BASE_URL, data=data, files=files)
    #         self.assertEqual(response.status_code, 409)
    #         self.assertIn("Model with this name already exists", response.json()["error"])

    def test_server_error(self):
        """Test for unexpected server errors."""
        with open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as model_zip, \
             open("/workspaces/IOTA-MODELS/test/ner_model-20250108T072216Z-001.zip", "rb") as tokenizer_zip:
            files = {
                "model.zip": model_zip,
                "tokenizer.zip": tokenizer_zip
            }
            data = {
                "model_name": "server_error_model",
                "task": "ner"
            }
            # Simulate an internal server error (you can mock this in your server code)
            response = requests.post(self.BASE_URL, data=data, files=files)
            self.assertEqual(response.status_code, 500)
            self.assertIn("Unexpected error", response.json()["error"])

if __name__ == '__main__':
    unittest.main()
