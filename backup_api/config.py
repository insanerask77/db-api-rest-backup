import yaml
import os
from sqlmodel import Session, select
from .models import Database
import logging

logger = logging.getLogger(__name__)

def load_and_sync_databases(session: Session):
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        logger.info("No config.yaml found, skipping predefined databases.")
        return

    with open(config_path, "r") as f:
        try:
            config_data = yaml.safe_load(f)
            db_configs = config_data.get("databases", [])

            for config in db_configs:
                # Load credentials from environment variables or directly from config
                username_var = config.pop("username_var", None)
                password_var = config.pop("password_var", None)

                if "username" not in config and username_var:
                    config["username"] = os.getenv(username_var)
                if "password" not in config and password_var:
                    config["password"] = os.getenv(password_var)

                # Check if all required credentials are provided
                if not config.get("username") or not config.get("password"):
                    logger.warning(f"Skipping database '{config['name']}' due to missing credentials.")
                    continue

                existing_db = session.exec(select(Database).where(Database.name == config["name"])).first()
                if not existing_db:
                    db = Database(**config)
                    session.add(db)

            session.commit()
            logger.info(f"Successfully loaded and synced databases from config.")

        except yaml.YAMLError as e:
            logger.error(f"Error parsing config.yaml: {e}")
