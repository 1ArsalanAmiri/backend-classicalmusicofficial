from ftplib import FTP_TLS, error_perm
import posixpath

from django.conf import settings
from django.core.files.storage import Storage


class FTPStorage(Storage):
    """
    Django storage backend for HostDL Explicit FTPS storage.

    Files are stored under:
        /www/

    Public URL:
        http://dl.clmusic.ir/
    """

    def _connect(self):
        ftp = FTP_TLS()

        ftp.connect(
            host=settings.FTP_HOST,
            port=settings.FTP_PORT,
            timeout=settings.FTP_TIMEOUT,
        )

        ftp.login(
            user=settings.FTP_USERNAME,
            passwd=settings.FTP_PASSWORD,
        )

        # Encrypt FTP data connection.
        ftp.prot_p()

        # Use binary mode for MP3, MP4, FLAC, images, etc.
        ftp.voidcmd("TYPE I")

        ftp.cwd(settings.FTP_ROOT)

        return ftp

    def _ensure_directory(self, ftp, directory):
        """
        Create nested directories if they don't exist.
        """
        if not directory:
            return

        current = ftp.pwd()

        for part in directory.strip("/").split("/"):
            if not part:
                continue

            try:
                ftp.cwd(part)
            except error_perm:
                ftp.mkd(part)
                ftp.cwd(part)

        ftp.cwd(current)

    def _save(self, name, content):
        name = name.replace("\\", "/").lstrip("/")

        directory = posixpath.dirname(name)
        filename = posixpath.basename(name)

        ftp = self._connect()

        try:
            if directory:
                self._ensure_directory(ftp, directory)
                ftp.cwd(directory)

            ftp.storbinary(
                f"STOR {filename}",
                content.file,
                blocksize=1024 * 1024,
            )

        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

        return name

    def delete(self, name):
        if not name:
            return

        name = name.replace("\\", "/").lstrip("/")

        ftp = self._connect()

        try:
            directory = posixpath.dirname(name)
            filename = posixpath.basename(name)

            if directory:
                try:
                    ftp.cwd(directory)
                except error_perm as exc:
                    if str(exc).startswith("550"):
                        return
                    raise

            try:
                ftp.delete(filename)
            except error_perm as exc:
                if not str(exc).startswith("550"):
                    raise

        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

    def exists(self, name):
        if not name:
            return False

        name = name.replace("\\", "/").lstrip("/")

        ftp = self._connect()

        try:
            directory = posixpath.dirname(name)
            filename = posixpath.basename(name)

            if directory:
                try:
                    ftp.cwd(directory)
                except error_perm as exc:
                    if str(exc).startswith("550"):
                        return False
                    raise

            try:
                ftp.size(filename)
                return True
            except error_perm as exc:
                if str(exc).startswith("550"):
                    return False
                raise

        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

    def size(self, name):
        name = name.replace("\\", "/").lstrip("/")

        ftp = self._connect()

        try:
            directory = posixpath.dirname(name)
            filename = posixpath.basename(name)

            if directory:
                ftp.cwd(directory)

            return ftp.size(filename)

        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

    def url(self, name):
        if not name:
            return settings.MEDIA_URL

        return (
            settings.MEDIA_URL.rstrip("/")
            + "/"
            + name.lstrip("/")
        )

    def get_name(self, name):
        return name.replace("\\", "/").lstrip("/")

    def path(self, name):
        """
        FTP storage has no local filesystem path.
        """
        raise NotImplementedError(
            "FTPStorage does not support local filesystem paths."
        )

