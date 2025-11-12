from prometheus_client import Counter, Histogram, Gauge

BACKUPS_TOTAL = Counter(
    "backups_total",
    "Total number of backups.",
    ["database_name", "status"]
)

BACKUP_DURATION_SECONDS = Histogram(
    "backup_duration_seconds",
    "Duration of backup operations in seconds.",
    ["database_name"]
)

BACKUP_SIZE_BYTES = Gauge(
    "backup_size_bytes",
    "Size of the last successful backup in bytes.",
    ["database_name"]
)

DISK_SPACE_AVAILABLE_BYTES = Gauge(
    "disk_space_available_bytes",
    "Available disk space for backups in bytes."
)

BACKUPS_DELETED_TOTAL = Counter(
    "backups_deleted_total",
    "Total number of backups deleted.",
    ["database_name"]
)

RETENTION_POLICY_RUNS_TOTAL = Counter(
    "retention_policy_runs_total",
    "Total number of retention policy runs.",
    ["database_name"]
)

RETENTION_FILES_DELETED_TOTAL = Counter(
    "retention_files_deleted_total",
    "Total number of files deleted by retention policy.",
    ["database_name"]
)

BACKUP_LAST_STATUS = Gauge(
    "backup_last_status",
    "Status of the last backup (1 for success, 0 for failure).",
    ["database_name"]
)

BACKUP_LAST_SUCCESSFUL_SCHEDULED_TIMESTAMP_SECONDS = Gauge(
    "backup_last_successful_scheduled_timestamp_seconds",
    "Timestamp of the last successful scheduled backup.",
    ["database_name"]
)

BACKUP_TRANSFER_SPEED_BYTES_PER_SECOND = Gauge(
    "backup_transfer_speed_bytes_per_second",
    "Transfer speed of the last backup in bytes per second.",
    ["database_name"]
)
