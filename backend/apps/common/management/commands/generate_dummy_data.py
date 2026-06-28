import random
from faker import Faker
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.text import slugify
from django.db import IntegrityError

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
        albums = self.create_albums(20, artists, labels)

        # We need to make sure we have albums before creating tracks
        if not albums:
            self.stdout.write(self.style.WARNING("No albums found or created, skipping track generation."))
            tracks = []
        else:
            tracks = self.create_tracks(50, albums, artists, genres, instruments)

        if users and tracks:
            playlists = self.create_playlists(users, tracks)
        else:
            self.stdout.write(self.style.WARNING("Skipping playlist generation due to missing users or tracks."))
            playlists = []

        if users and albums:
            self.create_comments(users, albums)

        likeable_objects = artists + albums + tracks + (playlists if playlists else [])
        if users and likeable_objects:
            self.create_likes(users, likeable_objects)

        followable_objects = artists + (playlists if playlists else [])
        if users and followable_objects:
            self.create_follows(users, followable_objects)

        self.create_discounts()

        self.stdout.write(self.style.SUCCESS("Dummy data generation process finished ✅"))

    def create_users(self, count):
        users = []
        for i in range(count):
            username = f'user{i}'
            email = f'user{i}@example.com'
            user, created = CustomUser.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': fake.first_name(),
                    'last_name': fake.last_name(),
                    'is_active': True
                }
            )
            if created:
                user.set_password('password12345')
                user.save()
            UserProfile.objects.get_or_create(user=user)
            users.append(user)
        self.stdout.write(self.style.SUCCESS(f'Successfully created/verified {len(users)} users.'))
        return users

    def create_genres(self):
        names = ["Classical", "Baroque", "Romantic", "Opera", "Symphony", "Chamber Music"]
        genres = []
        for name in names:
            genre, _ = Genre.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name)}
            )
            genres.append(genre)
        self.stdout.write(self.style.SUCCESS(f'Successfully created/verified {len(genres)} genres.'))
        return genres

    def create_instruments(self):
        names = ["Piano", "Violin", "Cello", "Flute", "Clarinet", "Harp"]
        instruments = []
        for name in names:
            inst, _ = Instrument.objects.get_or_create(name=name, defaults={"slug": slugify(name)})
            instruments.append(inst)
        self.stdout.write(self.style.SUCCESS(f'Successfully created/verified {len(instruments)} instruments.'))
        return instruments

    def create_labels(self, count):
        labels = []
        for _ in range(count):
            name = fake.company()
            label, _ = Label.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name), "country": fake.country()}
            )
            labels.append(label)
        self.stdout.write(self.style.SUCCESS(f'Successfully created/verified {len(labels)} labels.'))
        return labels

    def create_artists(self, count):
        artists = []
        for _ in range(count):
            name = fake.name()
            try:
                artist, _ = Artist.objects.get_or_create(
                    name=name,
                    defaults={
                        "slug": slugify(name),
                        "country": fake.country(),
                        "biography": fake.text(max_nb_chars=300),
                        "artist_type": random.choice(["person", "ensemble", "orchestra"])
                    }
                )
                artists.append(artist)
            except IntegrityError:
                # In case a slug collision happens with a different name
                continue
        self.stdout.write(self.style.SUCCESS(f'Successfully created/verified {len(artists)} artists.'))
        return artists

    def create_albums(self, count, artists, labels):
        albums = []
        if not artists or not labels:
            self.stdout.write(self.style.WARNING("Cannot create albums without artists and labels."))
            return []
        for _ in range(count):
            album_title = fake.sentence(nb_words=3)
            base_slug = slugify(album_title)
            album_slug = base_slug
            counter = 1
            while Album.objects.filter(slug=album_slug).exists():
                album_slug = f"{base_slug}-{counter}"
                counter += 1

            album = Album.objects.create(
                title=album_title,
                slug=album_slug,
                artist=random.choice(artists),
                label=random.choice(labels),
                release_date=fake.date_between("-30y", "today"),
                # Optional fields
                composer=fake.name(),
                conductor=fake.name(),
                orchestra=fake.company(),
                soloist=fake.name(),
                ensemble=fake.company(),
            )
            albums.append(album)
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(albums)} albums.'))
        return albums

    def create_tracks(self, count, albums, artists, genres, instruments):
        processed_tracks = []
        for i in range(count):
            album = random.choice(albums)
            last_track = Track.objects.filter(album=album).order_by('-track_number').first()
            next_track_number = (last_track.track_number + 1) if last_track else 1

            track_title = f'Dummy Track {i} {random.randint(1000, 9999)}'

            # --- Dynamically build defaults to avoid FieldError ---
            defaults = {'title': track_title}
            if hasattr(Track, 'slug'):
                defaults['slug'] = slugify(track_title)
            if hasattr(Track, 'duration'):
                defaults['duration'] = random.randint(120, 600)
            if hasattr(Track, 'audio_file'):
                defaults['audio_file'] = 'path/to/dummy.mp3'
            # --- End of dynamic build ---

            track, created = Track.objects.get_or_create(
                album=album,
                track_number=next_track_number,
                defaults=defaults
            )

            if created:
                # Dynamically set relationships
                if hasattr(track, 'artist') and not hasattr(track, 'artists'):
                    track.artist = random.choice(artists)
                if hasattr(track, 'artists') and hasattr(track.artists, 'set'):
                    track.artists.set(random.sample(list(artists), k=random.randint(1, min(3, len(artists)))))
                if hasattr(track, 'genres') and hasattr(track.genres, 'set'):
                    track.genres.set(random.sample(list(genres), k=random.randint(1, min(2, len(genres)))))
                if instruments and hasattr(track, 'instruments') and hasattr(track.instruments, 'set'):
                    track.instruments.set(
                        random.sample(list(instruments), k=random.randint(0, min(2, len(instruments)))))
                track.save()

            processed_tracks.append(track)
        self.stdout.write(self.style.SUCCESS(f'Successfully processed {len(processed_tracks)} tracks.'))
        return processed_tracks

    def create_playlists(self, users, tracks):
        playlists = []
        for user in users:
            for _ in range(random.randint(1, 3)):
                playlist = Playlist.objects.create(
                    owner=user, title=fake.sentence(nb_words=3), description=fake.text(100), is_public=True
                )
                sample_tracks = random.sample(tracks, k=random.randint(1, min(15, len(tracks))))
                for order, track in enumerate(sample_tracks, 1):
                    PlaylistTrack.objects.create(playlist=playlist, track=track, order=order)
                playlists.append(playlist)
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(playlists)} playlists.'))
        return playlists

    def create_comments(self, users, albums):
        comments_count = 0
        for _ in range(50):
            Comment.objects.create(
                user=random.choice(users), album=random.choice(albums), body=fake.sentence(), is_approved=True
            )
            comments_count += 1
        self.stdout.write(self.style.SUCCESS(f'Successfully created {comments_count} comments.'))

    def create_likes(self, users, models):
        likes_count = 0
        for _ in range(100):
            obj = random.choice(models)
            _, created = Like.objects.get_or_create(
                user=random.choice(users),
                content_type=ContentType.objects.get_for_model(obj),
                object_id=obj.id
            )
            if created:
                likes_count += 1
        self.stdout.write(self.style.SUCCESS(f'Successfully created {likes_count} new likes.'))

    def create_follows(self, users, models):
        follows_count = 0
        for _ in range(50):
            obj = random.choice(models)
            _, created = Follow.objects.get_or_create(
                user=random.choice(users),
                content_type=ContentType.objects.get_for_model(obj),
                object_id=obj.id
            )
            if created:
                follows_count += 1
        self.stdout.write(self.style.SUCCESS(f'Successfully created {follows_count} new follows.'))

    def create_discounts(self):
        for i in range(5):
            Discount.objects.get_or_create(
                code=f"TEST{i}",
                defaults={
                    "name": f"Test Discount {i}",
                    "discount_type": "percentage",
                    "discount_value": random.randint(5, 30),
                    "start_date": timezone.now(),
                    "end_date": timezone.now() + timezone.timedelta(days=30),
                    "max_uses": 100,
                    "max_uses_per_user": 2,
                    "is_active": True
                }
            )
        self.stdout.write(self.style.SUCCESS('Successfully created/verified 5 discounts.'))
