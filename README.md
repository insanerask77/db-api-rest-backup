# Backup API

This is a REST API for managing database backups. It allows you to register databases, create real backups using `pg_dump` and `mongodump`, and query the status of backups.

**Important:** This application is designed to be run inside the provided Docker container to ensure that `pg_dump` and `mongodump` are available.

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

## Running the Full Environment with Docker Compose

To test the complete solution, you can use Docker Compose to launch the backend API along with a PostgreSQL and a MongoDB database instance.

**1. Start the services:**
```bash
docker-compose up --build
```
This command will build the backend image, pull the database images, and start all three containers. The API will be available at `http://localhost:8000`.

**2. Stop the services:**
To stop and remove the containers, run:
```bash
docker-compose down
```

## API Usage Examples

Once the environment is running, you can use the following `curl` commands to interact with the API.

### 1. Register Databases

**Register the PostgreSQL test database:**
```bash
curl -X POST "http://localhost:8000/databases" -H "Content-Type: application/json" -d '{
  "name": "my-postgres-db",
  "engine": "postgres",
  "host": "postgres-db",
  "port": 5432,
  "username": "testuser",
  "password": "testpassword",
  "database_name": "testdb"
}'
```
*You will get a response with a database ID, for example: `{"id":"db_xxxxxxxx","name":"my-postgres-db"}`. Copy this ID for the next steps.*

**Register the MongoDB test database:**
```bash
curl -X POST "http://localhost:8000/databases" -H "Content-Type: application/json" -d '{
  "name": "my-mongo-db",
  "engine": "mongodb",
  "host": "mongo-db",
  "port": 27017,
  "username": "root",
  "password": "rootpassword",
  "database_name": "testdb"
}'
```
*You will get a response with a database ID, for example: `{"id":"db_yyyyyyyy","name":"my-mongo-db"}`. Copy this ID.*

### 2. Trigger Backups

**Execute a backup for the PostgreSQL database (replace `db_xxxxxxxx` with your ID):**
```bash
curl -X POST "http://localhost:8000/backups" -H "Content-Type: application/json" -d '{
  "database_id": "db_xxxxxxxx",
  "type": "full"
}'
```
*You will get a response with a backup ID, for example: `{"backup_id":"bkp_zzzzzzzz","status":"running"}`.*

**Execute a backup for the MongoDB database (replace `db_yyyyyyyy` with your ID):**
```bash
curl -X POST "http://localhost:8000/backups" -H "Content-Type: application/json" -d '{
  "database_id": "db_yyyyyyyy",
  "type": "full"
}'
```

### 3. Check Backup Status

**List all backups:**
```bash
curl -X GET "http://localhost:8000/backups"
```

**Get details of a specific backup (replace `bkp_zzzzzzzz` with a real backup ID):**
```bash
curl -X GET "http://localhost:8000/backups/bkp_zzzzzzzz"
```
*After a few seconds, the status should change from `running` to `completed`, and you will see the path to the backup file in the `storage` directory.*

### 4. Configure Schedule and Retention

You can configure a backup schedule and retention policy for any registered database.

**Set a daily backup schedule and a 7-day retention for the PostgreSQL database (replace `db_xxxxxxxx` with your ID):**
```bash
curl -X PATCH "http://localhost:8000/databases/db_xxxxxxxx" -H "Content-Type: application/json" -d '{
  "schedule": "0 2 * * *",
  "retention_days": 7
}'
```
*This configures the backup to run every day at 2:00 AM. The retention policy will automatically delete backups older than 7 days.*

**To remove a schedule, set it to `null`:**
```bash
curl -X PATCH "http://localhost:8000/databases/db_xxxxxxxx" -H "Content-Type: application/json" -d '{
  "schedule": null
}'
```

## API Endpoints

- `POST /databases`: Register a new database.
- `PATCH /databases/{database_id}`: Update the schedule and retention policy for a database.
- `POST /backups`: Create a new backup for a registered database.
- `GET /backups`: List all backups.
- `GET /backups/{backup_id}`: Get the details of a specific backup.

You can find the full API documentation at `http://localhost:8000/docs`.
