import django_filters
from apps.music.models import Album , Track


class AlbumFilter(django_filters.FilterSet):
    composer_era = django_filters.CharFilter(field_name='composer__era',lookup_expr='iexact',help_text="Filter By Era")
    release_year_min = django_filters.NumberFilter(field_name='release_date',lookup_expr='year__gte',help_text="Filter By Year(Since This Year)")
    release_year_max = django_filters.NumberFilter(field_name='release_date',lookup_expr='year__lte',help_text="Filter By Year(Until This Year)")
    label = django_filters.CharFilter(field_name='label__slug')

    class Meta:
        model = Album
        fields = ['composer', 'conductor', 'orchestra', 'soloist' , 'label']


class TrackFilter(django_filters.FilterSet):
    label = django_filters.CharFilter(field_name='label__slug')

    class Meta:
        model = Track
        fields = ['genre', 'label']


