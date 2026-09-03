import os
import tempfile
import zipfile
import rarfile
import shutil
import uuid
import logging
from datetime import timedelta
from django.core.files.storage import default_storage
from django.core.files.base import File
from django.utils import timezone
from django.utils.text import slugify
from django.core.files.base import ContentFile
from django.db import transaction
from celery import shared_task
from mutagen import File as MutagenFile
from django.utils.text import get_valid_filename
from .models import AlbumArchiveUpload, Track, Artist, AlbumZipExport, Genre, AlbumType, Album
from .utils import MockStorageConnector
from django.conf import settings
from apps.common.models import PublishStatus


logger = logging.getLogger(__name__)

TRACK_TITLE_MAX_LENGTH = Track._meta.get_field('title').max_length
TRACK_SLUG_MAX_LENGTH = Track._meta.get_field('slug').max_length


def _build_unique_track_slug(title: str) -> str:

    unique_suffix = uuid.uuid4().hex[:8]
    max_base_length = max(TRACK_SLUG_MAX_LENGTH - (len(unique_suffix) + 1), 1)
    base_slug = slugify(title, allow_unicode=True)[:max_base_length]
    return f"{base_slug}-{unique_suffix}" if base_slug else f"track-{unique_suffix}"


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    soft_time_limit=2400,  
    time_limit=2500,
)
def process_album_archive_task(self, upload_record_id: int):
    temp_dir = None
    upload_record = None

    try:
        upload_record = AlbumArchiveUpload.objects.select_related("album").prefetch_related("album__main_artists").get(
            id=upload_record_id)
        album = upload_record.album

        upload_record.status = "extracting"
        upload_record.save(update_fields=["status"])

        temp_dir = tempfile.mkdtemp()

        original_name = upload_record.archive_file.name
        archive_ext = os.path.splitext(original_name)[1].lower()
        archive_path = os.path.join(temp_dir, f"archive{archive_ext}")

        with default_storage.open(original_name, 'rb') as remote_f:
            with open(archive_path, 'wb') as local_f:
                shutil.copyfileobj(remote_f, local_f)

        if not os.path.exists(archive_path) or os.path.getsize(archive_path) == 0:
            raise ValueError("دانلود فایل آرشیو از storage ناموفق بود یا فایل خالی است.")

        # -------- Extract --------
        if archive_ext == ".zip":
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
        elif archive_ext == ".rar":
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
        task_warnings = []

        used_track_numbers = set(album.tracks.values_list('track_number', flat=True))

        tracks_data_list = []

        for index, file_path in enumerate(audio_files):
            raw_filename = os.path.basename(file_path)
            filename = get_valid_filename(raw_filename).replace(" ", "_").replace("%", "_")
            try:
                os.chmod(file_path, 0o644)
            except Exception as e:
                logger.warning(f"Could not change permissions for {file_path}: {e}")

            try:
                try:
                    audio_raw = MutagenFile(file_path)
                    audio_meta = MutagenFile(file_path, easy=True)
                except Exception as meta_error:
                    logger.warning(f"Skipping {file_path}: Metadata read error - {meta_error}")
                    task_warnings.append(f"خطا در خواندن متادیتا فایل {filename}")
                    continue

                if not audio_meta:
                    audio_meta = audio_raw
                    if not audio_meta:
                        task_warnings.append(f"فایل {filename} فاقد متادیتای معتبر است.")
                        continue

                # -------- Extract cover --------
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
                            cover_filename = f"album_cover_{album.id}_{uuid.uuid4().hex[:6]}.{ext}"
                            album.cover_image.save(cover_filename, ContentFile(image_data), save=True)
                            cover_extracted = True
                    except Exception as cover_error:
                        logger.warning(f"Failed to extract cover from {file_path}: {cover_error}")

                # -------- Metadata Extraction --------
                raw_title_list = audio_meta.get("title", [filename])
                raw_title = raw_title_list[0] if raw_title_list else filename
                safe_title = (str(raw_title) or "Untitled").strip()[:TRACK_TITLE_MAX_LENGTH]

                safe_slug = _build_unique_track_slug(safe_title)

                raw_track_number_list = audio_meta.get("tracknumber", [str(index + 1)])
                raw_track_number = raw_track_number_list[0] if raw_track_number_list else str(index + 1)
                try:
                    clean_track_str = str(raw_track_number).split("/")[0].strip()
                    track_number = int(clean_track_str) if clean_track_str.isdigit() else (index + 1)
                except (ValueError, TypeError, AttributeError):
                    track_number = index + 1

                while track_number in used_track_numbers:
                    track_number += 1
                used_track_numbers.add(track_number)

                album_artists = list(album.main_artists.all())

                if album_artists:
                    track_artists = album_artists
                else:
                    raw_artist_name_list = audio_meta.get("artist", [None])
                    raw_artist_name = raw_artist_name_list[0] if raw_artist_name_list else None
                    track_artist_name = str(raw_artist_name).strip() if raw_artist_name else None

                    track_artists = []
                    if track_artist_name:
                        found_artist = Artist.objects.filter(name__iexact=track_artist_name).first()
                        if found_artist:
                            track_artists.append(found_artist)

                    if not track_artists:
                        unknown_artist, _ = Artist.objects.get_or_create(
                            name="Unknown Artist", defaults={"artist_type": "other"}
                        )
                        track_artists.append(unknown_artist)

                genre_name_list = audio_meta.get("genre", [None])
                genre_name = genre_name_list[0] if genre_name_list else None
                genre_obj = None
                if genre_name:
                    genre_obj = Genre.objects.filter(name=str(genre_name)).only("id").first()

                duration_ms = 0
                if hasattr(audio_meta, "info") and hasattr(audio_meta.info, "length"):
                    try:
                        duration_ms = int(float(audio_meta.info.length) * 1000)
                    except (ValueError, TypeError):
                        pass

                # ساخت نمونه ترک در حافظه RAM (بدون audio_file هنوز)
                track_instance = Track(
                    album=album,
                    track_number=track_number,
                    title=safe_title,
                    slug=safe_slug,
                    genre=genre_obj,
                    duration_ms=duration_ms,
                    status=PublishStatus.PUBLISHED,
                )

                try:
                    with open(file_path, 'rb') as f:
                        track_instance.audio_file.save(filename, File(f), save=False)
                except Exception as upload_err:
                    logger.error(f"Upload failed for {file_path}: {upload_err}")
                    task_warnings.append(f"خطا در ذخیره‌سازی فایل {filename}")
                    continue

                tracks_data_list.append({
                    "track_instance": track_instance,
                    "artist_objs": track_artists
                })

                if index % 5 == 0 or index == total_files - 1:
                    progress = int(((index + 1) / total_files) * 90)
                    AlbumArchiveUpload.objects.filter(id=upload_record_id).update(progress=progress)

            except Exception as track_error:
                logger.error(f"Track processing error on {file_path}: {track_error}")
                task_warnings.append(f"خطا در پردازش کامل فایل {filename}")
                continue

        # -------- Database Save (Optimized Bulk Insert/Update) --------
        if tracks_data_list:
            try:
                with transaction.atomic():
                    tracks_to_create = [item["track_instance"] for item in tracks_data_list]

                    # ۱. ایجاد یا آپدیت یکجای تمام ترک‌ها با یک کوئری
                    Track.objects.bulk_create(
                        tracks_to_create,
                        update_conflicts=True,
                        unique_fields=['album', 'track_number'],
                        update_fields=['title', 'slug', 'genre', 'duration_ms', 'audio_file', 'status']
                    )

                    # ۲. بازیابی ID ترک‌های ایجادشده جهت اتصال Many-to-Many هنرمندان
                    track_map = {
                        t.track_number: t
                        for t in Track.objects.filter(
                            album=album,
                            track_number__in=[item["track_instance"].track_number for item in tracks_data_list]
                        )
                    }

                    # ۳. ساخت دسته‌جمعی روابط هنرمندان (Track.artists)
                    TrackArtistThrough = Track.artists.through
                    m2m_relations = []

                    for item in tracks_data_list:
                        num = item["track_instance"].track_number
                        saved_track = track_map.get(num)
                        if saved_track:
                            for artist in item["artist_objs"]:
                                m2m_relations.append(
                                    TrackArtistThrough(track_id=saved_track.id, artist_id=artist.id)
                                )

                    if m2m_relations:
                        TrackArtistThrough.objects.bulk_create(m2m_relations, ignore_conflicts=True)

            except Exception as db_err:
                logger.error(f"DB Bulk save failed for album {album.id}: {db_err}")
                task_warnings.append(f"خطای دیتابیس در ذخیره دسته‌جمعی ترک‌ها: {db_err}")

        # -------- Auto-Sync پلی‌لیست‌های ادیتوریال --------
        if album.album_type == AlbumType.EDITORIAL_PLAYLIST:
            from apps.playlists.models import sync_editorial_album_to_playlist
            try:
                sync_editorial_album_to_playlist(album)
            except Exception as sync_err:
                logger.error(f"Editorial playlist sync failed for album {album.id}: {sync_err}")
                task_warnings.append("خطا در همگام‌سازی پلی‌لیست ادیتوریال")

        upload_record.status = "completed"
        upload_record.progress = 100
        if task_warnings:
            upload_record.error_log = "هشدارهای تسک:\n" + "\n".join(task_warnings)
        upload_record.save(update_fields=["status", "progress", "error_log"])

    except ValueError as ve:
        if upload_record:
            upload_record.status = "failed"
            upload_record.error_log = str(ve)
            upload_record.save(update_fields=["status", "error_log"])
        logger.error(f"Validation Error in task {upload_record_id}: {ve}")

    except Exception as e:
        if upload_record:
            upload_record.status = "failed"
            upload_record.error_log = str(e)
            upload_record.save(update_fields=["status", "error_log"])
        logger.exception(f"Unexpected error in task {upload_record_id}")
        raise self.retry(exc=e, countdown=10)

    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_err:
                logger.error(f"Failed to delete temp dir {temp_dir}: {cleanup_err}")


@shared_task
def extract_track_metadata_task(track_id):
    try:
        track = Track.objects.get(id=track_id)
        old_title = track.title
        track.extract_metadata()

        update_fields_list = [
            'title', 'duration_ms', 'genre', 'track_number', 'release_date', 'cover_image'
        ]

        if track.title != old_title and not track.slug:
            track.slug = _build_unique_track_slug(track.title)
            update_fields_list.append('slug')

        track.save(update_fields=update_fields_list)
    except Track.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Metadata extraction failed for track {track_id}: {e}")


@shared_task
def cleanup_old_album_zips():
    try:
        expiration_date = timezone.now() - timedelta(days=7)
        old_exports = AlbumZipExport.objects.filter(created_at__lt=expiration_date)

        deleted_count = 0
        for export in old_exports:
            if export.zip_file and export.zip_file.name:
                try:
                    default_storage.delete(export.zip_file.name)
                except Exception as e:
                    logger.error(f"Failed to remove remote zip {export.zip_file.name}: {e}")
                    continue
            export.delete()
            deleted_count += 1

        return f"Successfully deleted {deleted_count} old album zip caches."
    except Exception as e:
        logger.error(f"Error in cleanup_old_album_zips: {e}")
        return "Failed during cleanup."


@shared_task(bind=True, max_retries=3, default_retry_delay=10, soft_time_limit=1200, time_limit=1300)
def generate_album_zip_task(self, album_id: int):
    zip_export = None
    try:
        album = Album.objects.prefetch_related('tracks').get(pk=album_id)
        zip_export, _ = AlbumZipExport.objects.get_or_create(album=album)

        AlbumZipExport.objects.filter(pk=zip_export.pk).update(
            status=AlbumZipExport.StatusChoices.PROCESSING
        )

        file_name = f"album_{album.id}_{int(timezone.now().timestamp())}.zip"

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_zip_path = os.path.join(tmp_dir, file_name)

            with zipfile.ZipFile(local_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for track in album.tracks.filter(status=PublishStatus.PUBLISHED):
                    if not track.audio_file:
                        continue
                    ext = os.path.splitext(track.audio_file.name)[1]
                    arcname = f"{track.track_number:02d} - {track.title}{ext}"
                    try:
                        with default_storage.open(track.audio_file.name, 'rb') as remote_audio:
                            zip_file.writestr(arcname, remote_audio.read())
                    except Exception as track_err:
                        logger.error(
                            "Could not read track %s for album zip %s: %s",
                            track.id, album_id, track_err,
                        )
                        continue

            # -------- آپلود فایل زیپ نهایی به FTP --------
            remote_zip_name = f"exports/albums/{file_name}"
            with open(local_zip_path, 'rb') as f:
                saved_name = default_storage.save(remote_zip_name, File(f))

        AlbumZipExport.objects.filter(pk=zip_export.pk).update(
            zip_file=saved_name,
            status=AlbumZipExport.StatusChoices.COMPLETED,
            created_at=timezone.now(),
        )

    except Exception as exc:
        if zip_export is not None:
            AlbumZipExport.objects.filter(pk=zip_export.pk).update(
                status=AlbumZipExport.StatusChoices.FAILED
            )
        logger.exception(f"generate_album_zip_task failed for album {album_id}")
        raise self.retry(exc=exc, countdown=10)