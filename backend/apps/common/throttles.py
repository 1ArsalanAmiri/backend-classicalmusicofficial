from rest_framework.throttling import UserRateThrottle

class ZipGenerationRateThrottle(UserRateThrottle):
    scope = 'zip_generation'
