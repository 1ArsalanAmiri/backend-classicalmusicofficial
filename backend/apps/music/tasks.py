import os
import tempfile
import zipfile
import rarfile
from mutagen import File as MutagenFile
from celery import shared_task
from django.core.files import File
from config.settings import SITE_URL
from .models import *
from apps.common.connectors import MockStorageConnector
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils.text import slugify
from django.core.cache import cache
from datetime import timedelta
from django.utils import timezone


@shared_task
def process_album_archive_task(upload_record_id: int):
    try:
        upload_record = AlbumArchiveUpload.objects.get(id=upload_record_id)
        upload_record.status = 'extracting'
        upload_record.save()

        album = upload_record.album
        archive_path = upload_record.archive_file.path

        temp_dir = tempfile.mkdtemp()

        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
        elif archive_path.endswith('.rar'):
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                rar_ref.extractall(temp_dir)

        upload_record.status = 'processing'
        upload_record.save()

        audio_extensions = ('.mp3', '.flac', '.wav', '.m4a')
        audio_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(audio_extensions):
                    audio_files.append(os.path.join(root, file))

        total_files = len(audio_files)
        if total_files == 0:
            raise ValueError("no file exist in archive")

        storage_connector = MockStorageConnector()

        for index, file_path in enumerate(audio_files):
            audio_meta = MutagenFile(file_path, easy=True)

            title = audio_meta.get('title', [os.path.basename(file_path)])[0]
            track_number = audio_meta.get('tracknumber', [str(index + 1)])[0]
            artist_name = audio_meta.get('artist', ['Unknown Artist'])[0]
            genre = audio_meta.get('genre', [None])[0]

            duration_ms = int(audio_meta.info.length * 1000) if hasattr(audio_meta.info, 'length') else 0

            artist, _ = Artist.objects.get_or_create(
                name=artist_name,
                defaults={'slug': slugify(artist_name)}
            )

            # فرمت: tracks/{album_slug}/{filename}
            filename = os.path.basename(file_path)
            target_relative_path = f"tracks/{album.slug}/{filename}"

            final_path = storage_connector.upload_chunked(file_path, target_relative_path)

            raw_title = title or "Untitled"

            safe_title = raw_title[:95]


            raw_slug = slugify(raw_title, allow_unicode=True)
            safe_slug = raw_slug[:95]


            Track.objects.update_or_create(
                album=album,
                track_number=track_number.split('/')[0],
                defaults={
                    'title': safe_title,
                    'slug': safe_slug,
                    'genre': genre,
                    'composer': artist,
                    'duration_ms': duration_ms,
                    'audio_file': final_path,
                }
            )

            progress = int(((index + 1) / total_files) * 100)
            upload_record.progress = progress
            upload_record.save()

        upload_record.status = 'completed'
        upload_record.save()

    except Exception as e:
        upload_record.status = 'failed'
        upload_record.error_log = str(e)
        upload_record.save()

    finally:
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)


def send_status_to_websocket(album_slug, status, message, download_url=None):
    channel_layer = get_channel_layer()
    group_name = f'album_{album_slug}'

    event_data = {
        'type': 'zip_status',
        'message': {
            'status': status,
            'message': message,
            'download_url': download_url
        }
    }
    print(f"--- CELERY SENDING EVENT TO GROUP: {group_name} ---")
    print(event_data)
    print("-----------------------------------------------")

    async_to_sync(channel_layer.group_send)(
        group_name,
        event_data
    )


@shared_task(bind=True)
def generate_album_zip_task(self, album_id, export_record_id):
    lock_id = f"lock_album_zip_{album_id}"

    if not cache.add(lock_id, 'locked', 600):
        return "Task is already running for this album."

    try:
        album = Album.objects.get(id=album_id)
        export_record = AlbumZipExport.objects.get(id=export_record_id)

        export_record.status = 'PROCESSING'
        export_record.save()

        with tempfile.NamedTemporaryFile(delete=True, suffix='.zip') as tmp_file:
            with zipfile.ZipFile(tmp_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                for track in album.tracks.all():
                    if track.audio_file:
                        file_path = track.audio_file.path
                        file_name = os.path.basename(file_path)
                        zf.write(file_path, arcname=file_name)

            tmp_file.flush()
            export_record.zip_file.save(f"{album.slug}.zip", File(tmp_file))

        export_record.status = 'COMPLETED'
        export_record.save()

        download_link = f"{SITE_URL}/api/v1/albums/{album.slug}/download-zip/"

        send_status_to_websocket(
            album_slug=album.slug,
            status='COMPLETED',
            message='Zip file is completed successfully.',
            download_url=download_link
        )

    except Exception as e:
        if 'export_record' in locals():
            export_record.status = 'FAILED'
            export_record.save()
        raise e
    finally:
        cache.delete(lock_id)


@shared_task
def cleanup_old_zip_exports():
    time_threshold = timezone.now() - timedelta(hours=24)
    old_exports = AlbumZipExport.objects.filter(created_at__lt=time_threshold)

    deleted_count = 0
    for export in old_exports:
        if export.zip_file:
            export.zip_file.delete(save=False)
        export.delete()
        deleted_count += 1

    return f"Deleted {deleted_count} old zip files."
