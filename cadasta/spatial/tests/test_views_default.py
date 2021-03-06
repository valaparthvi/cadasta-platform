import pytest
import json
from importlib import import_module
from django.http import HttpRequest, Http404
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from questionnaires.tests import factories as q_factories

from tutelary.models import Policy, assign_user_policies
from jsonattrs.models import Attribute, AttributeType, Schema
from skivvy import ViewTestCase, remove_csrf

from accounts.tests.factories import UserFactory
from organization.tests.factories import ProjectFactory
from core.tests.utils.cases import UserTestCase, FileStorageTestCase
from core.tests.utils.files import make_dirs  # noqa
from resources.tests.factories import ResourceFactory
from resources.tests.utils import clear_temp  # noqa
from resources.forms import AddResourceFromLibraryForm, ResourceForm
from party.tests.factories import PartyFactory, TenureRelationshipFactory
from party.models import Party, TenureRelationship, TenureRelationshipType

from .factories import SpatialUnitFactory
from ..views import default
from .. import forms
from ..models import SpatialUnit

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


def assign_policies(user, deny_edit_delete_permissions=False):
    clauses = {
        'clause': [
            {
                'effect': 'allow',
                'object': ['project/*/*'],
                'action': ['spatial.*', 'tenure_rel.*']
            },
            {
                'effect': 'allow',
                'object': ['spatial/*/*/*'],
                'action': ['spatial.*', 'spatial.resources.*']
            },
            {
                'effect': 'allow',
                'object': ['tenure_rel/*/*/*'],
                'action': ['tenure_rel.*', 'tenure_rel.*.*']
            }
        ]
    }

    if deny_edit_delete_permissions:
        deny_clause = {
                          'effect': 'deny',
                          'object': ['spatial/*/*/*'],
                          'action': ['spatial.update', 'spatial.delete']
                       }
        clauses['clause'].append(deny_clause)

    policy = Policy.objects.create(
        name='allow',
        body=json.dumps(clauses))
    assign_user_policies(user, policy)


class LocationsListTest(ViewTestCase, UserTestCase, TestCase):
    view_class = default.LocationsList
    template = 'spatial/location_map.html'

    def setup_models(self):
        self.project = ProjectFactory.create()
        self.locations = SpatialUnitFactory.create_batch(
            2, project=self.project)
        SpatialUnitFactory.create()

    def setup_template_context(self):
        return {
            'object': self.project,
            'object_list': self.locations,
            'is_allowed_add_location': True
        }

    def setup_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug
        }

    def test_get_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert response.content == self.expected_content

    def test_get_from_non_existent_project(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'project': 'abc123'})

    def test_get_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(user=user)
        assert response.status_code == 200
        expected = self.render_content(is_allowed_add_location=False)
        assert response.content == expected

    def test_get_with_unauthenticated_user(self):
        response = self.request()
        assert response.status_code == 302
        assert '/account/login/' in response.location


class LocationAddTest(ViewTestCase, UserTestCase, TestCase):
    view_class = default.LocationsAdd
    template = 'spatial/location_add.html'
    success_url_name = 'locations:detail'
    post_data = {
        'geometry': '{"type": "Polygon","coordinates": [[[-0.1418137550354'
                    '004,51.55240622205599],[-0.14117002487182617,51.55167'
                    '905819532],[-0.1411914825439453,51.55181915488898],[-'
                    '0.1411271095275879,51.55254631651022],[-0.14181375503'
                    '54004,51.55240622205599]]]}',
        'type': 'CB',
        'spatialunit::default::fname': 'Test text'
    }

    def setup_models(self):
        self.project = ProjectFactory.create()
        questionnaire = q_factories.QuestionnaireFactory.create(
            project=self.project)
        content_type = ContentType.objects.get(
            app_label='spatial', model='spatialunit')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(
                self.project.organization.id, self.project.id, questionnaire.id
            )
        )
        attr_type = AttributeType.objects.get(name='text')
        Attribute.objects.create(
            schema=schema,
            name='fname', long_name='Test field',
            attr_type=attr_type, index=0,
            required=False, omit=False
        )

    def setup_template_context(self):
        return {
            'object': self.project,
            'is_allowed_add_location': True,
            'form': forms.LocationForm(project=self.project)
        }

    def setup_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug
        }

    def setup_success_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug,
            'location': self.location_created.id
        }

    def test_get_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        expected_content = self.render_content(cancel_url=reverse(
            'organization:project-dashboard', kwargs=self.setup_url_kwargs()))
        assert response.content == expected_content
        assert '<input class="form-control" '
        'id="id_spatialunit::default::fname" '
        'name="spatialunit::default::fname" type="text" />' in response.content

    def test_get_with_authorized_user_with_referrer(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user,
                                request_meta={'HTTP_REFERER': '/help/'})
        assert response.status_code == 200
        assert '<input class="form-control" '
        'id="id_spatialunit::default::fname" '
        'name="spatialunit::default::fname" type="text" />' in response.content

    def test_get_with_authorized_user_with_same_referrer(self):
        user = UserFactory.create()
        assign_policies(user)
        referer = reverse('locations:add', kwargs=self.setup_url_kwargs())
        response = self.request(user=user,
                                request_meta={'HTTP_REFERER': referer})
        assert response.status_code == 200
        assert '<input class="form-control" '
        'id="id_spatialunit::default::fname" '
        'name="spatialunit::default::fname" type="text" />' in response.content

    def test_get_with_authorized_user_with_same_referrer_with_session(self):
        user = UserFactory.create()
        assign_policies(user)

        # Manually construct our request to enable session reuse
        request = HttpRequest()
        self._request = request
        setattr(request, 'method', 'GET')
        setattr(request, 'user', user)
        request.META['SERVER_NAME'] = 'testserver'
        request.META['SERVER_PORT'] = '80'
        setattr(request, 'session', SessionStore())
        url_params = self._get_url_kwargs()
        view = self.setup_view()
        expected_content = self.render_content(cancel_url='/info/')

        # First request that should set the session
        request.META['HTTP_REFERER'] = '/info/'
        response = view(request, **url_params)
        content = response.render().content.decode('utf-8')
        assert response.status_code == 200
        assert remove_csrf(content) == expected_content
        assert request.session['cancel_add_location_url'] == '/info/'

        # Second request to check that the session is being used
        request.META['HTTP_REFERER'] = reverse(
            'locations:add', kwargs=self.setup_url_kwargs())
        response = view(request, **url_params)
        content = response.render().content.decode('utf-8')
        assert response.status_code == 200
        assert remove_csrf(content) == expected_content
        assert request.session['cancel_add_location_url'] == '/info/'

    def test_get_from_non_existent_project(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'project': 'abc123'})

    def test_get_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to add "
                "locations to this project." in response.messages)

    def test_get_with_unauthenticated_user(self):
        response = self.request()
        assert response.status_code == 302
        assert '/account/login/' in response.location

    def test_get_with_archived_project(self):
        self.project.archived = True
        self.project.save()

        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to add "
                "locations to this project." in response.messages)

    def test_post_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)

        assert SpatialUnit.objects.count() == 1
        self.location_created = SpatialUnit.objects.first()
        assert self.location_created.attributes.get('fname') == 'Test text'
        assert response.status_code == 302
        assert response.location == self.expected_success_url

    def test_post_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(method='POST', user=user)
        assert SpatialUnit.objects.count() == 0
        assert response.status_code == 302
        assert ("You don't have permission to add "
                "locations to this project." in response.messages)

    def test_post_with_unauthenticated_user(self):
        response = self.request(method='POST')
        assert SpatialUnit.objects.count() == 0
        assert response.status_code == 302
        assert '/account/login/' in response.location

    def test_post_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert SpatialUnit.objects.count() == 0
        assert response.status_code == 302
        assert ("You don't have permission to add "
                "locations to this project." in response.messages)


class LocationDetailTest(ViewTestCase, UserTestCase, TestCase):
    view_class = default.LocationDetail
    template = 'spatial/location_detail.html'

    def setup_models(self):
        self.project = ProjectFactory.create()
        content_type = ContentType.objects.get(
            app_label='spatial', model='spatialunit')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(self.project.organization.id, self.project.id, ))
        attr_type = AttributeType.objects.get(name='text')
        Attribute.objects.create(
            schema=schema,
            name='fname', long_name='Test field',
            attr_type=attr_type, index=0,
            required=False, omit=False
        )
        Attribute.objects.create(
            schema=schema,
            name='fname_2', long_name='Test field 2',
            attr_type=AttributeType.objects.get(name='select_one'),
            choices=['-', 'one', 'two', 'three'],
            choice_labels=['None', 'Choice 1', 'Choice 2', 'Choice 3'],
            index=1,
            required=False, omit=False
        )
        Attribute.objects.create(
            schema=schema,
            name='fname_3', long_name='Test field 3',
            attr_type=AttributeType.objects.get(name='select_multiple'),
            choices=['-', 'one', 'two', 'three'],
            choice_labels=['None', 'Choice 1', 'Choice 2', 'Choice 3'],
            index=2,
            required=False, omit=False
        )
        self.location = SpatialUnitFactory.create(
            project=self.project, attributes={
                'fname': 'test',
                'fname_2': 'two',
                'fname_3': ['one', 'three']
            })

    def setup_template_context(self):
        return {
            'object': self.project,
            'location': self.location,
            'attributes': (('Test field', 'test', ),
                           ('Test field 2', 'Choice 2', ),
                           ('Test field 3', 'Choice 1, Choice 3', )),
            'is_allowed_add_location': True,
            'is_allowed_edit_location': True,
            'is_allowed_delete_location': True,
        }

    def setup_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug,
            'location': self.location.id
        }

    def test_get_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert response.content == self.expected_content

    def test_does_not_show_buttons_when_no_edit_permissions(self):
        user = UserFactory.create()
        assign_policies(user, True)
        response = self.request(user=user)
        assert response.status_code == 200
        expected = self.render_content(is_allowed_edit_location=False,
                                       is_allowed_delete_location=False)
        assert response.content == expected

    def test_get_with_incomplete_questionnaire(self):
        questionnaire = q_factories.QuestionnaireFactory.create()
        self.project.current_questionnaire = questionnaire.id
        self.project.save()

        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert response.content == self.expected_content

    def test_get_with_questionnaire(self):
        questionnaire = q_factories.QuestionnaireFactory.create()
        self.project.current_questionnaire = questionnaire.id
        self.project.save()

        location_type_question = q_factories.QuestionFactory.create(
            questionnaire=questionnaire,
            name='location_type',
            label={'en': 'Location type', 'de': 'Parzelle Typ'},
            type='S1')
        q_factories.QuestionOptionFactory.create(
            question=location_type_question,
            name=self.location.type,
            label={'en': 'House', 'de': 'Haus'})

        tenure_type_question = q_factories.QuestionFactory.create(
            questionnaire=questionnaire,
            name='tenure_type',
            label={'en': 'Location type', 'de': 'Parzelle Typ'},
            type='S1')
        q_factories.QuestionOptionFactory.create(
            question=tenure_type_question,
            name='LH',
            label={'en': 'Leasehold', 'de': 'Miete'})
        q_factories.QuestionOptionFactory.create(
            question=tenure_type_question,
            name='WR',
            label={'en': 'Water rights', 'de': 'Wasserecht'})
        lh_ten = TenureRelationshipFactory.create(
            tenure_type=TenureRelationshipType.objects.get(id='LH'),
            spatial_unit=self.location,
            project=self.project)

        wr_ten = TenureRelationshipFactory.create(
            tenure_type=TenureRelationshipType.objects.get(id='WR'),
            spatial_unit=self.location,
            project=self.project)

        relationships = self.location.tenurerelationship_set.all()
        for rel in relationships:
            if lh_ten == rel:
                rel.type_labels = ('data-label-de="Miete" '
                                   'data-label-en="Leasehold"')
            elif wr_ten == rel:
                rel.type_labels = ('data-label-de="Wasserecht" '
                                   'data-label-en="Water rights"')

        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert response.content == self.render_content(
            type_labels=('data-label-de="Parzelle Typ" '
                         'data-label-en="Location type"'),
            type_choice_labels=('data-label-de="Haus" data-label-en="House"'),
            relationships=relationships,
            form_lang_default='en',
            form_langs=[('en', 'English'), ('de', 'German')]
        )

    def test_get_with_questionnaire_but_missing_option(self):
        questionnaire = q_factories.QuestionnaireFactory.create()
        self.project.current_questionnaire = questionnaire.id
        self.project.save()

        q_factories.QuestionFactory.create(
            questionnaire=questionnaire,
            name='location_type',
            label={'en': 'Location type', 'de': 'Parzelle Typ'},
            type='S1')

        tenure_type_question = q_factories.QuestionFactory.create(
            questionnaire=questionnaire,
            name='tenure_type',
            label={'en': 'Location type', 'de': 'Parzelle Typ'},
            type='S1')
        q_factories.QuestionOptionFactory.create(
            question=tenure_type_question,
            name='LH',
            label={'en': 'Leasehold', 'de': 'Miete'})
        q_factories.QuestionOptionFactory.create(
            question=tenure_type_question,
            name='WR',
            label={'en': 'Water rights', 'de': 'Wasserecht'})
        lh_ten = TenureRelationshipFactory.create(
            tenure_type=TenureRelationshipType.objects.get(id='LH'),
            spatial_unit=self.location,
            project=self.project)

        wr_ten = TenureRelationshipFactory.create(
            tenure_type=TenureRelationshipType.objects.get(id='WR'),
            spatial_unit=self.location,
            project=self.project)

        relationships = self.location.tenurerelationship_set.all()
        for rel in relationships:
            if lh_ten == rel:
                rel.type_labels = ('data-label-de="Miete" '
                                   'data-label-en="Leasehold"')
            elif wr_ten == rel:
                rel.type_labels = ('data-label-de="Wasserecht" '
                                   'data-label-en="Water rights"')

        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert response.content == self.render_content(
            type_labels=('data-label-de="Parzelle Typ" '
                         'data-label-en="Location type"'),
            relationships=relationships,
            form_lang_default='en',
            form_langs=[('en', 'English'), ('de', 'German')]
        )

    def test_get_from_non_existent_project(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'project': 'abc123'})

    def test_get_non_existent_location(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'location': 'abc123'})

    def test_get_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to view this location."
                in response.messages)

    def test_get_with_unauthenticated_user(self):
        response = self.request()
        assert response.status_code == 302
        assert '/account/login/' in response.location


class LocationEditTest(ViewTestCase, UserTestCase, TestCase):
    view_class = default.LocationEdit
    template = 'spatial/location_edit.html'
    success_url_name = 'locations:detail'
    post_data = {
        'geometry': '{"type": "Polygon","coordinates": [[[-0.1418137550354'
                    '004,51.55240622205599],[-0.14117002487182617,51.55167'
                    '905819532],[-0.1411914825439453,51.55181915488898],[-'
                    '0.1411271095275879,51.55254631651022],[-0.14181375503'
                    '54004,51.55240622205599]]]}',
        'type': 'NP',
        'spatialunit::default::fname': 'New text'
    }

    def setup_models(self):
        self.project = ProjectFactory.create()
        questionnaire = q_factories.QuestionnaireFactory.create(
            project=self.project)
        content_type = ContentType.objects.get(
            app_label='spatial', model='spatialunit')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(
                self.project.organization.id, self.project.id, questionnaire.id
            )
        )
        attr_type = AttributeType.objects.get(name='text')
        Attribute.objects.create(
            schema=schema,
            name='fname', long_name='Test field',
            attr_type=attr_type, index=0,
            required=False, omit=False
        )
        self.location = SpatialUnitFactory.create(
            project=self.project, attributes={'fname': 'test'})

    def setup_template_context(self):
        return {'object': self.project,
                'location': self.location,
                'form': forms.LocationForm(instance=self.location),
                'is_allowed_add_location': True}

    def setup_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug,
            'location': self.location.id
        }

    def test_get_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert '<input class="form-control" '
        'id="id_spatialunit::default::fname" '
        'name="spatialunit::default::fname" type="text" />' in response.content

    def test_get_from_non_existent_project(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'project': 'abc123'})

    def test_get_non_existent_location(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'location': 'abc123'})

    def test_get_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to update this location."
                in response.messages)

    def test_get_with_unauthenticated_user(self):
        response = self.request()
        assert response.status_code == 302
        assert '/account/login/' in response.location

    def test_get_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to update this location."
                in response.messages)

    def test_post_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert response.location == self.expected_success_url

        # attributes field is deferred so we fetch a fresh instance
        location = SpatialUnit.objects.defer(None).get(id=self.location.id)
        assert location.type == self.post_data['type']
        assert location.attributes.get('fname') == 'New text'

    def test_post_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to update this location."
                in response.messages)
        self.location.refresh_from_db()
        assert self.location.type != self.post_data['type']

    def test_post_with_unauthenticated_user(self):
        response = self.request(method='POST')
        assert response.status_code == 302
        assert '/account/login/' in response.location
        self.location.refresh_from_db()
        assert self.location.type != self.post_data['type']

    def test_post_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to update this location."
                in response.messages)
        self.location.refresh_from_db()
        assert self.location.type != self.post_data['type']


class LocationDeleteTest(ViewTestCase, UserTestCase, TestCase):
    view_class = default.LocationDelete
    template = 'spatial/location_delete.html'
    success_url_name = 'locations:list'

    def setup_models(self):
        self.project = ProjectFactory.create()
        self.location = SpatialUnitFactory.create(project=self.project)
        TenureRelationshipFactory.create(
            project=self.project, spatial_unit=self.location)

    def setup_template_context(self):
        return {'object': self.project,
                'location': self.location,
                'is_allowed_add_location': True}

    def setup_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug,
            'location': self.location.id
        }

    def setup_success_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug
        }

    def test_get_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert response.content == self.expected_content

    def test_get_from_non_existent_project(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'project': 'abc123'})

    def test_get_non_existent_location(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'location': 'abc123'})

    def test_get_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to remove this location."
                in response.messages)

    def test_get_with_unauthenticated_user(self):
        response = self.request()
        assert response.status_code == 302
        assert '/account/login/' in response.location

    def test_get_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to remove this location."
                in response.messages)

    def test_post_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert response.location == self.expected_success_url

        assert SpatialUnit.objects.count() == 0
        assert TenureRelationship.objects.count() == 0

    def test_post_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to remove this location."
                in response.messages)
        assert SpatialUnit.objects.count() == 1
        assert TenureRelationship.objects.count() == 1

    def test_post_with_unauthenticated_user(self):
        response = self.request(method='POST')
        assert response.status_code == 302
        assert '/account/login/' in response.location
        assert SpatialUnit.objects.count() == 1
        assert TenureRelationship.objects.count() == 1

    def test_POST_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to remove this location."
                in response.messages)
        assert SpatialUnit.objects.count() == 1
        assert TenureRelationship.objects.count() == 1


@pytest.mark.usefixtures('make_dirs')
class LocationResourceAddTest(ViewTestCase, UserTestCase, TestCase):
    view_class = default.LocationResourceAdd
    template = 'spatial/resources_add.html'
    success_url_name = 'locations:detail'

    def setup_models(self):
        self.project = ProjectFactory.create()
        self.location = SpatialUnitFactory.create(project=self.project)
        self.attached = ResourceFactory.create(project=self.project,
                                               content_object=self.location)
        self.unattached = ResourceFactory.create(project=self.project)

    def setup_template_context(self):
        form = AddResourceFromLibraryForm(content_object=self.location,
                                          project_id=self.project.id)
        return {'object': self.project,
                'location': self.location,
                'form': form,
                'is_allowed_add_location': True}

    def setup_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug,
            'location': self.location.id
        }

    def setup_post_data(self):
        return {
            self.attached.id: False,
            self.unattached.id: True,
        }

    def test_get_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert response.content == self.expected_content

    def test_get_from_non_existent_project(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'project': 'abc123'})

    def test_get_non_existent_location(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'location': 'abc123'})

    def test_get_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to "
                "add resources to this location." in response.messages)

    def test_get_with_unauthenticated_user(self):
        response = self.request()
        assert response.status_code == 302
        assert '/account/login/' in response.location

    def test_get_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to "
                "add resources to this location." in response.messages)

    def test_post_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert response.location == self.expected_success_url + '#resources'

        location_resources = self.location.resources.all()
        assert len(location_resources) == 2
        assert self.attached in location_resources
        assert self.unattached in location_resources

    def test_post_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to "
                "add resources to this location." in response.messages)
        assert self.location.resources.count() == 1
        assert self.location.resources.first() == self.attached

    def test_post_with_unauthenticated_user(self):
        response = self.request(method='POST')
        assert response.status_code == 302
        assert '/account/login/' in response.location
        assert self.location.resources.count() == 1
        assert self.location.resources.first() == self.attached

    def test_post_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to "
                "add resources to this location." in response.messages)
        assert self.location.resources.count() == 1
        assert self.location.resources.first() == self.attached


@pytest.mark.usefixtures('make_dirs')
@pytest.mark.usefixtures('clear_temp')
class LocationResourceNewTest(ViewTestCase, UserTestCase,
                              FileStorageTestCase, TestCase):
    view_class = default.LocationResourceNew
    template = 'spatial/resources_new.html'
    success_url_name = 'locations:detail'

    def setup_models(self):
        self.project = ProjectFactory.create()
        self.location = SpatialUnitFactory.create(project=self.project)

    def setup_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug,
            'location': self.location.id
        }

    def setup_template_context(self):
        form = ResourceForm(content_object=self.location,
                            project_id=self.project.id)
        return {'object': self.project,
                'location': self.location,
                'form': form,
                'is_allowed_add_location': True}

    def setup_post_data(self):
        file = self.get_file('/resources/tests/files/image.jpg', 'rb')
        file_name = self.storage.save('resources/image.jpg', file.read())
        file.close()

        return {
            'name': 'Some name',
            'description': '',
            'file': file_name,
            'original_file': 'image.png',
            'mime_type': 'image/jpeg'
        }

    def test_get_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert response.content == self.expected_content

    def test_get_from_non_existent_project(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'project': 'abc123'})

    def test_get_non_existent_location(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'location': 'abc123'})

    def test_get_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to "
                "add resources to this location." in response.messages)

    def test_get_with_unauthenticated_user(self):
        response = self.request()
        assert response.status_code == 302
        assert '/account/login/' in response.location

    def test_get_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to "
                "add resources to this location." in response.messages)

    def test_post_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert response.location == self.expected_success_url + '#resources'
        assert self.location.resources.count() == 1

    def test_post_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to "
                "add resources to this location." in response.messages)
        assert self.location.resources.count() == 0

    def test_post_with_unauthenticated_user(self):
        response = self.request(method='POST')
        assert response.status_code == 302
        assert '/account/login/' in response.location
        assert self.location.resources.count() == 0

    def test_post_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to "
                "add resources to this location." in response.messages)
        assert self.location.resources.count() == 0


class TenureRelationshipAddTest(ViewTestCase, UserTestCase, TestCase):
    view_class = default.TenureRelationshipAdd
    template = 'spatial/relationship_add.html'
    success_url_name = 'locations:detail'
    post_data = {
        'new_entity': 'on',
        'id': '',
        'name': 'The Beatles',
        'party_type': 'GR',
        'tenure_type': 'CU',
        'party::gr::p_name': 'Party Name',
        'party::gr::p_gr_name': 'Party Group Name',
        'tenurerelationship::default::r_name': 'Rel Name'
    }

    def setup_models(self):
        self.project = ProjectFactory.create()
        questionnaire = q_factories.QuestionnaireFactory.create(
            project=self.project)
        self.spatial_unit = SpatialUnitFactory(project=self.project)
        content_type = ContentType.objects.get(
            app_label='party', model='tenurerelationship')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(
                self.project.organization.id, self.project.id, questionnaire.id
            )
        )
        attr_type = AttributeType.objects.get(name='text')
        Attribute.objects.create(
            schema=schema,
            name='r_name', long_name='Relationship field',
            attr_type=attr_type, index=0,
            required=False, omit=False
        )

        content_type = ContentType.objects.get(
            app_label='party', model='party')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(
                self.project.organization.id, self.project.id, questionnaire.id
            )
        )
        attr_type = AttributeType.objects.get(name='text')
        Attribute.objects.create(
            schema=schema,
            name='p_name', long_name='Party field',
            attr_type=attr_type, index=0,
            required=False, omit=False
        )
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(
                self.project.organization.id, self.project.id,
                questionnaire.id, 'GR'
            )
        )
        Attribute.objects.create(
            schema=schema,
            name='p_gr_name', long_name='Party Group field',
            attr_type=attr_type, index=0,
            required=False, omit=False
        )

    def setup_template_context(self):
        return {
            'object': self.project,
            'location': self.spatial_unit,
            'form': forms.TenureRelationshipForm(
                project=self.project,
                spatial_unit=self.spatial_unit,
                initial={
                    'new_entity': not self.project.parties.exists(),
                },
            ),
            'is_allowed_add_location': True,
        }

    def setup_url_kwargs(self):
        return {
            'organization': self.project.organization.slug,
            'project': self.project.slug,
            'location': self.spatial_unit.id
        }

    def test_get_with_authorized_user(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 200
        assert response.content == self.expected_content

    def test_get_from_non_existent_project(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'project': 'abc123'})

    def test_get_non_existent_location(self):
        user = UserFactory.create()
        assign_policies(user)
        with pytest.raises(Http404):
            self.request(user=user, url_kwargs={'location': 'abc123'})

    def test_get_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to add tenure relationships to "
                "this project." in response.messages)

    def test_get_with_unauthenticated_user(self):
        response = self.request()
        assert response.status_code == 302
        assert '/account/login/' in response.location

    def test_get_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(user=user)
        assert response.status_code == 302
        assert ("You don't have permission to add tenure relationships to "
                "this project." in response.messages)

    def test_post_new_party_with_authorized(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert (response.location ==
                self.expected_success_url + '#relationships')

        assert TenureRelationship.objects.count() == 1
        rel = TenureRelationship.objects.first()
        assert rel.attributes.get('r_name') == 'Rel Name'
        assert Party.objects.count() == 1
        party = Party.objects.first()
        assert party.attributes.get('p_name') == 'Party Name'
        assert party.attributes.get('p_gr_name') == 'Party Group Name'

    def test_post_existing_party_with_authorized(self):
        user = UserFactory.create()
        assign_policies(user)
        party = PartyFactory.create(project=self.project)
        response = self.request(method='POST', user=user,
                                post_data={
                                    'new_entity': '',
                                    'id': party.id,
                                })
        assert response.status_code == 302
        assert (response.location ==
                self.expected_success_url + '#relationships')

        assert TenureRelationship.objects.count() == 1
        rel = TenureRelationship.objects.first()
        assert rel.attributes.get('r_name') == 'Rel Name'
        assert Party.objects.count() == 1
        assert Party.objects.first().name == party.name

    def test_post_with_authorized_invalid_new_party_data(self):
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST',
                                user=user,
                                post_data={'name': '', 'party_type': ''})
        assert response.status_code == 200
        data = self.post_data.copy()
        data.update({'name': '', 'party_type': ''})
        form = forms.TenureRelationshipForm(
            project=self.project,
            spatial_unit=self.spatial_unit,
            data=data
        )
        expected = self.render_content(form=form)
        assert response.content == expected

        assert TenureRelationship.objects.count() == 0
        assert Party.objects.count() == 0

    def test_post_with_authorized_invalid_existing_party_data(self):
        user = UserFactory.create()
        assign_policies(user)

        party = PartyFactory.create(project=self.project)
        response = self.request(method='POST',
                                user=user,
                                post_data={'new_entity': ''})

        data = self.post_data.copy()
        data['new_entity'] = ''
        form = forms.TenureRelationshipForm(
            project=self.project,
            spatial_unit=self.spatial_unit,
            data=data
        )
        assert response.status_code == 200
        expected = self.render_content(form=form)
        assert response.content == expected
        assert TenureRelationship.objects.count() == 0
        assert Party.objects.count() == 1
        assert Party.objects.first().name == party.name

    def test_post_with_unauthorized_user(self):
        user = UserFactory.create()
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to add tenure relationships to "
                "this project." in response.messages)
        assert TenureRelationship.objects.count() == 0
        assert Party.objects.count() == 0

    def test_post_with_unauthenticated_user(self):
        response = self.request(method='POST')
        assert response.status_code == 302
        assert '/account/login/' in response.location
        assert TenureRelationship.objects.count() == 0
        assert Party.objects.count() == 0

    def test_post_with_archived_project(self):
        self.project.archived = True
        self.project.save()
        user = UserFactory.create()
        assign_policies(user)
        response = self.request(method='POST', user=user)
        assert response.status_code == 302
        assert ("You don't have permission to add tenure relationships to "
                "this project." in response.messages)
        assert TenureRelationship.objects.count() == 0
        assert Party.objects.count() == 0
