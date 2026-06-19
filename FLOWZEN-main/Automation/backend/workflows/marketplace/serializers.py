"""
Marketplace Serializers
"""

from rest_framework import serializers
from .models import (
    WorkflowTemplate, TemplateRating, DeveloperProfile, 
    TemplateCollection, MarketplaceTransaction
)

class DeveloperProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = DeveloperProfile
        fields = [
            'display_name', 'bio', 'website', 'github_username',
            'is_verified', 'total_downloads', 'average_rating',
            'template_count', 'username'
        ]

class TemplateRatingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = TemplateRating
        fields = ['rating', 'review', 'created_at', 'user_name', 'username']

class WorkflowTemplateSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    author_username = serializers.CharField(source='author.username', read_only=True)
    author_profile = DeveloperProfileSerializer(source='author.developer_profile', read_only=True)
    
    class Meta:
        model = WorkflowTemplate
        fields = [
            'id', 'name', 'description', 'long_description', 'category', 'tags',
            'workflow_definition', 'preview_image', 'screenshots', 'version',
            'pricing_model', 'price', 'download_count', 'rating_average', 'rating_count',
            'min_platform_version', 'required_integrations', 'created_at', 'updated_at',
            'author_name', 'author_username', 'author_profile'
        ]

class TemplateCollectionSerializer(serializers.ModelSerializer):
    template_count = serializers.SerializerMethodField()
    curator_name = serializers.CharField(source='curator.get_full_name', read_only=True)
    
    class Meta:
        model = TemplateCollection
        fields = [
            'id', 'name', 'description', 'is_featured', 'template_count',
            'curator_name', 'created_at', 'updated_at'
        ]
    
    def get_template_count(self, obj):
        return obj.templates.count()

class MarketplaceTransactionSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source='buyer.get_full_name', read_only=True)
    seller_name = serializers.CharField(source='seller.get_full_name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    
    class Meta:
        model = MarketplaceTransaction
        fields = [
            'id', 'transaction_type', 'status', 'amount', 'platform_fee',
            'developer_payout', 'created_at', 'completed_at',
            'buyer_name', 'seller_name', 'template_name'
        ]