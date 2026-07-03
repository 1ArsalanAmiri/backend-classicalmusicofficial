from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf import settings
from django.conf.urls.static import static


def trigger_error(request):
    division_by_zero = 1 / 0

def health_check(request):
    return HttpResponse("OK")

urlpatterns = [

    path("admin/", admin.site.urls),

    path('health/', health_check),

    path('_nested_admin/', include('nested_admin.urls')),

    path('schema/', SpectacularAPIView.as_view(), name='schema'),

    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path("accounts/" , include("apps.accounts.urls") , name="accounts"),

    path("profile/", include("apps.profiles.urls"), name="profile"),

    path("music/", include("apps.music.urls"), name="music"),

    path("playlist/" , include("apps.playlists.urls") , name="playlist"),

    path("payments/", include("apps.payments.urls") , name="payment"),

    path("videos/",include("apps.videos.urls") , name="videos"),

    # path('sentry-debug/', trigger_error),

]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
                      path('__debug__/', include(debug_toolbar.urls)),
                  ] + urlpatterns

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
