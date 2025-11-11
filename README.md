# Backup API

This is a REST API for managing database backups. It allows you to register databases, create simulated backups, and query the status of backups.

## Installation

1. Clone the repository.
2. Install the dependencies:

```bash
pip install -r requirements.txt
```

## Running the application

To run the application, use the following command:

```bash
uvicorn backup_api.main:app --reload
```

The API will be available at `http://localhost:8000`.

## Running with Docker

You can also run the application using Docker.

### Build the Docker image

```bash
docker build -t backup-api .
```

### Run the Docker container

```bash
docker run -p 8000:8000 backup-api
```

The API will be available at `http://localhost:8000`.

## API Endpoints

- `POST /databases`: Register a new database.
- `POST /backups`: Create a new backup for a registered database.
- `GET /backups`: List all backups.
- `GET /backups/{backup_id}`: Get the details of a specific backup.

You can find the full API documentation at `http://localhost:8000/docs`.
