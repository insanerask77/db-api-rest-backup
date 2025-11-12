# Backup API

This is a REST API for managing database backups. It allows you to register databases, create real backups using `pg_dump` and `mongodump`, schedule them, enforce retention policies, and monitor the system via Prometheus metrics.

**Important:** This application is designed to be run inside the provided Docker container to ensure that `pg_dump` and `mongodump` are available.

The application uses a persistent SQLite database (`backup.db`) to store all configurations and backup history.

## Features

- **Database Support:** PostgreSQL and MongoDB.
- **Backup Naming:** Backups are stored with a clear, descriptive name: `engine_dbname_timestamp`.
- **Compression:** Configurable backup compression (`gzip` or `none`).
- **Integrity:** Each backup includes an MD5 checksum to verify its integrity.
- **Scheduling:** Cron-based scheduling for automated backups.
- **Retention Policies:** Dual-criteria retention (by age and by count).
- **Monitoring:** Prometheus endpoint at `/metrics`.

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
    compression: "gzip"
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
    compression: "none"
```

### Credential Management

Database credentials are provided to the application via environment variables, which are defined in the `docker-compose.yml` file.

## Monitoring

The application exposes a `/metrics` endpoint with Prometheus metrics. You can access them at `http://localhost:8000/metrics`.

## API Endpoints
- `GET /databases`: List all registered databases.
- `POST /databases`: Register a new database.
- `PATCH /databases/{database_id}`: Update database settings (schedule, retention, compression).
- `GET /backups`: List all backups.
- `POST /backups`: Create a new on-demand backup.
- `GET /backups/{backup_id}`: Get the details of a specific backup.
- `GET /metrics`: Exposes Prometheus metrics.

You can find the full API documentation at `http://localhost:8000/docs`.
