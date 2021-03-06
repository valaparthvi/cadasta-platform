import json
from buckets.serializers import S3Field
from django.utils.translation import ugettext as _
from rest_framework import serializers

from .models import ContentObject, Resource, SpatialResource


class ResourceSerializer(serializers.ModelSerializer):
    file = S3Field()

    class Meta:
        model = Resource
        fields = ('id', 'name', 'description', 'file', 'original_file',
                  'archived', 'mime_type', )
        read_only_fields = ('id', )
        extra_kwargs = {'mime_type': {'required': False}}

    def is_valid(self, raise_exception=False):
        data = self.initial_data
        if 'id' in data:
            try:
                self.resource = Resource.objects.get(id=data['id'])
                self._errors = {}
                self._validated_data = data
                return True
            except Resource.DoesNotExist:
                self._errors = {'id': _('Resource not found')}
                if raise_exception:
                    raise serializers.ValidationError(self._errors)
                return False

        return super().is_valid(raise_exception=raise_exception)

    def create(self, validated_data):
        if 'id' in validated_data:
            ContentObject.objects.create(
                resource_id=validated_data['id'],
                content_object=self.context['content_object']
            )
            return self.resource
        else:
            return Resource.objects.create(
                content_object=self.context['content_object'],
                contributor=self.context['contributor'],
                project_id=self.context['project_id'],
                **validated_data
            )


class SpatialResourceSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    geom = serializers.SerializerMethodField()

    class Meta:
        model = SpatialResource
        fields = ('id', 'name', 'time', 'geom')

    def get_geom(self, obj):
        return json.loads(obj.geom.geojson)


class ReadOnlyResourceSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    original_file = serializers.CharField()
    archived = serializers.BooleanField()
    spatial_resources = SpatialResourceSerializer(many=True)
