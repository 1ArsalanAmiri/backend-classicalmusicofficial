import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


class MockStorageConnector:

    CHUNK_SIZE = 1024 * 1024

    def upload_chunked(self, local_temp_path: str, target_relative_path: str) -> str:

        if default_storage.exists(target_relative_path):
            default_storage.delete(target_relative_path)

        with open(local_temp_path, 'rb') as source_file:

            target_path = default_storage.save(target_relative_path, ContentFile(b''))
            absolute_target_path = default_storage.path(target_path)

            with open(absolute_target_path, 'wb') as dest_file:
                while True:
                    chunk = source_file.read(self.CHUNK_SIZE)
                    if not chunk:
                        break  # پایان فایل
                    dest_file.write(chunk)

        return target_relative_path
