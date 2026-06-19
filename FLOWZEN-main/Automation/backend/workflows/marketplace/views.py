"""
Marketplace API Views
Template discovery, purchase, and management
"""

from rest_framework import status, generics, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Avg, Count
from django.shortcuts import get_object_or_404
import logging

from .models import (
    WorkflowTemplate, TemplateRating, TemplateDownload, 
    DeveloperProfile, MarketplaceTransaction, TemplateCollection
)
from .serializers import (
    WorkflowTemplateSerializer, TemplateRatingSerializer,
    DeveloperProfileSerializer, TemplateCollectionSerializer
)
from ..security.rbac import rbac_manager, Permission

logger = logging.getLogger(__name__)

class MarketplacePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class TemplateListView(generics.ListAPIView):
    """List marketplace templates with filtering and search"""
    serializer_class = WorkflowTemplateSerializer
    pagination_class = MarketplacePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['created_at', 'rating_average', 'download_count', 'name']
    ordering = ['-rating_average', '-download_count']
    
    def get_queryset(self):
        queryset = WorkflowTemplate.objects.filter(status='approved')
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by pricing
        pricing = self.request.query_params.get('pricing')
        if pricing:
            queryset = queryset.filter(pricing_model=pricing)
        
        # Filter by tags
        tags = self.request.query_params.getlist('tags')
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__contains=[tag])
        
        # Filter by rating
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            try:
                queryset = queryset.filter(rating_average__gte=float(min_rating))
            except ValueError:
                pass
        
        return queryset.select_related('author').prefetch_related('ratings')

@api_view(['GET'])
def template_detail(request, template_id):
    """Get detailed template information"""
    try:
        template = get_object_or_404(WorkflowTemplate, id=template_id, status='approved')
        
        # Check if user has downloaded this template
        has_downloaded = False
        if request.user.is_authenticated:
            has_downloaded = TemplateDownload.objects.filter(
                template=template,
                user=request.user
            ).exists()
        
        # Get user's rating if exists
        user_rating = None
        if request.user.is_authenticated:
            try:
                rating = TemplateRating.objects.get(template=template, user=request.user)
                user_rating = TemplateRatingSerializer(rating).data
            except TemplateRating.DoesNotExist:
                pass
        
        # Get recent ratings
        recent_ratings = TemplateRating.objects.filter(
            template=template
        ).order_by('-created_at')[:5]
        
        serializer = WorkflowTemplateSerializer(template)
        data = serializer.data
        data.update({
            'has_downloaded': has_downloaded,
            'user_rating': user_rating,
            'recent_ratings': TemplateRatingSerializer(recent_ratings, many=True).data
        })
        
        return Response(data)
        
    except Exception as e:
        logger.error(f"Template detail error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def download_template(request, template_id):
    """Download a template"""
    try:
        template = get_object_or_404(WorkflowTemplate, id=template_id, status='approved')
        
        # Check if it's a paid template and user has purchased it
        if template.pricing_model == 'paid' and template.price > 0:
            has_purchased = MarketplaceTransaction.objects.filter(
                buyer=request.user,
                template=template,
                transaction_type='purchase',
                status='completed'
            ).exists()
            
            if not has_purchased:
                return Response(
                    {'error': 'Template must be purchased before download'}, 
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )
        
        # Record download
        download, created = TemplateDownload.objects.get_or_create(
            template=template,
            user=request.user,
            organization=request.tenant,
            defaults={'downloaded_at': timezone.now()}
        )
        
        if created:
            # Increment download count
            template.download_count += 1
            template.save(update_fields=['download_count'])
        
        # Log the download
        rbac_manager.log_security_action(
            user=request.user,
            organization=request.tenant,
            action='download_template',
            resource_type='template',
            resource_id=str(template.id),
            success=True,
            details={
                'template_name': template.name,
                'template_version': template.version,
                'pricing_model': template.pricing_model
            },
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'success': True,
            'template': WorkflowTemplateSerializer(template).data,
            'download_id': download.id
        })
        
    except Exception as e:
        logger.error(f"Template download error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rate_template(request, template_id):
    """Rate and review a template"""
    try:
        template = get_object_or_404(WorkflowTemplate, id=template_id, status='approved')
        
        # Check if user has downloaded the template
        if not TemplateDownload.objects.filter(template=template, user=request.user).exists():
            return Response(
                {'error': 'You must download the template before rating it'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rating_value = request.data.get('rating')
        review_text = request.data.get('review', '')
        
        if not rating_value or not (1 <= int(rating_value) <= 5):
            return Response(
                {'error': 'Rating must be between 1 and 5'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update rating
        rating, created = TemplateRating.objects.update_or_create(
            template=template,
            user=request.user,
            defaults={
                'rating': int(rating_value),
                'review': review_text
            }
        )
        
        # Recalculate template rating average
        avg_rating = TemplateRating.objects.filter(template=template).aggregate(
            avg=Avg('rating')
        )['avg'] or 0
        
        rating_count = TemplateRating.objects.filter(template=template).count()
        
        template.rating_average = round(avg_rating, 2)
        template.rating_count = rating_count
        template.save(update_fields=['rating_average', 'rating_count'])
        
        return Response({
            'success': True,
            'rating': TemplateRatingSerializer(rating).data,
            'template_rating_average': template.rating_average,
            'template_rating_count': template.rating_count
        })
        
    except Exception as e:
        logger.error(f"Template rating error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def publish_template(request):
    """Publish a new template to marketplace"""
    try:
        # Check if user can publish templates
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.WORKFLOW_PUBLISH
        ):
            return Response(
                {'error': 'Insufficient permissions to publish templates'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate required fields
        required_fields = ['name', 'description', 'category', 'workflow_definition']
        for field in required_fields:
            if not request.data.get(field):
                return Response(
                    {'error': f'{field} is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create template
        template_data = {
            'name': request.data['name'],
            'description': request.data['description'],
            'long_description': request.data.get('long_description', ''),
            'category': request.data['category'],
            'tags': request.data.get('tags', []),
            'workflow_definition': request.data['workflow_definition'],
            'author': request.user,
            'organization': request.tenant,
            'version': request.data.get('version', '1.0.0'),
            'pricing_model': request.data.get('pricing_model', 'free'),
            'price': request.data.get('price', 0.00),
            'min_platform_version': request.data.get('min_platform_version', '1.0.0'),
            'required_integrations': request.data.get('required_integrations', []),
            'status': 'pending'  # Requires approval
        }
        
        template = WorkflowTemplate.objects.create(**template_data)
        
        # Create or update developer profile
        developer_profile, created = DeveloperProfile.objects.get_or_create(
            user=request.user,
            defaults={
                'display_name': request.user.get_full_name() or request.user.username,
                'template_count': 1
            }
        )
        
        if not created:
            developer_profile.template_count += 1
            developer_profile.save()
        
        # Log the publication
        rbac_manager.log_security_action(
            user=request.user,
            organization=request.tenant,
            action='publish_template',
            resource_type='template',
            resource_id=str(template.id),
            success=True,
            details={
                'template_name': template.name,
                'category': template.category,
                'pricing_model': template.pricing_model
            },
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'success': True,
            'template': WorkflowTemplateSerializer(template).data,
            'message': 'Template submitted for review'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Template publication error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def marketplace_stats(request):
    """Get marketplace statistics"""
    try:
        stats = {
            'total_templates': WorkflowTemplate.objects.filter(status='approved').count(),
            'total_downloads': TemplateDownload.objects.count(),
            'categories': WorkflowTemplate.objects.filter(status='approved').values('category').annotate(
                count=Count('id')
            ).order_by('-count'),
            'top_templates': WorkflowTemplate.objects.filter(status='approved').order_by(
                '-rating_average', '-download_count'
            )[:10].values('id', 'name', 'rating_average', 'download_count'),
            'featured_collections': TemplateCollection.objects.filter(
                is_featured=True, is_public=True
            )[:5].values('id', 'name', 'description')
        }
        
        return Response(stats)
        
    except Exception as e:
        logger.error(f"Marketplace stats error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_templates(request):
    """Get user's published templates"""
    try:
        templates = WorkflowTemplate.objects.filter(author=request.user).order_by('-created_at')
        
        # Add pagination
        paginator = MarketplacePagination()
        page = paginator.paginate_queryset(templates, request)
        
        if page is not None:
            serializer = WorkflowTemplateSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = WorkflowTemplateSerializer(templates, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"My templates error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_downloads(request):
    """Get user's downloaded templates"""
    try:
        downloads = TemplateDownload.objects.filter(
            user=request.user
        ).select_related('template').order_by('-downloaded_at')
        
        # Add pagination
        paginator = MarketplacePagination()
        page = paginator.paginate_queryset(downloads, request)
        
        templates_data = []
        downloads_list = page if page is not None else downloads
        
        for download in downloads_list:
            template_data = WorkflowTemplateSerializer(download.template).data
            template_data['downloaded_at'] = download.downloaded_at
            templates_data.append(template_data)
        
        if page is not None:
            return paginator.get_paginated_response(templates_data)
        
        return Response(templates_data)
        
    except Exception as e:
        logger.error(f"My downloads error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )