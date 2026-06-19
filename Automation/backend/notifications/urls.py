from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, NotificationSettingsViewSet

router = DefaultRouter()
router.register(r'list', NotificationViewSet, basename='notification')
router.register(r'settings', NotificationSettingsViewSet, basename='notification-settings')

urlpatterns = [
    path('', include(router.urls)),
]
