# backup_api/error_parser.py

def parse_backup_error(stderr: str, engine: str) -> str:
    """
    Parses the stderr output from a backup command and returns a human-readable summary.
    """
    stderr = stderr.lower()

    if engine == "postgres":
        if "authentication failed" in stderr:
            return "Error de Autenticación: El usuario o la contraseña son incorrectos."
        if "password authentication failed" in stderr:
            return "Error de Autenticación: La contraseña proporcionada fue rechazada."
        if "does not exist" in stderr and "database" in stderr:
            return "Error de Base de Datos: La base de datos especificada no existe."
        if "connection refused" in stderr:
            return "Error de Conexión: No se pudo conectar al servidor de la base de datos. Verifique el host y el puerto."
        if "could not translate host name" in stderr:
            return "Error de Conexión: El nombre del host no se pudo resolver. Verifique la dirección del servidor."
        if "timeout expired" in stderr:
            return "Error de Conexión: Se agotó el tiempo de espera al intentar conectar con el servidor."
        if "permission denied" in stderr:
            return "Error de Permisos: El usuario no tiene los permisos necesarios para realizar el backup."

    elif engine == "mongodb":
        if "authentication failed" in stderr:
            return "Error de Autenticación: El usuario o la contraseña son incorrectos."
        if "could not connect to server" in stderr:
            return "Error de Conexión: No se pudo conectar al servidor. Verifique la dirección y el puerto."
        if "failed to connect" in stderr:
            return "Error de Conexión: Fallo al conectar con el servidor. Verifique la configuración de red."

    return "Error Desconocido: El backup falló por una razón no identificada. Revise el log completo para más detalles."
