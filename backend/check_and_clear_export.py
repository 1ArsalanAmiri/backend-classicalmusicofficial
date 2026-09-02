import os
from apps.music.models import Album, AlbumZipExport

album = Album.objects.get(slug="claudio-monteverdi-lorfeo")
exports = AlbumZipExport.objects.filter(album=album)

print(f"تعداد AlbumZipExport موجود برای این آلبوم: {exports.count()}")
for e in exports:
    print(f"  id={e.id} status={e.status} zip_file={e.zip_file} created_at={e.created_at}")
    if e.zip_file:
        try:
            size = os.path.getsize(e.zip_file.path)
            print(f"    حجم فایل روی دیسک: {size} بایت")
        except Exception as ex:
            print(f"    فایل روی دیسک پیدا نشد: {ex}")

print("\nدر حال پاک کردن...")
for e in exports:
    if e.zip_file:
        try:
            if os.path.exists(e.zip_file.path):
                os.remove(e.zip_file.path)
        except Exception as ex:
            print(f"خطا در حذف فایل: {ex}")
    e.delete()
print("پاک شد. حالا /download-zip/ رو دوباره تست کن.")
