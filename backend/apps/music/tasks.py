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
from .models import AlbumArchiveUpload, Track, Artist, AlbumZipExport, Genre
from .utils import MockStorageConnector


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_album_archive_task(self, upload_record_id: int):
    temp_dir = None
    upload_record = None

    try:
        upload_record = AlbumArchiveUpload.objects.select_related("album").prefetch_related("album__main_artists").get(id=upload_record_id)
        album = upload_record.album

        upload_record.status = "extracting"
        upload_record.save(update_fields=["status"])

        archive_path = upload_record.archive_file.path
        if not os.path.exists(archive_path):
            raise ValueError("فایل آرشیو در مسیر مشخص شده یافت نشد.")

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
        tracks_to_update = []
        task_warnings = []

        used_track_numbers = set(album.tracks.values_list('track_number', flat=True))


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
                # 1. Title & Slug
                raw_title_list = audio_meta.get("title", [filename])
                raw_title = raw_title_list[0] if raw_title_list else filename
                safe_title = (str(raw_title) or "Untitled")[:450]

                base_slug = slugify(safe_title, allow_unicode=True)[:400]
                unique_suffix = uuid.uuid4().hex[:8]
                safe_slug = f"{base_slug}-{unique_suffix}" if base_slug else f"track-{unique_suffix}"

                if not safe_slug:
                    safe_slug = f"track-{uuid.uuid4().hex[:10]}"

                # 2. Track Number
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

                # 3. Artist Extraction
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

                # -----------------------
                # 4. Genre
                genre_name_list = audio_meta.get("genre", [None])
                genre_name = genre_name_list[0] if genre_name_list else None
                genre_obj = None
                if genre_name:
                    genre_obj = Genre.objects.filter(name=str(genre_name)).only("id").first()

                # 5. Duration
                duration_ms = 0
                if hasattr(audio_meta, "info") and hasattr(audio_meta.info, "length"):
                    try:
                        duration_ms = int(float(audio_meta.info.length) * 1000)
                    except (ValueError, TypeError):
                        pass

                # -------- Upload file --------
                target_relative_path = f"tracks/{album.slug}/{filename}"
                saved_path = None
                try:
                    with open(file_path, 'rb') as f:
                        saved_path = default_storage.save(target_relative_path, File(f))

                except Exception as upload_err:
                    logger.error(f"Upload failed for {file_path}: {upload_err}")
                    task_warnings.append(f"خطا در ذخیره‌سازی فایل {filename}")
                    continue
                tracks_to_update.append({
                    "album": album,
                    "track_number": track_number,
                    "defaults": {
                        "title": safe_title,
                        "slug": safe_slug,
                        "genre": genre_obj,
                        "duration_ms": duration_ms,
                        "audio_file": saved_path,
                        "status": "published",
                    },
                    "artist_objs": track_artists
                })
                # -------- Progress update --------
                if index % 5 == 0 or index == total_files - 1:
                    progress = int(((index + 1) / total_files) * 90)
                    AlbumArchiveUpload.objects.filter(id=upload_record_id).update(progress=progress)

            except Exception as track_error:
                logger.error(f"Track processing error on {file_path}: {track_error}")
                task_warnings.append(f"خطا در پردازش کامل فایل {filename}")
                continue

        # -------- Database Save --------
        # -------- Database Save --------
        saved_tracks_count = 0
        for data in tracks_to_update:
            track_title = data["defaults"].get("title", "Unknown")
            try:
                with transaction.atomic():
                    track, created = Track.objects.update_or_create(
                        album=data["album"],
                        track_number=data["track_number"],
                        defaults=data["defaults"],
                    )
                    if data["artist_objs"]:
                        track.artists.add(*data["artist_objs"])

                saved_tracks_count += 1
            except Exception as db_err:
                logger.error(f"DB Update failed for track {track_title}: {db_err}")
                task_warnings.append(f"خطای دیتابیس در ذخیره ترک {track_title}")

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
        # Retrying only on unexpected exceptions (like DB deadlock, storage timeouts, etc.)
        raise self.retry(exc=e, countdown=10)

    finally:
        tracks_to_create = []
        for data in tracks_to_update:
            track = Track(
                album=data["album"],
                track_number=data["track_number"],
                title=data["defaults"].get("title"),
                slug=data["defaults"].get("slug"),
                genre=data["defaults"].get("genre"),
                duration_ms=data["defaults"].get("duration_ms"),
                audio_file=data["defaults"].get("audio_file"),
                status=data["defaults"].get("status")
            )
            tracks_to_create.append(track)

        if tracks_to_create:
            Track.objects.bulk_create(tracks_to_create)
            
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
            track.slug = slugify(track.title, allow_unicode=True)
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
            if export.zip_file and os.path.exists(export.zip_file.path):
                try:
                    os.remove(export.zip_file.path)
                except OSError as e:
                    logger.error(f"Failed to remove file {export.zip_file.path}: {e}")
                    continue
            export.delete()
            deleted_count += 1

        return f"Successfully deleted {deleted_count} old album zip caches."
    except Exception as e:
        logger.error(f"Error in cleanup_old_album_zips: {e}")
        return "Failed during cleanup."
