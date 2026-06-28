import random
from faker import Faker
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import CustomUser
from apps.profiles.models import UserProfile
from apps.music.models import (
    Artist, Album, Track, Genre, Instrument, Label
)
from apps.interactions.models import Comment, Like, Follow
from apps.playlists.models import Playlist, PlaylistTrack
from apps.payments.models import Discount

fake = Faker()


class Command(BaseCommand):
    help = "Generate dummy data for development"

    def handle(self, *args, **kwargs):

        self.stdout.write(self.style.SUCCESS("Generating dummy data..."))

        users = self.create_users(10)
        genres = self.create_genres()
        instruments = self.create_instruments()
        labels = self.create_labels(5)
        artists = self.create_artists(10)
        albums = self.create_albums(10, artists, labels)
        tracks = self.create_tracks(50, albums, artists, genres, instruments, labels)

        playlists = self.create_playlists(users, tracks)

        self.create_comments(users, albums)
        self.create_likes(users, artists, albums, tracks, playlists)
        self.create_follows(users, artists, playlists)

        self.create_discounts()

        self.stdout.write(self.style.SUCCESS("Dummy data generated successfully ✅"))

    # -------------------------------------------------
    # USERS
    # -------------------------------------------------

    def create_users(self, count):

        users = []

        for i in range(count):

            phone = f"+989{random.randint(100000000,999999999)}"

            user, _ = CustomUser.objects.get_or_create(
                phone_number=phone,
                defaults={
                    "username": f"user{i}",
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "email": fake.email(),
                }
            )

            user.set_password("password123")
            user.save()

            UserProfile.objects.get_or_create(user=user)

            users.append(user)

        return users

    # -------------------------------------------------
    # GENRES
    # -------------------------------------------------

    def create_genres(self):

        names = [
            "Classical",
            "Baroque",
            "Romantic",
            "Opera",
            "Symphony",
            "Chamber Music",
        ]

        genres = []

        for name in names:

            genre, _ = Genre.objects.get_or_create(
                name=name,
                defaults={"slug": name.lower().replace(" ", "-")}
            )

            genres.append(genre)

        return genres

    # -------------------------------------------------
    # INSTRUMENTS
    # -------------------------------------------------

    def create_instruments(self):

        names = [
            "Piano",
            "Violin",
            "Cello",
            "Flute",
            "Clarinet",
            "Harp"
        ]

        instruments = []

        for name in names:

            inst, _ = Instrument.objects.get_or_create(
                name=name,
                defaults={"slug": name.lower()}
            )

            instruments.append(inst)

        return instruments

    # -------------------------------------------------
    # LABELS
    # -------------------------------------------------

    def create_labels(self, count):

        labels = []

        for _ in range(count):

            name = fake.company()

            label, _ = Label.objects.get_or_create(
                name=name,
                defaults={
                    "slug": name.lower().replace(" ", "-"),
                    "country": fake.country(),
                }
            )

            labels.append(label)

        return labels

    # -------------------------------------------------
    # ARTISTS
    # -------------------------------------------------

    def create_artists(self, count):

        artists = []

        for _ in range(count):

            name = fake.name()

            artist = Artist.objects.create(
                name=name,
                country=fake.country(),
                biography=fake.text(max_nb_chars=300),
                artist_type=random.choice(["person", "ensemble", "orchestra"])
            )

            artists.append(artist)

        return artists

    # -------------------------------------------------
    # ALBUMS
    # -------------------------------------------------

    # -------------------------------------------------
    # ALBUMS
    # -------------------------------------------------

    def create_albums(self, count, artists, labels):

        albums = []

        for _ in range(count):
            # ۱. تولید عنوان و اسلاگ باید داخل حلقه باشد تا برای هر رکورد متفاوت شود
            album_title = fake.sentence(nb_words=3)
            base_slug = slugify(album_title)
            album_slug = base_slug
            counter = 1

            # ۲. بررسی اصولی و بهینه برای یکتا بودن اسلاگ در دیتابیس
            while Album.objects.filter(slug=album_slug).exists():
                album_slug = f"{base_slug}-{counter}"
                counter += 1

            # ۳. ایجاد رکورد جدید در دیتابیس
            album = Album.objects.create(
                title=album_title,
                slug=album_slug,
                composer=fake.name(),
                artist=random.choice(artists),
                conductor=fake.name(),
                orchestra=fake.company(),
                soloist=fake.name(),
                ensemble=fake.company(),
                release_date=fake.date_between("-30y", "today"),
                label=random.choice(labels),
            )

            albums.append(album)

        return albums

    # -------------------------------------------------
    # TRACKS
    # -------------------------------------------------

    def create_tracks(self, count, albums, artists, genres, instruments, labels):

        tracks = []

        for i in range(count):

            album = random.choice(albums)

            track = Track.objects.create(
                album=album,
                title=fake.sentence(nb_words=3),
                genre=random.choice(genres),
                instrument=random.choice(instruments),
                composer=random.choice(artists),
                singer=random.choice(artists),
                track_number=random.randint(1, 12),
                duration_ms=random.randint(60000, 500000),
                description=fake.text(100),
                label=random.choice(labels),
                audio_file="dummy.mp3",
            )

            tracks.append(track)

        return tracks

    # -------------------------------------------------
    # PLAYLISTS
    # -------------------------------------------------

    def create_playlists(self, users, tracks):

        playlists = []

        for user in users:

            for _ in range(random.randint(1, 3)):

                playlist = Playlist.objects.create(
                    owner=user,
                    title=fake.sentence(nb_words=3),
                    description=fake.text(100),
                    is_public=True
                )

                sample_tracks = random.sample(tracks, random.randint(5, 15))

                for order, track in enumerate(sample_tracks):

                    PlaylistTrack.objects.create(
                        playlist=playlist,
                        track=track,
                        order=order
                    )

                playlists.append(playlist)

        return playlists

    # -------------------------------------------------
    # COMMENTS
    # -------------------------------------------------

    def create_comments(self, users, albums):

        for _ in range(200):

            Comment.objects.create(
                user=random.choice(users),
                album=random.choice(albums),
                body=fake.sentence(),
                is_approved=True
            )

    # -------------------------------------------------
    # LIKES
    # -------------------------------------------------

    def create_likes(self, users, artists, albums, tracks, playlists):

        models = artists + albums + tracks + playlists

        for _ in range(300):

            obj = random.choice(models)

            Like.objects.get_or_create(
                user=random.choice(users),
                content_type=ContentType.objects.get_for_model(obj),
                object_id=obj.id
            )

    # -------------------------------------------------
    # FOLLOWS
    # -------------------------------------------------

    def create_follows(self, users, artists, playlists):

        models = artists + playlists

        for _ in range(150):

            obj = random.choice(models)

            Follow.objects.get_or_create(
                user=random.choice(users),
                content_type=ContentType.objects.get_for_model(obj),
                object_id=obj.id
            )

    # -------------------------------------------------
    # DISCOUNTS
    # -------------------------------------------------

    def create_discounts(self):

        for i in range(5):

            Discount.objects.create(
                name=f"Test Discount {i}",
                code=f"TEST{i}",
                discount_type="percentage",
                discount_value=random.randint(5, 30),
                start_date=timezone.now(),
                end_date=timezone.now() + timezone.timedelta(days=30),
                max_uses=100,
                max_uses_per_user=2,
                is_active=True
            )
