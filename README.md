

## Features

1. **Add a Model**: Upload a Hugging Face model and tokenizer as zip files, and initialize a voting process for approval.
2. **Fetch Approved Models**: Retrieve approved models and download their files.
3. **Check Model Status**: Query the current status of a model by its ID.
4. **Get List of Approved Model**: Query the list of approved models

---

## API Endpoints

### 1. Add a Model

#### Endpoint:
`POST /add_model`

#### Description:
Uploads a Hugging Face model and tokenizer, starts a voting process, and registers the model in the database.

#### Parameters:
- `model_name` (form-data): Name of the model.
- `task` (form-data): Task type (e.g., "ner", "classification").
- `tokenizer.zip` (file): Zip file containing the tokenizer files.
- `model.zip` (file): Zip file containing the model files.

#### Example Request:
```bash
curl -X POST http://<SERVER_IP>:5000/add_model \
  -F "model_name=my_model" \
  -F "task=ner" \
  -F "model.zip=@path_to_model.zip" \
  -F "tokenizer.zip=@path_to_tokenizer.zip"
```
### Add Model Programmatically

```python
import requests

def upload_model(server_url, model_name, task, model_path, tokenizer_path):
    files = {
        "model.zip": open(model_path, "rb"),
        "tokenizer.zip": open(tokenizer_path, "rb")
    }
    data = {"model_name": model_name, "task": task}
    response = requests.post(f"{server_url}/add_model", data=data, files=files)
    print(response.json())
```

---

### 2. Fetch Approved Models

#### Endpoint:
`GET /approved-models`

#### Description:
Fetches all approved models list with their metadata.

#### Example Request:
```bash
curl -X GET http://<SERVER_IP>:5000/approved-models
```


---

### 3. Fetch Model Files

#### Endpoint:
`GET /fetch_model`

#### Description:
Retrieves files for an approved model.

#### Query Parameters:
- `model_name`: Name of the model.
- `nft_id`: NFT ID associated with the model.

#### Example Request:
```bash
curl -X GET http://<SERVER_IP>:5000/fetch_model?model_name=my_model
```
### Retrieve Model Files

```python
import requests

def fetch_model(server_url, model_name):
    response = requests.get(f"{server_url}/fetch_model", params={"model_name": model_name})
    with open(f"{model_name}_files.zip", "wb") as f:
        f.write(response.content)
    print(f"Model files saved as {model_name}_files.zip")
```

---

### 4. Check Model Status

#### Endpoint:
`GET /model_status/<model_id>`

#### Description:
Fetches the status of a model by its unique ID.

#### Example Request:
```bash
curl -X GET http://<SERVER_IP>:5000/model_status/<model_id>
```

