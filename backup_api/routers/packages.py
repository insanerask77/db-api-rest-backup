from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from backup_api.database import engine
from backup_api.models import Package
from backup_api.schemas import PackageList, PackageDetail
from backup_api.metrics import PACKAGES_TOTAL, PACKAGES_SIZE_BYTES
from backup_api.packager import create_package
from backup_api.scheduler import schedule_package_creation
import yaml
import os
from ..storage import get_storage_provider
from ..config import load_config

router = APIRouter()
config = load_config()
storage = get_storage_provider(config)

def get_session():
    with Session(engine) as session:
        yield session

@router.get("/", response_model=List[PackageList])
def list_packages(session: Session = Depends(get_session)):
    """List all backup packages."""
    return session.exec(select(Package)).all()

@router.get("/{package_id}", response_model=PackageDetail)
def get_package_details(package_id: str, session: Session = Depends(get_session)):
    """Get details of a specific backup package."""
    pkg = session.get(Package, package_id)

    if not pkg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    return pkg

@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(package_id: str, session: Session = Depends(get_session)):
    """Delete a specific backup package."""
    pkg = session.get(Package, package_id)
    if pkg:
        size_bytes = pkg.size_bytes
        if not storage.delete(pkg.storage_path):
            raise HTTPException(status_code=502, detail="Failed to delete package from storage")

        session.delete(pkg)
        session.commit()
        PACKAGES_TOTAL.dec()
        PACKAGES_SIZE_BYTES.dec(size_bytes)

@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_packages(session: Session = Depends(get_session)):
    """Delete all backup packages."""
    packages = session.exec(select(Package)).all()
    total_size = 0
    count = 0
    for pkg in packages:
        if not storage.delete(pkg.storage_path):
            session.rollback()
            raise HTTPException(status_code=502, detail=f"Failed to delete package {pkg.storage_path} from storage")

        total_size += pkg.size_bytes
        count += 1
        session.delete(pkg)
    session.commit()
    PACKAGES_TOTAL.dec(count)
    PACKAGES_SIZE_BYTES.dec(total_size)


@router.get("/{package_id}/download")
def download_package(package_id: str, session: Session = Depends(get_session)):
    """Download a specific backup package."""
    pkg = session.get(Package, package_id)
    if not pkg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")

    if not pkg.storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package has no file associated")

    return storage.get_download_response(pkg.storage_path)

@router.get("/configuration/", response_model=dict)
def get_package_configuration():
    """Get the current package configuration from config.yaml."""
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f).get("package-conf", {})
    except FileNotFoundError:
        return {}

@router.post("/reload/", status_code=status.HTTP_204_NO_CONTENT)
def reload_package_schedule():
    """Reload the package creation schedule from config.yaml."""
    try:
        with open("config.yaml", "r") as f:
            config_data = yaml.safe_load(f)
            package_conf = config_data.get("package-conf", {})
            if package_conf.get("schedule"):
                schedule_package_creation(package_conf)
    except FileNotFoundError:
        pass # No config, no schedule to update

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def trigger_package_creation(compression: str = None, session: Session = Depends(get_session)):
    """Manually trigger the creation of a backup package."""
    try:
        with open("config.yaml", "r") as f:
            config_data = yaml.safe_load(f)
            package_conf = config_data.get("package-conf", {})

            comp_to_use = compression or package_conf.get("compression", "zip")

            create_package(session, comp_to_use)
            return {"message": "Package creation triggered."}

    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="config.yaml not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
