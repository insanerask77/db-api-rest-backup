from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from backup_api.database import engine
from backup_api.models import Package, PackageConfig
from backup_api.schemas import PackageList, PackageDetail, PackageConfigUpdate
from backup_api.metrics import PACKAGES_TOTAL, PACKAGES_SIZE_BYTES
from backup_api.packager import create_package
from backup_api.scheduler import schedule_package_creation
from backup_api.storage import StorageProvider, get_storage_provider
from backup_api.logger import get_logger
from backup_api.dependencies import get_settings


router = APIRouter()
logger = get_logger(__name__)


def get_session():
    with Session(engine) as session:
        yield session


@router.get("/", response_model=List[PackageList])
def list_packages(session: Session = Depends(get_session)):
    """List all backup packages."""
    logger.info("Listing all packages.")
    packages = session.exec(select(Package)).all()
    logger.debug(f"Found {len(packages)} packages.")
    return packages


@router.get("/{package_id}", response_model=PackageDetail)
def get_package_details(package_id: str, session: Session = Depends(get_session)):
    """Get details of a specific backup package."""
    logger.info(f"Getting details for package_id: {package_id}")
    pkg = session.get(Package, package_id)

    if not pkg:
        logger.warning(f"Package with id {package_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    return pkg


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(
    package_id: str,
    session: Session = Depends(get_session),
    storage: StorageProvider = Depends(get_storage_provider),
):
    """Delete a specific backup package."""
    logger.info(f"Request to delete package_id: {package_id}")
    pkg = session.get(Package, package_id)
    if pkg:
        size_bytes = pkg.size_bytes
        if not storage.delete(pkg.storage_path):
            logger.error(f"Failed to delete package file from storage: {pkg.storage_path}")
            raise HTTPException(status_code=502, detail="Failed to delete package from storage")

        session.delete(pkg)
        session.commit()
        logger.info(f"Successfully deleted package_id: {package_id}")
        PACKAGES_TOTAL.dec()
        PACKAGES_SIZE_BYTES.dec(size_bytes)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_packages(
    session: Session = Depends(get_session),
    storage: StorageProvider = Depends(get_storage_provider),
):
    """Delete all backup packages."""
    logger.info("Request to delete all packages.")
    packages = session.exec(select(Package)).all()
    logger.debug(f"Found {len(packages)} packages to delete.")
    total_size = 0
    count = 0
    for pkg in packages:
        if not storage.delete(pkg.storage_path):
            logger.error(f"Failed to delete package file from storage: {pkg.storage_path}")
            session.rollback()
            raise HTTPException(status_code=502, detail=f"Failed to delete package {pkg.storage_path} from storage")

        total_size += pkg.size_bytes
        count += 1
        session.delete(pkg)
    session.commit()
    logger.info(f"Successfully deleted {count} packages.")
    PACKAGES_TOTAL.dec(count)
    PACKAGES_SIZE_BYTES.dec(total_size)


@router.get("/{package_id}/download")
def download_package(
    package_id: str,
    session: Session = Depends(get_session),
    storage: StorageProvider = Depends(get_storage_provider),
):
    """Download a specific backup package."""
    logger.info(f"Request to download package_id: {package_id}")
    pkg = session.get(Package, package_id)
    if not pkg:
        logger.warning(f"Package with id {package_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")

    if not pkg.storage_path:
        logger.error(f"Package {package_id} has no storage_path.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package has no file associated")

    logger.debug(f"Serving download for package file: {pkg.storage_path}")
    return storage.get_download_response(pkg.storage_path)


@router.get("/configuration/", response_model=dict)
def get_package_configuration(settings: dict = Depends(get_settings)):
    """Get the current package configuration."""
    logger.info("Getting package configuration.")
    return settings.get("package-conf", {})


@router.put("/configuration/", response_model=dict)
def update_package_configuration(
    config_update: PackageConfigUpdate,
    session: Session = Depends(get_session),
    settings: dict = Depends(get_settings),
):
    """Update the package configuration."""
    logger.info("Updating package configuration.")

    package_config_db = session.get(PackageConfig, 1)
    if not package_config_db:
        package_config_db = PackageConfig(id=1)

    update_data = config_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(package_config_db, key, value)

    package_config_db.override_static_config = True
    session.add(package_config_db)
    session.commit()
    session.refresh(package_config_db)

    # Update in-memory settings
    package_conf = settings.setdefault("package-conf", {})
    package_conf["schedule"] = package_config_db.schedule
    package_conf["compression"] = package_config_db.compression
    package_conf["retention_days"] = package_config_db.retention_days

    # Reload schedule if it was changed
    if "schedule" in update_data:
        logger.info("Reloading package schedule due to configuration change.")
        schedule_package_creation(package_conf)

    return package_conf


@router.post("/reload/", status_code=status.HTTP_204_NO_CONTENT)
def reload_package_schedule(settings: dict = Depends(get_settings)):
    """Reload the package creation schedule from the current configuration."""
    logger.info("Reloading package schedule.")
    package_conf = settings.get("package-conf", {})
    if package_conf.get("schedule"):
        schedule_package_creation(package_conf)
        logger.info("Package schedule reloaded.")
    else:
        logger.info("No package schedule found in configuration, skipping reload.")


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def trigger_package_creation(
    compression: str = None,
    session: Session = Depends(get_session),
    settings: dict = Depends(get_settings),
):
    """Manually trigger the creation of a backup package."""
    logger.info("Manual package creation triggered.")
    try:
        package_conf = settings.get("package-conf", {})

        comp_to_use = compression or package_conf.get("compression", "zip")
        logger.debug(f"Using compression: {comp_to_use}")

        create_package(session, comp_to_use, trigger_mode="manual")
        return {"message": "Package creation triggered."}
    except Exception as e:
        logger.error(f"Failed to trigger package creation: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
