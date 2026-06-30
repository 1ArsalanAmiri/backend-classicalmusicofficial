import django_filters
from django.db.models import Q
from apps.music.models import Album, Track


class AlbumFilter(django_filters.FilterSet):
    era = django_filters.CharFilter(
        field_name='main_artists__era',
        lookup_expr='iexact',
        help_text="فیلتر بر اساس دوره زمانی (Era) آهنگساز/آرتیست"
    )
    release_year_min = django_filters.NumberFilter(
        field_name='release_year',
        lookup_expr='gte',
        help_text="از سال انتشار (>=)"
    )
    release_year_max = django_filters.NumberFilter(
        field_name='release_year',
        lookup_expr='lte',
        help_text="تا سال انتشار (<=)"
    )
    label = django_filters.CharFilter(field_name='label__slug')

    class Meta:
        model = Album
        fields = ['status', 'label']


class TrackFilter(django_filters.FilterSet):
    label = django_filters.CharFilter(field_name='label__slug')
    genre = django_filters.CharFilter(field_name='genre__slug')
    instrument = django_filters.CharFilter(field_name='instrument__slug')
    album = django_filters.CharFilter(field_name='album__slug')

    era = django_filters.CharFilter(
        method='filter_by_era',
        help_text="فیلتر بر اساس دوره زمانی (رنسانس، باروک و ...)"
    )

    class Meta:
        model = Track
        fields = ['genre', 'instrument', 'label', 'album']

    def filter_by_era(self, queryset, name, value):
        return queryset.filter(
            Q(artists__era__iexact=value) | Q(album__main_artists__era__iexact=value)
        ).distinct()
