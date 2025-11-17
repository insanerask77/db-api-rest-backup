# backup_api/storage.py
import abc
import os
from fastapi.responses import FileResponse, RedirectResponse
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

class StorageProvider(abc.ABC):
    @abc.abstractmethod
    def save(self, source_path: str, destination_path: str) -> None:
        pass

    @abc.abstractmethod
    def delete(self, file_path: str) -> bool:
        pass

    @abc.abstractmethod
    def get_download_response(self, file_path: str) -> FileResponse | RedirectResponse:
        pass

    @abc.abstractmethod
    def download_file(self, file_path: str, destination_path: str) -> None:
        pass


class LocalStorage(StorageProvider):
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def save(self, source_path: str, destination_path: str) -> None:
        final_destination = os.path.join(self.base_path, destination_path)
        os.makedirs(os.path.dirname(final_destination), exist_ok=True)
        os.rename(source_path, final_destination)

    def delete(self, file_path: str) -> bool:
        full_path = os.path.join(self.base_path, file_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                return True
            except OSError:
                return False
        return True

    def get_download_response(self, file_path: str) -> FileResponse:
        full_path = os.path.join(self.base_path, file_path)
        return FileResponse(path=full_path, filename=os.path.basename(file_path))

    def download_file(self, file_path: str, destination_path: str) -> None:
        import shutil
        source = os.path.join(self.base_path, file_path)
        shutil.copy(source, destination_path)


class S3Storage(StorageProvider):
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket: str):
        self.bucket = bucket
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4')
        )
        self._create_bucket_if_not_exists()

    def _create_bucket_if_not_exists(self):
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                self.s3_client.create_bucket(Bucket=self.bucket)
            else:
                raise

    def save(self, source_path: str, destination_path: str) -> None:
        self.s3_client.upload_file(source_path, self.bucket, destination_path)

    def delete(self, file_path: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=file_path)
            return True
        except ClientError as e:
            print(f"Failed to delete {file_path} from S3: {e}")
            return False

    def get_download_response(self, file_path: str) -> RedirectResponse:
        url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': file_path},
            ExpiresIn=3600  # 1 hour
        )
        return RedirectResponse(url=url)

    def download_file(self, file_path: str, destination_path: str) -> None:
        self.s3_client.download_file(self.bucket, file_path, destination_path)


_storage_provider: StorageProvider = None

def get_storage_provider(config: dict) -> StorageProvider:
    global _storage_provider
    if _storage_provider is None:
        storage_config = config.get('storage', {'type': 'local'})
        if storage_config['type'] == 's3':
            _storage_provider = S3Storage(**storage_config['s3'])
        else:
            _storage_provider = LocalStorage(base_path='data')
    return _storage_provider
