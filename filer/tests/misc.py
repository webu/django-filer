#-*- coding: utf-8 -*-
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File as DjangoFile
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import RequestFactory

from filer import settings as filer_settings
from filer.models.foldermodels import Folder
from filer.models.imagemodels import Image
from filer.tests.helpers import create_superuser, create_image
from filer.utils.folders import DefaultFolderGetter, get_default_folder_getter
from filer.validators import FileMimetypeValidator


class CustomFolderGetter(DefaultFolderGetter):
    @classmethod
    def USER_OWN_FOLDER(cls, request):
        if not request.user.is_authenticated():
            return None
        usersfolder = Folder.objects.get(name='USERS_FOLDERS')
        folder = Folder.objects.filter(owner=request.user, parent_id=usersfolder.pk)[0:1]
        if not folder:
            folder = Folder()
            folder.name = request.user.username
            folder.parent_id = usersfolder.pk
            folder.owner = request.user
            folder.save()
        else:
            folder = folder[0]
        return folder


class FilerDynamicFolderTest(TestCase):

    def setUp(self):
        self.old_conf = filer_settings.FILER_DEFAULT_FOLDER_GETTER
        filer_settings.FILER_DEFAULT_FOLDER_GETTER = 'filer.tests.misc.CustomFolderGetter'
        self.superuser = create_superuser()
        self.client.login(username='admin', password='secret')
        self.img = create_image()
        self.image_name = 'test_file.jpg'
        self.filename = os.path.join(settings.FILE_UPLOAD_TEMP_DIR, self.image_name)
        self.img.save(self.filename, 'JPEG')
        self.usersfolder = Folder()
        self.usersfolder.name = 'USERS_FOLDERS'
        self.usersfolder.owner = self.superuser
        self.usersfolder.save()

    def tearDown(self):
        self.client.logout()
        self.usersfolder.delete()
        filer_settings.FILER_DEFAULT_FOLDER_GETTER = self.old_conf

    def test_filer_dynamic_folder_creation(self):
        rf = RequestFactory()
        request = rf.get("/")
        request.session = {}
        request.user = self.superuser
        folder = get_default_folder_getter().get('USER_OWN_FOLDER', request)
        self.assertEqual(folder.name, self.superuser.username)

    def test_filer_dynamic_folder_ajax_upload_file(self):
        self.assertEqual(Image.objects.count(), 0)
        file_obj = DjangoFile(open(self.filename, 'rb'))
        url = reverse('filer_direct_upload')
        url += '?qqfile=%s&folder_key=%s' % (self.image_name, 'USER_OWN_FOLDER')
        response = self.client.post(
            url, data=file_obj.read(), content_type='application/octet-stream',
            **{'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        )
        self.assertEqual(Image.objects.count(), 1)
        img = Image.objects.all()[0]
        self.assertEqual(img.original_filename, self.image_name)
        self.assertEqual(img.folder.name, self.superuser.username)
        self.assertEqual(img.folder.parent_id, self.usersfolder.pk)


class FilerMimetypeLimitationTest(TestCase):

    def setUp(self):
        self.superuser = create_superuser()
        self.client.login(username='admin', password='secret')
        self.img = create_image()
        self.image_name = 'test_file.jpg'
        self.filename = os.path.join(settings.FILE_UPLOAD_TEMP_DIR, self.image_name)
        self.img.save(self.filename, 'JPEG')
        file_obj = DjangoFile(open(self.filename, 'rb'), name=self.image_name)
        self.image = Image.objects.create(
            owner=self.superuser,
            is_public=True,
            original_filename=self.image_name,
            file=file_obj
         )

    def tearDown(self):
        Image.objects.delete()
        self.client.logout()

    def test_filer_specific_mimetype_validator(self):
        jpeg_validator = FileMimetypeValidator(['image/jpeg',])
        try:
            jpeg_validator(self.image.pk)
        except ValidationError:
            self.failfast("FileMimetypeValidator() raised ValidationError unexpectedly !")
        
        png_validator = FileMimetypeValidator(['image/png',])
        with self.assertRaises(ValidationError):
            png_validator(self.image.pk)

    def test_filer_generic_mimetype_validator(self):
        image_validator = FileMimetypeValidator(['image/*',])
        try:
            image_validator(self.image.pk)
        except ValidationError:
            self.failfast("FileMimetypeValidator() raised ValidationError unexpectedly !")
        
        application_validator = FileMimetypeValidator(['application/*',])
        with self.assertRaises(ValidationError):
            application_validator(self.image.pk)
