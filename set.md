python 3.10

docker run -p 6379:6379 redis


pip install --upgrade pip

python app.py
celery -A app.celery worker --loglevel=info --pool=eventlet