import yaml
import os
from sqlmodel import Session, select
from .models import Database
import logging

logger = logging.getLogger(__name__)


def load_config():
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing config.yaml: {e}")
            return {}


def load_and_sync_databases(session: Session):
    config_data = load_config()
    if not config_data:
        logger.info("No config.yaml found or it's empty, skipping predefined databases.")
        return

    try:
        global_config = config_data.get("global", {})
        db_configs = config_data.get("databases", [])

        if not db_configs:
            return

        # Pre-validate for duplicate IDs
        config_ids = [conf.get('id') for conf in db_configs if conf.get('id')]
        if len(config_ids) > len(set(config_ids)):
            seen = set()
            duplicates = {x for x in config_ids if x in seen or seen.add(x)}
            error_msg = f"Duplicate IDs found in config.yaml: {list(duplicates)}. Halting sync process."
            logger.error(error_msg)
            raise ValueError(error_msg)

        db_defaults = {
            "schedule", "compression", "retention_days", "max_backups"
        }

        for config in db_configs:
            # Apply global defaults
            for key, value in global_config.items():
                if key in db_defaults and key not in config:
                    config[key] = value

            config_id = config.get('id')
            if not config_id:
                db_name_for_log = config.get('name', 'N/A')
                logger.warning(
                    f"Skipping a database configuration (name: {db_name_for_log}) "
                    f"because it is missing the required 'id' field."
                )
                continue

            # Load credentials from environment variables or directly from config
            username_var = config.pop("username_var", None)
            password_var = config.pop("password_var", None)

            if "username" not in config and username_var:
                config["username"] = os.getenv(username_var)
            if "password" not in config and password_var:
                config["password"] = os.getenv(password_var)

            if not config.get("username") or not config.get("password"):
                logger.warning(f"Skipping database with id '{config_id}' due to missing credentials.")
                continue

            existing_db = session.exec(select(Database).where(Database.config_id == config_id)).first()

            config.pop('id')

            if existing_db:
                if existing_db.override_static_config:
                    logger.info(
                        f"Skipping update for config_id='{config_id}' because it is managed by the API."
                    )
                    continue

                if existing_db.is_deleted:
                    logger.info(
                        f"Skipping update for config_id='{config_id}' because it has been deleted via the API."
                    )
                    continue

                logger.info(f"Updating database configuration for config_id='{config_id}'.")
                for key, value in config.items():
                    setattr(existing_db, key, value)
                session.add(existing_db)
            else:
                logger.info(f"Creating new database configuration for config_id='{config_id}'.")
                db = Database(config_id=config_id, **config)
                session.add(db)

        session.commit()
        logger.info("Successfully synced databases from config.yaml.")

    except yaml.YAMLError as e:
        logger.error(f"Error parsing config.yaml: {e}")
        raise
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during database sync: {e}")
        session.rollback()
        raise


def overwrite_static_config(yaml_content: str, session: Session):
    try:
        config_data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing uploaded YAML content: {e}")
        raise

    if not config_data:
        logger.info("Uploaded YAML is empty, clearing all static configurations.")
        config_data = {}

    # Delete all existing databases that were loaded from a static config
    logger.info("Deleting all existing static database configurations.")
    static_dbs = session.exec(select(Database).where(Database.config_id != None)).all()
    for db in static_dbs:
        session.delete(db)
    session.flush()

    # Logic adapted from load_and_sync_databases
    try:
        global_config = config_data.get("global", {})
        db_configs = config_data.get("databases", [])

        if not db_configs:
            logger.info("No databases found in the uploaded YAML. Static configurations have been cleared.")
            session.commit()
            return

        config_ids = [conf.get('id') for conf in db_configs if conf.get('id')]
        if len(config_ids) > len(set(config_ids)):
            seen = set()
            duplicates = {x for x in config_ids if x in seen or seen.add(x)}
            error_msg = f"Duplicate IDs found in uploaded YAML: {list(duplicates)}. Halting process."
            logger.error(error_msg)
            raise ValueError(error_msg)

        db_defaults = {
            "schedule", "compression", "retention_days", "max_backups"
        }

        for config in db_configs:
            for key, value in global_config.items():
                if key in db_defaults and key not in config:
                    config[key] = value

            config_id = config.get('id')
            if not config_id:
                db_name_for_log = config.get('name', 'N/A')
                logger.warning(
                    f"Skipping a database configuration (name: {db_name_for_log}) "
                    f"in uploaded YAML because it is missing the required 'id' field."
                )
                continue

            username_var = config.pop("username_var", None)
            password_var = config.pop("password_var", None)

            if "username" not in config and username_var:
                config["username"] = os.getenv(username_var)
            if "password" not in config and password_var:
                config["password"] = os.getenv(password_var)

            if not config.get("username") or not config.get("password"):
                logger.warning(f"Skipping database with id '{config_id}' from uploaded YAML due to missing credentials.")
                continue

            config.pop('id', None)
            logger.info(f"Creating new database configuration from uploaded YAML for config_id='{config_id}'.")
            db = Database(config_id=config_id, **config)
            session.add(db)

        session.commit()
        logger.info("Successfully overwrote static configurations from uploaded YAML.")

    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        session.rollback()
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during config overwrite: {e}")
        session.rollback()
        raise
