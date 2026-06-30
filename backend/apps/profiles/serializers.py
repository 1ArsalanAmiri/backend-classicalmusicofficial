from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from apps.interactions.models import Like, Follow
from django.contrib.contenttypes.models import ContentType
from apps.music.models import Artist, Album, Track, PlayHistory , ArtistRole
from apps.profiles.models import UserProfile
from django.db.models import Q
import jdatetime
from apps.music.serializers import TrackSerializer
from apps.playlists.models import Playlist
from apps.music.serializers import AlbumListSerializer


User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    current_subscription_name = serializers.SerializerMethodField()
    subscription_start_date = serializers.SerializerMethodField()
    subscription_end_date = serializers.SerializerMethodField()
    days_until_expiration = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()

    liked_albums_count = serializers.SerializerMethodField()
    followed_artists_count = serializers.SerializerMethodField()
    liked_songs_count = serializers.SerializerMethodField()
    saved_playlists_count = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'phone_number', 'first_name', 'last_name', 'email',
            'profile_image', 'joined_date',
            'current_subscription_name', 'subscription_start_date',
            'subscription_end_date', 'days_until_expiration',
            'subscription_status',

            'liked_albums_count', 'followed_artists_count',
            'liked_songs_count', 'saved_playlists_count'
        ]


    def get_latest_active_subscription_history(self, obj):
        today = jdatetime.date.today()
        # Fetch history entries that are either active or will start soon
        return obj.subscriptionhistory_set.filter(
            Q(end_date__gte=today) | Q(start_date__gte=today)
        ).order_by('-start_date').select_related('subscription').first()

    def get_current_subscription_name(self, obj):
        history = self.get_latest_active_subscription_history(obj)
        if history and history.subscription:
            return history.subscription.name
        return None

    def get_subscription_start_date(self, obj):
        history = self.get_latest_active_subscription_history(obj)
        if history and history.start_date:
            # Convert jdatetime.date to string YYYY-MM-DD
            return history.start_date.strftime('%Y-%m-%d')
        return None

    def get_subscription_end_date(self, obj):
        history = self.get_latest_active_subscription_history(obj)
        if history and history.end_date:
            # Convert jdatetime.date to string YYYY-MM-DD
            return history.end_date.strftime('%Y-%m-%d')
        return None

    def get_days_until_expiration(self, obj):
        history = self.get_latest_active_subscription_history(obj)
        if not history or not history.end_date:
            return 0

        today = jdatetime.date.today()
        end_date = history.end_date

        if end_date <= today:
            return 0

        diff = end_date - today
        return diff.days

    def get_subscription_status(self, obj):
        history = self.get_latest_active_subscription_history(obj)
        if not history:
            return "No active subscription"

        today = jdatetime.date.today()
        end_date = history.end_date

        if end_date is None:
            return "Active (Unlimited)"

        if history.start_date > today:
            return "Upcoming"
        elif end_date >= today:
            return "Active"
        else: # end_date < today
            return "Expired"

    def get_liked_albums_count(self, obj):
        album_ct = ContentType.objects.get_for_model(Album)
        return Like.objects.filter(user=obj.user, content_type=album_ct).count()

    def get_followed_artists_count(self, obj):
        artist_ct = ContentType.objects.get_for_model(Artist)
        return Follow.objects.filter(user=obj.user, content_type=artist_ct).count()

    def get_liked_songs_count(self, obj):
        track_ct = ContentType.objects.get_for_model(Track)
        return Like.objects.filter(user=obj.user, content_type=track_ct).count()

    def get_saved_playlists_count(self, obj):
        playlist_ct = ContentType.objects.get_for_model(Playlist)
        return Like.objects.filter(user=obj.user, content_type=playlist_ct).count()


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    email = serializers.EmailField(source='user.email', required=False)

    class Meta:
        model = UserProfile
        fields = ['profile_image', 'first_name', 'last_name', 'email']

    def validate_email(self, value):
        request = self.context.get('request')
        user = request.user if request else None

        if user and User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError(_("این ایمیل از قبل در سیستم ثبت شده است."))
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user
        user_needs_update = False

        if 'first_name' in user_data:
            user.first_name = user_data['first_name']
            user_needs_update = True
        if 'last_name' in user_data:
            user.last_name = user_data['last_name']
            user_needs_update = True
        if 'email' in user_data:
            user.email = user_data['email']
            user_needs_update = True

        if user_needs_update:
            user.save()

        return super().update(instance, validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        user = self.context['request'].user
        new_password = attrs.get('new_password')
        new_password_confirm = attrs.get('new_password_confirm')
        old_password = attrs.get('old_password')

        # بررسی تطابق رمز جدید و تکرار آن
        if new_password != new_password_confirm:
            raise serializers.ValidationError(
                {"new_password_confirm": _("رمز عبور جدید و تکرار آن مطابقت ندارند.")}
            )

        # بررسی رمز قبلی اگر کاربر رمز دارد
        if user.has_usable_password():
            if not old_password:
                raise serializers.ValidationError(
                    {"old_password": _("وارد کردن رمز عبور فعلی الزامی است.")}
                )

            if not user.check_password(old_password):
                raise serializers.ValidationError(
                    {"old_password": _("رمز عبور فعلی اشتباه است.")}
                )

        # جلوگیری از ثبت رمز جدید دقیقاً مشابه رمز قدیم
        if old_password and old_password == new_password:
            raise serializers.ValidationError(
                {"new_password": _("رمز عبور جدید نمی‌تواند با رمز فعلی یکسان باشد.")}
            )

        return attrs


class ArtistListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = ['slug', 'name', 'image']


class ArtistDetailSerializer(serializers.ModelSerializer):
    albums = serializers.SerializerMethodField()
    related_artists = ArtistListSerializer(many=True, read_only=True)

    class Meta:
        model = Artist
        fields = [
            'slug', 'name', 'biography', 'image', 'birth_year', 'death_year',
            'albums','related_artists'
        ]

    def get_albums(self, obj):
        albums = obj.main_albums.all()
        return AlbumListSerializer(albums, many=True, context=self.context).data


class PlayHistorySerializer(serializers.ModelSerializer):
    track = TrackSerializer(read_only=True)

    class Meta:
        model = PlayHistory
        fields = ['id', 'track', 'last_played_at', 'play_count']
