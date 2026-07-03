import os
import subprocess
import logging
from celery import shared_task
from django.conf import settings
from .models import Video

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def convert_video_to_hls(self, video_id):
    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        logger.error(f"Video with ID {video_id} does not exist.")
        return

    if not video.video_file:
        logger.error(f"Video {video_id} has no file attached.")
        return

    input_path = video.video_file.path

    if not os.path.exists(input_path):
        logger.error(f"Input file not found at {input_path}")
        return

    base_output_dir = os.path.join(settings.MEDIA_ROOT, 'videos', 'hls', str(video.id))
    os.makedirs(base_output_dir, exist_ok=True)

    master_playlist_path = os.path.join(base_output_dir, 'master.m3u8')

    ffmpeg_cmd = [
        'ffmpeg',
        '-i', input_path,
        '-y',

        '-map', '0:v:0', '-map', '0:a:0',
        '-s:v:0', '640x360', '-c:v:0', 'libx264', '-b:v:0', '800k',

        '-map', '0:v:0', '-map', '0:a:0',
        '-s:v:1', '854x480', '-c:v:1', 'libx264', '-b:v:1', '1400k',

        '-map', '0:v:0', '-map', '0:a:0',
        '-s:v:2', '1280x720', '-c:v:2', 'libx264', '-b:v:2', '2800k',

        '-c:a', 'aac', '-b:a', '128k',

        '-f', 'hls',
        '-hls_time', '10',
        '-hls_playlist_type', 'vod',  # نوع استریم: VOD (Video on Demand)
        '-hls_segment_filename', os.path.join(base_output_dir, 'v%v_fileSequence%d.ts'),

        '-master_pl_name', 'master.m3u8',
        '-var_stream_map', 'v:0,a:0 v:1,a:1 v:2,a:2',

        os.path.join(base_output_dir, 'v%v_prog_index.m3u8')
    ]

    try:

        process = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.returncode != 0:
            logger.error(f"FFmpeg error for video {video_id}:\n{process.stderr}")
            raise Exception(f"FFmpeg process failed with exit code {process.returncode}")

        relative_master_path = os.path.relpath(master_playlist_path, settings.MEDIA_ROOT)
        video.hls_file = relative_master_path
        video.status = 'published'
        video.save()

        logger.info(f"Video {video_id} successfully converted to HLS.")
        video.video_file.delete(save=False)
        video.save()
        if os.path.exists(input_path):
            os.remove(input_path)

    except Exception as exc:
        logger.error(f"Task convert_video_to_hls failed for video {video_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
