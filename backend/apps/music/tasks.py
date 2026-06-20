import os
import tempfile
import zipfile
import rarfile
import shutil
from mutagen import File as MutagenFile
from celery import shared_task
from django.core.files import File
from config.settings import SITE_URL
from apps.common.connectors import MockStorageConnector
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils.text import slugify
from django.core.cache import cache
from datetime import timedelta
from django.utils import timezone
import uuid
from django.core.files.base import ContentFile
from django.db import transaction
from .models import Album, AlbumArchiveUpload, Track, Artist, AlbumZipExport ,Genre
import logging


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_album_archive_task(self, upload_record_id: int):
    temp_dir = None
    upload_record = None

    try:
        upload_record = AlbumArchiveUpload.objects.select_related("album").get(id=upload_record_id)
        album = upload_record.album

        upload_record.status = "extracting"
        upload_record.save(update_fields=["status"])

        archive_path = upload_record.archive_file.path
        temp_dir = tempfile.mkdtemp()

        # -------- Extract --------
        if archive_path.lower().endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
        elif archive_path.lower().endswith(".rar"):
            with rarfile.RarFile(archive_path, "r") as rar_ref:
                rar_ref.extractall(temp_dir)
        else:
            raise ValueError("فرمت فایل آرشیو پشتیبانی نمی‌شود. فقط zip و rar مجاز است.")

        upload_record.status = "processing"
        upload_record.save(update_fields=["status"])

        # -------- Collect audio files --------
        audio_extensions = (".mp3", ".flac", ".wav", ".m4a")
        audio_files = [
            os.path.join(root, f)
            for root, _, files in os.walk(temp_dir)
            for f in files
            if f.lower().endswith(audio_extensions)
        ]

        if not audio_files:
            raise ValueError("هیچ فایل صوتی مجازی در آرشیو یافت نشد.")

        total_files = len(audio_files)
        cover_extracted = bool(album.cover_image)
        storage_connector = MockStorageConnector()
        artist_cache = {}
        tracks_to_update = []
        task_warnings = []

        for index, file_path in enumerate(audio_files):
            try:
                try:
                    audio_raw = MutagenFile(file_path)
                    audio_meta = MutagenFile(file_path, easy=True)
                except Exception as meta_error:
                    logger.warning(f"Skipping {file_path}: Metadata read error - {meta_error}")
                    task_warnings.append(f"خطا در خواندن فایل {os.path.basename(file_path)}")
                    continue

                if not audio_meta:
                    continue

                # -------- Extract cover once ایمن --------
                if not cover_extracted and audio_raw:
                    try:
                        image_data, mime_type = None, None

                        if hasattr(audio_raw, "tags") and audio_raw.tags:
                            for tag in audio_raw.tags.values():
                                if tag.__class__.__name__ == "APIC":
                                    image_data = tag.data
                                    mime_type = tag.mime
                                    break

                        if not image_data and hasattr(audio_raw, "pictures") and audio_raw.pictures:
                            pic = audio_raw.pictures[0]
                            image_data = pic.data
                            mime_type = pic.mime

                        if image_data:
                            ext = {"image/png": "png", "image/webp": "webp"}.get(mime_type, "jpg")
                            filename = f"album_cover_{album.id}_{uuid.uuid4().hex[:6]}.{ext}"
                            album.cover_image.save(filename, ContentFile(image_data), save=True)
                            cover_extracted = True
                    except Exception as cover_error:
                        logger.warning(f"Failed to extract cover from {file_path}: {cover_error}")

                # -------- Metadata Extraction --------
                # 1. Title & Slug
                raw_title = audio_meta.get("title", [os.path.basename(file_path)])[0]
                safe_title = (raw_title or "Untitled")[:450]
                safe_slug = slugify(safe_title, allow_unicode=True)[:450]
                if not safe_slug:
                    safe_slug = f"track-{uuid.uuid4().hex[:10]}"

                # 2. Track Number (تبدیل ایمن به عدد)
                raw_track_number = audio_meta.get("tracknumber", [str(index + 1)])[0]
                try:
                    # مثلا اگر "1/12" باشد فقط "1" را میگیرد
                    clean_track_str = str(raw_track_number).split("/")[0].strip()
                    track_number = int(clean_track_str) if clean_track_str.isdigit() else (index + 1)
                except (ValueError, TypeError, AttributeError):
                    track_number = index + 1

                # 3. Artist -------------

                raw_artist_name = audio_meta.get("artist", [None])[0]
                album_artist_name = raw_artist_name.strip() if raw_artist_name else None
                artist_obj = None
                if album_artist_name:
                    artist_obj = Artist.objects.filter(name__iexact=album_artist_name).first()

                if not artist_obj:
                    artist_obj, _ = Artist.objects.get_or_create(name="Unknown Artist",defaults={"artist_type": "unknown"})

                # Genre ------------
                genre_name = audio_meta.get("genre", [None])[0]
                genre_obj = None
                if genre_name:
                    genre_obj = Genre.objects.filter(name=genre_name).only("id").first()

                # 4. Duration
                duration_ms = 0
                if audio_meta.info and hasattr(audio_meta.info, "length"):
                    try:
                        duration_ms = int(audio_meta.info.length * 1000)
                    except (ValueError, TypeError):
                        pass

                # -------- Upload file --------
                filename = os.path.basename(file_path)
                target_relative_path = f"tracks/{album.slug}/{filename}"
                final_path = storage_connector.upload_chunked(file_path, target_relative_path)

                tracks_to_update.append({
                    "album": album,
                    "track_number": track_number,
                    "defaults": {
                        "title": safe_title,
                        "slug": safe_slug,
                        "genre": genre_obj,
                        "composer": artist_obj,
                        "duration_ms": duration_ms,
                        "audio_file": final_path,
                    }
                })

                # -------- Progress update --------
                if index % 5 == 0 or index == total_files - 1:
                    progress = int(((index + 1) / total_files) * 90)  # رزرو 10 درصد آخر برای ذخیره دیتابیس
                    AlbumArchiveUpload.objects.filter(id=upload_record_id).update(progress=progress)

            except Exception as track_error:
                logger.error(f"Track processing error on {file_path}: {track_error}")
                task_warnings.append(f"خطا در پردازش کامل فایل {os.path.basename(file_path)}")
                continue


        saved_tracks_count = 0
        for data in tracks_to_update:
            try:
                with transaction.atomic():
                    Track.objects.update_or_create(
                        album=data["album"],
                        track_number=data["track_number"],
                        defaults=data["defaults"],
                    )

                saved_tracks_count += 1
            except Exception as db_err:
                logger.error(f"DB Update failed for track {data.get('title')}: {db_err}")
                task_warnings.append(f"خطای دیتابیس برای ترک {data.get('title')}")

        # بروزرسانی وضعیت نهایی
        upload_record.status = "completed"
        upload_record.progress = 100

        # اگر در طول پروسه هشداری داشتیم، آن را در لاگ ذخیره میکنیم تا مدیر ببیند
        if task_warnings:
            upload_record.error_log = "هشدارهای تسک:\n" + "\n".join(task_warnings)

        upload_record.save(update_fields=["status", "progress", "error_log"])

    except ValueError as ve:
        # خطاهای منطقی (مثل فرمت اشتباه) نیازی به Retry ندارند
        if upload_record:
            upload_record.status = "failed"
            upload_record.error_log = str(ve)
            upload_record.save(update_fields=["status", "error_log"])
        logger.error(f"Validation Error in task {upload_record_id}: {ve}")

    except Exception as e:
        # خطاهای پیش بینی نشده (شبکه، دیتابیس اصلی، پر شدن هارد) نیاز به Retry دارند
        if upload_record:
            upload_record.status = "failed"
            upload_record.error_log = str(e)
            upload_record.save(update_fields=["status", "error_log"])
        logger.exception(f"Unexpected error in task {upload_record_id}")
        raise self.retry(exc=e, countdown=10)

    finally:
        # حذف ایمن پوشه موقت
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_err:
                logger.error(f"Failed to delete temp dir {temp_dir}: {cleanup_err}")


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


@shared_task
def extract_track_metadata_task(track_id):
    try:
        track = Track.objects.get(id=track_id)

        old_title = track.title

        track.extract_metadata()

        update_fields_list = [
            'title', 'duration_ms', 'singer', 'composer',
            'genre', 'track_number', 'release_date', 'cover_image'
        ]

        if track.title != old_title and not track.slug:
            track.slug = slugify(track.title, allow_unicode=True)
            update_fields_list.append('slug')

        track.save(update_fields=update_fields_list)

    except Track.DoesNotExist:
        pass