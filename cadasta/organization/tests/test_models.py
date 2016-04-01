from django.conf import settings
from django.test import TestCase

from tutelary.models import Policy

from accounts.tests.factories import UserFactory
from .factories import OrganizationFactory, ProjectFactory
from ..models import OrganizationRole, ProjectRole

PERMISSIONS_DIR = settings.BASE_DIR + '/permissions/'


class OrganizationTest(TestCase):
    def test_str(self):
        org = OrganizationFactory.create(**{'name': 'Org'})
        assert str(org) == '<Organization: Org>'

    def test_has_random_id(self):
        org = OrganizationFactory.create()
        assert type(org.id) is not int


class OrganizationRoleTest(TestCase):
    def test_assign_new_admin(self):
        Policy.objects.create(
            name='org-admin',
            body=open(PERMISSIONS_DIR + 'org-admin.json').read()
        )

        org = OrganizationFactory.create()
        user = UserFactory.create()

        OrganizationRole.objects.create(
            organization=org, user=user, admin=True)
        assert user.has_perm('org.update', org) is True

    def test_keep_admin_role(self):
        policy = Policy.objects.create(
            name='org-admin',
            body=open(PERMISSIONS_DIR + 'org-admin.json').read()
        )
        user = UserFactory.create()
        org = OrganizationFactory.create(add_users=[user])
        user.assign_policies((policy, {'organization': org.slug}))

        assert user.has_perm('org.update', org) is True
        role = OrganizationRole.objects.get(organization=org, user=user)
        role.admin = True
        role.save()
        assert user.has_perm('org.update', org) is True

    def test_keep_non_admin_role(self):
        Policy.objects.create(
            name='org-admin',
            body=open(PERMISSIONS_DIR + 'org-admin.json').read()
        )
        user = UserFactory.create()
        org = OrganizationFactory.create(add_users=[user])

        assert user.has_perm('org.update', org) is False
        role = OrganizationRole.objects.get(organization=org, user=user)
        role.admin = False
        role.save()
        assert user.has_perm('org.update', org) is False

    def test_add_admin_role(self):
        Policy.objects.create(
            name='org-admin',
            body=open(PERMISSIONS_DIR + 'org-admin.json').read()
        )

        user = UserFactory.create()
        org = OrganizationFactory.create(add_users=[user])

        assert user.has_perm('org.update', org) is False
        role = OrganizationRole.objects.get(organization=org, user=user)
        role.admin = True
        role.save()
        assert user.has_perm('org.update', org) is True

    def test_remove_admin_role(self):
        policy = Policy.objects.create(
            name='org-admin',
            body=open(PERMISSIONS_DIR + 'org-admin.json').read()
        )

        user = UserFactory.create()
        org = OrganizationFactory.create(add_users=[user])

        user.assign_policies((policy, {'organization': org.slug}))

        assert user.has_perm('org.update', org) is True
        role = OrganizationRole.objects.get(organization=org, user=user)
        role.admin = False
        role.save()
        assert user.has_perm('org.update', org) is False

    def test_delete_project_roles(self):
        user = UserFactory.create()
        org = OrganizationFactory.create(add_users=[user])
        ProjectFactory.create_batch(2, add_users=[user],
                                    **{'organization': org})
        ProjectFactory.create_batch(2, add_users=[user])

        assert ProjectRole.objects.filter(user=user).count() == 4

        role = OrganizationRole.objects.get(organization=org, user=user)
        role.delete()

        assert ProjectRole.objects.filter(user=user).count() == 2


class ProjectTest(TestCase):
    def test_str(self):
        project = ProjectFactory.create(**{'name': 'Project'})
        assert str(project) == '<Project: Project>'

    def test_has_random_id(self):
        project = ProjectFactory.create()
        assert type(project.id) is not int


class ProjectRoleTest(TestCase):
    def test_assign_new_manager(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        ProjectRole.objects.create(
            project=project, user=user, role='PM')
        assert user.has_perm('project.edit', project) is True

    def test_add_manager_role(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        assert user.has_perm('project.edit', project) is False
        ProjectRole.objects.create(
            project=project, user=user, role='PM')
        assert user.has_perm('project.edit', project) is True

    def test_keep_manager_role(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        role = ProjectRole.objects.create(
            project=project, user=user, role='PM')

        assert user.has_perm('project.edit', project) is True
        role.manager = True
        role.save()
        assert user.has_perm('project.edit', project) is True

    def test_keep_non_manager_role(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        role = ProjectRole.objects.create(
            project=project, user=user, role='PU')

        assert user.has_perm('project.edit', project) is False
        role.manager = False
        role.save()
        assert user.has_perm('project.edit', project) is False

    def test_remove_manager_role(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        role = ProjectRole.objects.create(
            project=project, user=user, role='PM')

        assert user.has_perm('project.edit', project) is True
        role.role = 'PU'
        role.save()
        assert user.has_perm('project.edit', project) is False

    def test_assign_new_collector(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        ProjectRole.objects.create(
            project=project, user=user, role='DC')
        assert user.has_perm('project.resources.add', project) is True

    def test_add_collector_role(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        assert user.has_perm('project.resources.add', project) is False
        ProjectRole.objects.create(
            project=project, user=user, role='DC')
        assert user.has_perm('project.resources.add', project) is True

    def test_keep_collector_role(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        role = ProjectRole.objects.create(
            project=project, user=user, role='DC')

        assert user.has_perm('project.resources.add', project) is True
        role.role = 'DC'
        role.save()
        assert user.has_perm('project.resources.add', project) is True

    def test_keep_non_collector_role(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        role = ProjectRole.objects.create(
            project=project, user=user, role='PU')

        assert user.has_perm('project.resources.add', project) is False
        role.role = 'PU'
        role.save()
        assert user.has_perm('project.resources.add', project) is False

    def test_remove_collector_role(self):
        project = ProjectFactory.create()
        user = UserFactory.create()

        role = ProjectRole.objects.create(
            project=project, user=user, role='DC')

        assert user.has_perm('project.resources.add', project) is True
        role.role = 'PU'
        role.save()
        assert user.has_perm('project.resources.add', project) is False
