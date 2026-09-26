"""Create two distinct synthetic staging users in the isolated staging database."""
import getpass
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_project.settings')
import django
django.setup()
from django.contrib.auth.models import Group, User
from django.db import transaction

for name, group_name in [('founder_viewer', 'founder_viewer'), ('test_editor', 'editor')]:
    if User.objects.filter(username=name).exists():
        raise RuntimeError(f'{name} already exists; use a separate reviewed rotation')
    password = getpass.getpass(f'Password for {name}: ')
    confirmation = getpass.getpass('Confirm: ')
    if not password or password != confirmation:
        raise RuntimeError('Password not confirmed')
    with transaction.atomic():
        group, _ = Group.objects.get_or_create(name=group_name)
        user = User.objects.create_user(username=name, password=password, is_staff=False, is_superuser=False)
        user.groups.add(group)
    print(f'Created {name} in {group_name}')
