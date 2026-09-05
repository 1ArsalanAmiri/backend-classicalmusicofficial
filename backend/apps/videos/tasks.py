import os
import shutil
import subprocess
import tempfile
import logging
from celery import shared_task
from django.core.files.base import File
from django.core.files.storage import default_storage
from .models import Video

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    soft_time_limit=1800,   
    time_limit=1900,
)
def convert_video_to_hls(self, video_id):
    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        logger.warning("convert_video_to_hls: video %s does not exist", video_id)
        return

    if not video.video_file:
        logger.warning("convert_video_to_hls: video %s has no video_file", video_id)
        return

    work_dir = tempfile.mkdtemp(prefix=f"hls_{video_id}_")
    input_ext = os.path.splitext(video.video_file.name)[1] or ".mp4"
    local_input_path = os.path.join(work_dir, f"input{input_ext}")
    local_output_dir = os.path.join(work_dir, "output")
    os.makedirs(local_output_dir, exist_ok=True)

    try:
        with default_storage.open(video.video_file.name, 'rb') as remote_file:
            with open(local_input_path, 'wb') as local_file:
                shutil.copyfileobj(remote_file, local_file)

        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', local_input_path,
            '-map', '0:v:0', '-map', '0:a:0', '-s:v:0', '640x360', '-c:v:0', 'libx264', '-preset', 'veryfast', '-b:v:0', '800k',
            '-map', '0:v:0', '-map', '0:a:0', '-s:v:1', '854x480', '-c:v:1', 'libx264', '-preset', 'veryfast', '-b:v:1', '1400k',
            '-map', '0:v:0', '-map', '0:a:0', '-s:v:2', '1280x720', '-c:v:2', 'libx264', '-preset', 'veryfast', '-b:v:2', '2800k',
            '-c:a', 'aac', '-b:a', '128k', '-f', 'hls', '-hls_time', '10',
            '-hls_playlist_type', 'vod',
            '-hls_segment_filename', os.path.join(local_output_dir, 'v%v_fileSequence%d.ts'),
            '-master_pl_name', 'master.m3u8',
            '-var_stream_map', 'v:0,a:0 v:1,a:1 v:2,a:2',
            os.path.join(local_output_dir, 'v%v_prog_index.m3u8'),
        ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(
                "ffmpeg failed for video %s (exit code %s)\n--- stdout ---\n%s\n--- stderr ---\n%s",
                video_id, result.returncode, result.stdout, result.stderr,
            )
            raise RuntimeError(f"ffmpeg exited with code {result.returncode} for video {video_id}")

        remote_base = f"videos/hls/{video.id}"
        output_files = sorted(
            f for f in os.listdir(local_output_dir)
            if os.path.isfile(os.path.join(local_output_dir, f))
        )
        if not output_files:
            raise RuntimeError(f"ffmpeg produced no output files for video {video_id}")

        for filename in output_files:
            local_file_path = os.path.join(local_output_dir, filename)
            remote_name = f"{remote_base}/{filename}"
            with open(local_file_path, 'rb') as f:
                default_storage.save(remote_name, File(f))

        remote_master_name = f"{remote_base}/master.m3u8"

        Video.objects.filter(pk=video.pk).update(
            hls_file=remote_master_name,
            status='published',
        )

        default_storage.delete(video.video_file.name)
        Video.objects.filter(pk=video.pk).update(video_file=None)

    except Exception as exc:
        logger.exception("convert_video_to_hls failed for video %s", video_id)
        raise self.retry(exc=exc)

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)