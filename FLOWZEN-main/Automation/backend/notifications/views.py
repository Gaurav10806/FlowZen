from rest_framework import serializers, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Notification, NotificationSettings

# --- SERIALIZERS ---
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['user', 'created_at']

class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = '__all__'
        read_only_fields = ['user']

# --- VIEWS ---
class NotificationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response({'status': 'marked all read'})

    @action(detail=False, methods=['post'])
    def clear_all(self, request):
        self.get_queryset().delete()
        return Response({'status': 'cleared all'})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count})
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        notifications = self.get_queryset().order_by('-created_at')[:5]
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked read'})

class NotificationSettingsViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSettingsSerializer
    
    def get_queryset(self):
        # Ensure user has settings
        if not hasattr(self.request.user, 'notification_settings'):
            NotificationSettings.objects.create(user=self.request.user)
        return NotificationSettings.objects.filter(user=self.request.user)
    
    def list(self, request, *args, **kwargs):
        settings, _ = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(settings)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # Handle update via Post/Put on list endpoint effectively
        settings, _ = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
