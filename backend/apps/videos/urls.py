from rest_framework.routers import DefaultRouter
from .views import VideoViewSet

app_name = 'videos'

router = DefaultRouter()
router.register(r'videos', VideoViewSet, basename='video')

urlpatterns = router.urls
