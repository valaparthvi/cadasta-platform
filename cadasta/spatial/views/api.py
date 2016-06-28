from rest_framework import generics, filters, status
from rest_framework.response import Response
from tutelary.mixins import APIPermissionRequiredMixin

from spatial import serializers
from . import mixins


class SpatialUnitList(APIPermissionRequiredMixin,
                      mixins.SpatialQuerySetMixin,
                      generics.ListCreateAPIView):

    serializer_class = serializers.SpatialUnitSerializer
    filter_backends = (filters.DjangoFilterBackend,
                       filters.SearchFilter,
                       filters.OrderingFilter,)
    filter_fields = ('type',)
    search_fields = ('name',)
    ordering_fields = ('name',)

    permission_required = {
        'GET': 'spatial.list',
        'POST': 'spatial.create',
    }

    def get_queryset(self):
        return super().get_queryset().filter(
            project__slug=self.kwargs['project_slug'])


class SpatialUnitDetail(APIPermissionRequiredMixin,
                        mixins.SpatialQuerySetMixin,
                        generics.RetrieveUpdateDestroyAPIView):

    serializer_class = serializers.SpatialUnitSerializer
    lookup_url_kwarg = 'spatial_id'
    lookup_field = 'id'
    permission_required = {
        'GET': 'spatial.view',
        'PATCH': 'spatial.update',
        'DELETE': 'spatial.delete'
    }

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SpatialRelationshipCreate(APIPermissionRequiredMixin,
                                mixins.SpatialRelationshipQuerySetMixin,
                                generics.CreateAPIView):

    permission_required = 'spatial_rel.create'
    serializer_class = serializers.SpatialRelationshipWriteSerializer


class SpatialRelationshipDetail(APIPermissionRequiredMixin,
                                mixins.SpatialRelationshipQuerySetMixin,
                                generics.RetrieveUpdateDestroyAPIView):

    lookup_url_kwarg = 'spatial_rel_id'
    lookup_field = 'id'
    permission_required = {
        'GET': 'spatial_rel.view',
        'PATCH': 'spatial_rel.update',
        'DELETE': 'spatial_rel.delete'
    }

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return serializers.SpatialRelationshipWriteSerializer
        else:
            return serializers.SpatialRelationshipReadSerializer

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)