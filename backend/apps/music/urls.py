from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ArtistViewSet, AlbumViewSet, TrackViewSet, GenreViewSet, InstrumentViewSet, EraListView, \
    AlbumBatchUploadAPIView, LabelViewSet, GenreDetailWithContentAPIView, \
    InstrumentDetailWithContentAPIView, EditorialPlaylistViewSet, LandingPageView
from apps.common.search_views import GlobalSearchView

router = DefaultRouter()

router.register(r'artists', ArtistViewSet, basename='artist')
router.register(r'albums', AlbumViewSet, basename='album')
router.register(r'editorial-playlists', EditorialPlaylistViewSet, basename='editorial-playlist')
router.register(r'tracks', TrackViewSet, basename='track')
router.register(r'genres', GenreViewSet, basename='genre')
router.register(r'instruments', InstrumentViewSet, basename='instrument')
router.register(r'labels', LabelViewSet, basename='label')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('eras/', EraListView.as_view(), name='era-list'),
    path('api/v1/albums/<int:album_id>/batch-upload/', AlbumBatchUploadAPIView.as_view(), name='api-album-batch-upload'),
    path('search/', GlobalSearchView.as_view(), name='global-search'),
    path('api/v1/genres/<slug:slug>/content/', GenreDetailWithContentAPIView.as_view(), name='genre-content'),
    path('api/v1/instruments/<slug:slug>/content/', InstrumentDetailWithContentAPIView.as_view(), name='instrument-content'),
    path('api/v1/landing/', LandingPageView.as_view(), name='landing-page'),

]