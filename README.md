# Backup API

Backup API es un servicio RESTful robusto y configurable para gestionar y automatizar backups de bases de datos PostgreSQL y MongoDB. Permite programar tareas, aplicar políticas de retención, empaquetar backups y almacenar los archivos de forma segura en un almacenamiento local o en un bucket S3.

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](/LICENSE)

## ✨ Features

- **Soporte Multi-Base de Datos**: Compatible con **PostgreSQL** y **MongoDB**.
- **Almacenamiento Flexible**: Guarda los backups en el **sistema de archivos local** o en cualquier **almacenamiento compatible con S3** (como Minio o AWS S3).
- **Programación Avanzada**: Define calendarios de backup utilizando la sintaxis de **cron**.
- **Políticas de Retención**: Controla el uso de espacio con políticas duales:
    - **Por Antigüedad**: Elimina backups después de un número determinado de días.
    - **Por Cantidad**: Conserva solo los `N` backups más recientes.
- **Empaquetado de Backups**: Agrupa los backups más recientes de varias bases de datos en un único archivo `.zip` o `.tar.gz` para una fácil portabilidad.
- **Configuración Centralizada**: Gestiona toda la configuración a través de un único archivo `config.yaml`.
- **API RESTful**: Interactúa con el sistema a través de una API bien definida para gestionar bases de datos, backups y paquetes.
- **Monitorización**: Endpoint `/metrics` compatible con **Prometheus** para una observabilidad completa del sistema.
- **Integridad de Datos**: Cada backup se almacena con un **checksum MD5** para verificar su integridad.
- **Contenerizado**: Listo para desplegar con Docker y Docker Compose.

## 🚀 Instalación y Uso

El entorno completo, incluyendo la API y las bases de datos para pruebas, se gestiona a través de Docker Compose.

**Requisitos**:
- Docker
- Docker Compose

**Pasos:**

1.  **Clona el repositorio:**
    ```bash
    git clone <repository-url>
    cd backup-api
    ```

2.  **Inicia los servicios:**
    ```bash
    docker compose up --build
    ```
    Este comando construirá la imagen de la API, levantará los contenedores (API, PostgreSQL, MongoDB y Minio) y los conectará.

3.  **Accede a la API:**
    - **API URL**: `http://localhost:8000`
    - **Documentación Interactiva (Swagger UI)**: `http://localhost:8000/docs`

4.  **Detén los servicios:**
    ```bash
    docker compose down
    ```

## ⚙️ Configuración

Toda la configuración de la aplicación se gestiona a través del archivo `config.yaml`. A continuación se describe la estructura completa.

### Sección `global`

Define valores por defecto que se aplicarán a todas las bases de datos que no tengan una configuración específica.

```yaml
global:
  schedule: "0 2 * * *"       # Cron schedule (ej. todos los días a las 2 AM)
  compression: "gzip"       # "gzip" o "none"
  retention_days: 14        # Días a retener los backups
  max_backups: 10           # Número máximo de backups a retener
  max_parallel_jobs: 10     # Hilos para ejecutar tareas en paralelo
```

### Sección `storage`

Configura dónde se almacenarán los backups.

- **Tipo `local` (por defecto):**
  ```yaml
  storage:
    type: local
  ```
  Los archivos se guardarán en el directorio `data/` dentro del contenedor.

- **Tipo `s3`:**
  ```yaml
  storage:
    type: s3
    s3:
      endpoint_url: "http://minio:9000"
      access_key: "your-access-key"
      secret_key: "your-secret-key"
      bucket: "backups"
  ```

### Sección `databases`

Define la lista de bases de datos a gestionar. Cada base de datos hereda la configuración de `global` a menos que se especifique lo contrario.

```yaml
databases:
  - id: "pg_main_db"
    name: "PostgreSQL Principal"
    engine: "postgres"
    host: "postgres-db"
    port: 5432
    username: "user"
    password: "password"
    database_name: "maindb"
    schedule: "0 3 * * *"       # Sobrescribe el schedule global
    retention_days: 30        # Sobrescribe la retención global
    package: true               # Incluir en los paquetes de backup

  - id: "mongo_logs_db"
    name: "MongoDB de Logs"
    engine: "mongodb"
    host: "mongodb"
    port: 27017
    username: "mongo_user"
    password: "mongo_password"
    database_name: "logs"
    max_backups: 5            # Sobrescribe el máximo de backups
    package: true
```

### Sección `package-conf`

Configura el proceso de empaquetado de backups.

```yaml
package-conf:
  schedule: "0 5 * * *"       # Cron para crear el paquete (ej. 5 AM)
  compression: "zip"          # "zip" o "tar.gz"
  retention_days: 60
  max_packages: 5
```

## 📋 API Endpoints Principales

- `GET /databases`: Lista todas las bases de datos registradas.
- `POST /databases`: Registra una nueva base de datos.
- `PATCH /databases/{database_id}`: Actualiza la configuración de una base de datos.
- `DELETE /databases/{database_id}`: Elimina una base de datos y su programación.
- `GET /backups`: Lista todos los backups realizados.
- `POST /backups`: Lanza un backup bajo demanda para una base de datos.
- `GET /backups/{backup_id}`: Obtiene los detalles de un backup.
- `DELETE /backups/{backup_id}`: Elimina un backup de la base de datos y del almacenamiento.
- `GET /packages`: Lista todos los paquetes creados.
- `POST /packages/create`: Lanza la creación de un paquete bajo demanda.

Para una lista completa de endpoints y sus parámetros, consulta la [documentación interactiva](http://localhost:8000/docs).

## 📊 Monitorización

La aplicación expone métricas en formato Prometheus en el endpoint `/metrics`. Estas métricas incluyen:
- Total de backups y su estado (completado, fallido).
- Duración de los backups.
- Tamaño de los backups.
- Total de archivos eliminados por la política de retención.
- Estado y tamaño de los paquetes.

Puedes integrar este endpoint con tu instancia de Prometheus para crear dashboards y alertas.
