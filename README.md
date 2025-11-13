# Backup API

Backup API es una solución integral para la gestión de copias de seguridad de bases de datos PostgreSQL y MongoDB. Esta API RESTful, diseñada para ser ejecutada en un entorno Docker, permite registrar bases de datos, programar backups automáticos, aplicar políticas de retención y monitorizar el sistema de forma centralizada.

## Características Principales

- **Soporte Multi-DB**: Compatible con **PostgreSQL** y **MongoDB**.
- **Configuración Dinámica**: Registra y modifica parámetros de bases de datos en caliente a través de la API, sin necesidad de reinicios.
- **Programación Flexible**: Define horarios de backup para cada base de datos usando sintaxis **cron**.
- **Políticas de Retención**: Controla el número de backups por edad (días) y cantidad, optimizando el uso del almacenamiento.
- **Compresión**: Reduce el tamaño de los backups con compresión `gzip`.
- **Checksum de Integridad**: Cada backup incluye un checksum **MD5** para verificar su integridad.
- **Empaquetado de Backups**: Agrupa los últimos backups de múltiples bases de datos en un único paquete (`.zip` o `.tar.gz`) para facilitar la descarga y migración.
- **Monitorización Avanzada**: Expone métricas detalladas en formato **Prometheus** y proporciona un **dashboard de Grafana** preconfigurado para una visualización completa.

## Despliegue y Configuración

### Prerrequisitos

- **Docker** y **Docker Compose** instalados en el sistema anfitrión.

### 1. Iniciar el Entorno

El proyecto se distribuye con un fichero `docker-compose.yml` que orquesta todos los servicios necesarios:

- `backend`: La aplicación principal de la API.
- `postgres-db`: Una instancia de PostgreSQL para pruebas.
- `mongo-db`: Una instancia de MongoDB para pruebas.

Para levantar todo el entorno, ejecuta:

```bash
docker compose up --build
```

La API estará disponible en `http://localhost:8000`.

### 2. Configurar Bases de Datos (`config.yaml`)

La aplicación utiliza un fichero `config.yaml` para registrar bases de datos de forma masiva durante el arranque. Este fichero es ideal para entornos de despliegue automatizado.

**Estructura del `config.yaml`:**

```yaml
global:
  # Valores por defecto para todas las bases de datos
  schedule: "0 2 * * *"       # Cron para backups diarios a las 2 AM
  compression: "gzip"
  retention_days: 15
  max_backups: 10
  max_parallel_jobs: 4      # Número máximo de backups simultáneos

package-conf:
  # Configuración para el empaquetado de backups
  schedule: "0 5 * * 1"       # Empaquetar cada lunes a las 5 AM
  compression: "zip"          # Formato del paquete (zip o tar.gz)
  retention_days: 30
  max_backups: 4

databases:
  - id: "pg_ventas_prod"
    name: "PostgreSQL Ventas"
    engine: "postgres"
    host: "postgres-db"
    port: 5432
    username_var: "POSTGRES_USER"
    password_var: "POSTGRES_PASSWORD"
    database_name: "ventasdb"
    schedule: "0 3 * * *"       # Sobrescribe el schedule global
    package: true               # Incluir en los paquetes de backup

  - id: "mongo_logs_dev"
    name: "MongoDB Logs"
    engine: "mongodb"
    host: "mongo-db"
    port: 27017
    database_name: "logsdb"
    # Hereda el resto de la configuración de 'global'
```

- **`global`**: Define valores por defecto. Cualquier base de datos en la sección `databases` que no especifique un parámetro (como `schedule` o `retention_days`) usará el valor definido aquí.
- **`package-conf`**: Configura el comportamiento del empaquetado de backups.
- **`databases`**: Es una lista de las bases de datos a registrar. El campo `id` es un identificador único que no debe repetirse.

### 3. Gestión de Credenciales

Las credenciales **no se guardan** en `config.yaml`. En su lugar, se leen desde variables de entorno. Los campos `username_var` y `password_var` en `config.yaml` especifican el **nombre** de las variables de entorno que contienen el usuario y la contraseña.

Estas variables se inyectan en el contenedor `backend` a través del `docker-compose.yml`:

```yaml
# En docker-compose.yml
services:
  backend:
    environment:
      - POSTGRES_USER=admin
      - POSTGRES_PASSWORD=secret
```

### 4. Configuración de Zona Horaria

Por defecto, el planificador de tareas (APScheduler) utiliza la zona horaria UTC. Para ajustarla, modifica la variable de entorno `TZ` en `docker-compose.yml`:

```yaml
# En docker-compose.yml
services:
  backend:
    environment:
      - TZ=Europe/Madrid
```

## Guía de Uso

### Restauración de Backups (Manual)

La API actualmente no incluye un endpoint para restaurar backups. La restauración debe realizarse manualmente utilizando las herramientas nativas de cada motor de base de datos.

**1. Identificar el Backup:**

Primero, obtén el nombre del fichero de backup que deseas restaurar. Puedes listarlos usando la API o inspeccionando el volumen de Docker donde se almacenan (`data/backups`).

**2. Copiar el Backup:**

Copia el fichero desde el contenedor `backend` a tu máquina local o a un lugar accesible por la base de datos.

```bash
docker cp <backend_container_id>:/app/data/backups/<nombre_del_backup> .
```

**3. Restaurar según el motor:**

#### PostgreSQL

Si el backup es un fichero `.sql.gz`, primero descomprímelo. Si es un formato custom (`.dump`), usa `pg_restore`.

```bash
# Para ficheros .sql
psql -h <db_host> -U <user> -d <database_name> < backup_file.sql

# Para ficheros .dump (formato custom)
pg_restore -h <db_host> -U <user> -d <database_name> --verbose < backup_file.dump
```

#### MongoDB

Usa `mongorestore`, apuntando al directorio que contiene el dump.

```bash
# Descomprime el backup si es necesario
mongorestore --host <db_host> --port <db_port> --db <database_name> <ruta_al_directorio_del_dump>
```

### Gestión de Paquetes de Backups

La funcionalidad de "empaquetado" crea un archivo unificado (`.zip` o `.tar.gz`) que contiene los backups más recientes de todas las bases de datos que tengan la opción `package: true` en `config.yaml`.

- **Programación**: Se define en la sección `package-conf` del `config.yaml`.
- **Gestión**: Puedes listar, descargar y eliminar paquetes a través de los endpoints de la API en `/packages`.

## Referencia de la API

La documentación completa de la API, generada con Swagger UI, está disponible en:

- **`http://localhost:8000/docs`**

A continuación, se muestran ejemplos para los endpoints más comunes.

---

### **`POST /databases`**

Registra una nueva base de datos.

**Ejemplo de Request:**

```json
{
  "name": "PostgreSQL Producción",
  "engine": "postgres",
  "host": "db.example.com",
  "port": 5432,
  "database_name": "production_db",
  "schedule": "0 4 * * *",
  "retention_days": 30,
  "max_backups": 15,
  "compression": "gzip",
  "credentials": {
    "username": "prod_user",
    "password": "very_strong_password"
  }
}
```

**Ejemplo de Response:**

```json
{
  "id": 1,
  "config_id": null,
  "name": "PostgreSQL Producción",
  "engine": "postgres",
  "host": "db.example.com",
  "port": 5432,
  "database_name": "production_db",
  "schedule": "0 4 * * *",
  "retention_days": 30,
  "max_backups": 15,
  "compression": "gzip"
}
```

---

### **`GET /databases`**

Lista todas las bases de datos registradas.

**Ejemplo de Response:**

```json
[
  {
    "id": 1,
    "name": "PostgreSQL Producción",
    // ... otros campos
  },
  {
    "id": 2,
    "name": "MongoDB Staging",
    // ... otros campos
  }
]
```

---

### **`PATCH /databases/{database_id}`**

Actualiza los parámetros de una base de datos existente. Solo necesitas enviar los campos que deseas cambiar.

**Ejemplo de Request (para cambiar el schedule):**

```json
{
  "schedule": "0 1 * * 1-5"
}
```

## Monitorización

### Métricas de Prometheus

La aplicación expone un endpoint `/metrics` con métricas listas para ser recolectadas por un servidor Prometheus.

- **URL de Métricas**: `http://localhost:8000/metrics`

Algunas de las métricas expuestas son:
- `backup_total`: Número total de backups realizados.
- `backup_duration_seconds`: Duración de cada backup.
- `backup_bytes`: Tamaño de cada backup.
- `backup_package_total`: Número total de paquetes creados.
- `available_disk_space_bytes`: Espacio libre en disco.

### Dashboard de Grafana

El repositorio incluye un fichero `grafana-dashboard.json` con un dashboard preconfigurado para visualizar las métricas de la API.

**Cómo importar el dashboard:**

1.  Abre tu instancia de Grafana.
2.  Navega a **Dashboards** -> **Import**.
3.  Haz clic en **Upload JSON file** y selecciona el fichero `grafana-dashboard.json` del repositorio.
4.  Elige el *data source* de Prometheus correcto.
5.  Haz clic en **Import**.
