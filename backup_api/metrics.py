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
