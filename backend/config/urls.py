from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


urlpatterns = [

    path("admin/", admin.site.urls),

    path('_nested_admin/', include('nested_admin.urls')),

    path('schema/', SpectacularAPIView.as_view(), name='schema'),

    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path("accounts/" , include("apps.accounts.urls") , name="accounts"),

    path("profile/", include("apps.profiles.urls"), name="profile"),

]
