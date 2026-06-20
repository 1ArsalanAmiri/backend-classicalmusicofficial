import random
import uuid
from uuid import uuid4
from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from faker import Faker
from django.utils.text import slugify

# Import Models
from apps.music.models import (
    Genre, Instrument, Label, Artist, Album, Track, PlayHistory,
    ArtistType, EraChoices
)
from apps.common.models import PublishStatus
from apps.profiles.models import UserProfile, ArtistProfile
from apps.payments.models import Payment, DiscountUsage

User = get_user_model()


# ==========================================
# Helpers for Mock Files
# ==========================================
def get_mock_image():
    gif_data = b'GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;'
    return ContentFile(gif_data, name=f"mock_image_{uuid4().hex[:8]}.jpg")


def get_mock_audio():
    audio_data = b'ID3 DUMMY AUDIO DATA'
    return ContentFile(audio_data, name=f"mock_audio_{uuid4().hex[:8]}.mp3")


def get_valid_iran_phone():
    return f"+989{random.randint(10, 39)}{random.randint(1000000, 9999999)}"


# ==========================================
# Classical Music Metadata Generators
# ==========================================
CLASSICAL_LABELS = [
    'Deutsche Grammophon', 'Decca Classics', 'Sony Classical',
    'Warner Classics', 'Naxos Records', 'Harmonia Mundi',
    'ECM New Series', 'Pentatone', 'Chandos Records', 'Hyperion'
]

COMPOSERS = [
    'Johann Sebastian Bach', 'Wolfgang Amadeus Mozart', 'Ludwig van Beethoven',
    'Pyotr Ilyich Tchaikovsky', 'Frédéric Chopin', 'Johannes Brahms',
    'Antonio Vivaldi', 'Claude Debussy', 'Franz Schubert', 'Gustav Mahler',
    'Richard Wagner', 'Igor Stravinsky', 'Giuseppe Verdi', 'Sergei Rachmaninoff'
]

PERFORMERS_ORCHESTRAS = [
    'Berlin Philharmonic', 'Vienna Philharmonic', 'London Symphony Orchestra',
    'Herbert von Karajan', 'Martha Argerich', 'Yo-Yo Ma', 'Leonard Bernstein',
    'Itzhak Perlman', 'Glenn Gould', 'Maria Callas', 'Arthur Rubinstein',
    'Chicago Symphony Orchestra', 'Royal Concertgebouw Orchestra'
]

FORMS = ['Symphony', 'Concerto', 'Sonata', 'String Quartet', 'Prelude', 'Fugue', 'Etude', 'Waltz', 'Nocturne']
KEYS = ['C Major', 'C Minor', 'D Major', 'D Minor', 'E-flat Major', 'E Minor', 'F Major', 'F Minor', 'G Major',
        'G Minor', 'A Major', 'A Minor', 'B-flat Major', 'B Minor']
MOVEMENTS = ['I. Allegro', 'II. Adagio', 'III. Scherzo', 'IV. Presto', 'I. Andante', 'II. Largo', 'III. Rondo',
             'I. Moderato']


def generate_classical_title(is_track=False):
    form = random.choice(FORMS)
    number = random.randint(1, 41)
    key = random.choice(KEYS)
    opus = random.randint(1, 130)

    base_title = f"{form} No. {number} in {key}, Op. {opus}"

    if is_track:
        movement = random.choice(MOVEMENTS)
        return f"{base_title}: {movement}"
    return base_title


class Command(BaseCommand):
    help = 'Generate specialized Classical Music dummy data (like Apple Music Classical).'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=50, help='Number of users to create')
        parser.add_argument('--albums', type=int, default=100, help='Number of albums to create')
        parser.add_argument('--tracks-per-album', type=int, default=4,
                            help='Avg tracks per album (usually 3-4 for a Symphony/Concerto)')
        parser.add_argument('--clear', action='store_true', help='Clear existing data before generating')

    def handle(self, *args, **kwargs):
        fake_fa = Faker('fa_IR')
        fake_en = Faker('en_US')

        num_users = kwargs['users']
        num_albums = kwargs['albums']
        tracks_per_album = kwargs['tracks_per_album']
        clear_db = kwargs['clear']

        if clear_db:
            self.stdout.write(self.style.WARNING("Clearing old data..."))
            with transaction.atomic():
                # Fix: ابتدا رکوردهای مالی که مانع حذف یوزرها می‌شوند پاک می‌شوند
                Payment.objects.filter(user__is_superuser=False).delete()
                DiscountUsage.objects.filter(user__is_superuser=False).delete()

                # سپس سایر دیتاها به ترتیب از فرزند به والد پاک می‌شوند
                PlayHistory.objects.all().delete()
                Track.objects.all().delete()
                Album.objects.all().delete()
                Artist.objects.all().delete()
                Label.objects.all().delete()
                Genre.objects.all().delete()
                Instrument.objects.all().delete()
                User.objects.exclude(is_superuser=True).delete()
            self.stdout.write(self.style.SUCCESS("Database cleared!"))

        with transaction.atomic():
            # 1. Base Data (Classical Genres & Instruments)
            self.stdout.write("Generating Classical Genres and Instruments...")
            genres = []
            classical_genres = ['Baroque', 'Classical Period', 'Romantic', '20th Century', 'Choral', 'Opera',
                                'Chamber Music', 'Symphonic']
            for name in classical_genres:
                genre, _ = Genre.objects.get_or_create(name=name)
                genres.append(genre)

            instruments = []
            classical_instruments = ['Piano', 'Violin', 'Cello', 'Viola', 'Flute', 'Oboe', 'Clarinet', 'Bassoon',
                                     'French Horn', 'Trumpet', 'Timpani', 'Harpsichord', 'Pipe Organ']
            for name in classical_instruments:
                instrument, _ = Instrument.objects.get_or_create(name=name)
                instruments.append(instrument)

            # 2. Classical Labels
            self.stdout.write("Generating Classical Labels...")
            labels = []
            for label_name in CLASSICAL_LABELS:
                label = Label.objects.create(
                    name=label_name,
                    country=fake_en.country(),
                    website=fake_en.url(),
                    description=fake_en.text(),
                    logo=get_mock_image()
                )
                labels.append(label)

            # 3. Users & Profiles
            self.stdout.write(f"Generating {num_users} Users...")
            users = []
            for _ in range(num_users):
                try:
                    user = User.objects.create_user(
                        phone_number=get_valid_iran_phone(),
                        password="password123",
                        first_name=fake_fa.first_name(),
                        last_name=fake_fa.last_name(),
                        email=fake_en.email()
                    )
                    UserProfile.objects.get_or_create(
                        user=user,
                        defaults={'profile_image': get_mock_image()}
                    )
                    users.append(user)
                except Exception:
                    pass

            # 4. Artists (Composers & Performers)
            self.stdout.write("Generating Classical Composers and Performers...")
            db_artists = []
            db_composers = []

            # Create Composers
            for name in COMPOSERS:
                artist = Artist.objects.create(
                    name=name,
                    country=fake_en.country(),
                    artist_type=ArtistType.COMPOSER if hasattr(ArtistType, 'COMPOSER') else
                    random.choice(ArtistType.choices)[0],
                    era=random.choice(EraChoices.choices)[0] if EraChoices.choices else None,
                    biography=fake_en.text(max_nb_chars=500),
                    image=get_mock_image()
                )
                ArtistProfile.objects.get_or_create(artist=artist)
                db_composers.append(artist)
                db_artists.append(artist)

            # Create Performers / Orchestras
            db_performers = []
            for name in PERFORMERS_ORCHESTRAS:
                artist = Artist.objects.create(
                    name=name,
                    country=fake_en.country(),
                    artist_type=random.choice(ArtistType.choices)[0],
                    biography=fake_en.text(max_nb_chars=500),
                    image=get_mock_image()
                )
                ArtistProfile.objects.get_or_create(artist=artist)
                db_performers.append(artist)
                db_artists.append(artist)

            # 5. Albums & Tracks
            self.stdout.write(f"Generating {num_albums} Classical Albums and Tracks...")
            all_tracks = []
            for _ in range(num_albums):
                composer = random.choice(db_composers)
                label = random.choice(labels)
                album_performer = random.choice(db_performers)

                album_title = f"{composer.name}: {generate_classical_title(is_track=False)}"

                album = Album.objects.create(
                    title=album_title,
                    composer=composer.name,
                    release_date=fake_en.date_between(start_date='-50y', end_date='today'),
                    status=PublishStatus.PUBLISHED,
                    label=label,
                    cover_image=get_mock_image()
                )

                album.artists.add(composer, album_performer)

                num_tracks = random.randint(max(1, tracks_per_album - 1), tracks_per_album + 1)
                for i in range(1, num_tracks + 1):
                    track_title = generate_classical_title(is_track=True)

                    # Fix: تولید slug به صورت دستی و کاملاً یکتا برای bulk_create
                    base_slug = slugify(track_title, allow_unicode=True) or f"track-{i}"
                    unique_slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"

                    track = Track(
                        album=album,
                        title=track_title,
                        slug=unique_slug,  # <-- جلوگیری از خطای IntegrityError
                        genre=random.choice(genres),
                        audio_file=get_mock_audio(),
                        composer=composer,
                        singer=album_performer,
                        duration_ms=random.randint(180000, 900000),
                        track_number=i,
                        status=PublishStatus.PUBLISHED,
                        instrument=random.choice(instruments),
                    )
                    all_tracks.append(track)

            # Bulk Create Tracks
            Track.objects.bulk_create(all_tracks, batch_size=200)
            created_tracks = list(Track.objects.all()[:1000])

            # 6. Play History
            if users and created_tracks:
                self.stdout.write("Generating Play History...")
                histories = []
                for user in random.sample(users, min(len(users), 20)):
                    listened_tracks = random.sample(created_tracks, min(len(created_tracks), 30))
                    for track in listened_tracks:
                        histories.append(PlayHistory(
                            user=user,
                            track=track,
                            play_count=random.randint(1, 20)
                        ))
                PlayHistory.objects.bulk_create(histories, batch_size=200)

            # 7. Related Artists
            self.stdout.write("Linking Related Artists...")
            for artist in db_artists:
                related = random.sample(db_artists, k=random.randint(0, 3))
                related = [r for r in related if r != artist]
                if related:
                    artist.related_artists.add(*related)

        self.stdout.write(self.style.SUCCESS(f"Successfully generated specialized Classical Music mock data!"))

