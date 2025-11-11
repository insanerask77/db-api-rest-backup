# Backup API

This is a REST API for managing database backups. It allows you to register databases, create real backups using `pg_dump` and `mongodump`, schedule them, enforce retention policies, and monitor the system via Prometheus metrics.

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
    max_backups: 5
  - name: "my-mongo-db"
    engine: "mongodb"
    host: "mongo-db"
    port: 27017
    username_var: "MONGO_USER"
    password_var: "MONGO_PASSWORD"
    database_name: "admin"
    schedule: "0 4 * * *"
    retention_days: 14
    max_backups: 10
```

### Credential Management

Database credentials are provided to the application via environment variables, which are defined in the `docker-compose.yml` file. This is a security best practice.

### Enhanced Retention Policy

The retention policy now supports two parameters, which are applied in order:
1.  `retention_days`: Deletes all backups older than the specified number of days.
2.  `max_backups`: If, after the first step, the number of backups still exceeds this limit, the oldest remaining backups are deleted until the count is met.

## Monitoring

The application exposes a `/metrics` endpoint with Prometheus metrics for monitoring.

**Key Metrics:**
- `backups_total`: Total number of backups, labeled by database and status (`completed` or `failed`).
- `backup_duration_seconds`: A histogram of backup durations.
- `backup_size_bytes`: The size of the last successful backup for each database.
- `disk_space_available_bytes`: Available disk space in the backup storage directory.

You can access the metrics at `http://localhost:8000/metrics`.

## API Usage Examples

... (API examples remain the same, but now `max_backups` can be included in the `PATCH` request) ...

## API Endpoints
- `GET /databases`: List all registered databases.
- `POST /databases`: Register a new database.
- `PATCH /databases/{database_id}`: Update the schedule and retention policy for a database.
- `GET /backups`: List all backups.
- `POST /backups`: Create a new backup for a registered database.
- `GET /backups/{backup_id}`: Get the details of a specific backup.
- `GET /metrics`: Exposes Prometheus metrics.

You can find the full API documentation at `http://localhost:8000/docs`.
