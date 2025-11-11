# Backup API

This is a REST API for managing database backups. It allows you to register databases, create real backups using `pg_dump` and `mongodump`, schedule them, and enforce retention policies.

**Important:** This application is designed to be run inside the provided Docker container to ensure that `pg_dump` and `mongodump` are available.

The application uses a persistent SQLite database (`backup.db`) to store all configurations and backup history.

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

## Configuration

### Predefined Databases (`config.yaml`)

This project supports loading a predefined list of databases at startup from a `config.yaml` file in the root of the project.

**Important:** Credentials are not stored in this file. Instead, you specify the names of environment variables that hold the credentials.

An example `config.yaml` is provided:
```yaml
databases:
  - name: "my-postgres-db"
    engine: "postgres"
    host: "postgres-db"
    port: 5432
    username_var: "POSTGRES_USER"
    password_var: "POSTGRES_PASSWORD"
    database_name: "testdb"
    schedule: "0 3 * * *"
    retention_days: 7
  - name: "my-mongo-db"
    engine: "mongodb"
    host: "mongo-db"
    port: 27017
    username_var: "MONGO_USER"
    password_var: "MONGO_PASSWORD"
    database_name: "admin"
    schedule: "0 4 * * *"
    retention_days: 14
```

### Credential Management

Database credentials are provided to the application via environment variables, which are defined in the `docker-compose.yml` file. This is a security best practice.

```yaml
# In docker-compose.yml
services:
  backend:
    # ...
    environment:
      - POSTGRES_USER=testuser
      - POSTGRES_PASSWORD=testpassword
      - MONGO_USER=root
      - MONGO_PASSWORD=rootpassword
```

## API Usage Examples

Once the environment is running with the predefined configurations, you can start triggering and managing backups immediately.

### 1. List Preloaded Databases
```bash
curl -X GET "http://localhost:8000/databases"
```

### 2. Trigger a Manual Backup
Get a database ID from the list above and use it to trigger a backup.
```bash
curl -X POST "http://localhost:8000/backups" -H "Content-Type: application/json" -d '{
  "database_id": "your_database_id_here",
  "type": "full"
}'
```

### 3. Check Backup Status
```bash
curl -X GET "http://localhost:8000/backups"
```

### 4. Configure Schedule and Retention
Update the schedule for an existing database.
```bash
curl -X PATCH "http://localhost:8000/databases/your_database_id_here" -H "Content-Type: application/json" -d '{
  "schedule": "0 2 * * *",
  "retention_days": 5
}'
```

## API Endpoints
- `GET /databases`: List all registered databases.
- `POST /databases`: Register a new database.
- `PATCH /databases/{database_id}`: Update the schedule and retention policy for a database.
- `GET /backups`: List all backups.
- `POST /backups`: Create a new backup for a registered database.
- `GET /backups/{backup_id}`: Get the details of a specific backup.

You can find the full API documentation at `http://localhost:8000/docs`.
