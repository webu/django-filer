# -*- coding: utf-8 -*-
from __future__ import unicode_literals

try:
    from magic import from_buffer
    def get_mime_type(fp):
        return from_buffer(fp.read(1024), mime=True)
except ImportError:
    import warnings
    warnings.warn((
        'Can not import python-magic. '
        'Mime detection will be based on file\'s extension : this is not safe at all.'
        'Please install python-magic for better mime type detection based on file\'s content.'
    ))
    
    from mimetypes import guess_type
    def get_mime_type(fp):
        (mime, encoding) = guess_type(fp.name, strict=False)
        return mime

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from filer.models import File

class FileMimetypeValidator(object):
    def __init__(self, mimetypes):
        self.mimetypes = mimetypes

    def __call__(self, value):
        if not value:
            return

        try:
            f = File.objects.get(pk=value)
        except File.DoesNotExist:
            raise ValidationError(_('This value is not a valid file'))

        try:
            mime = get_mime_type(f.file)
        except AttributeError:
            mime = None

        if not mime:
            raise ValidationError(_('This value is not a valid file'))

        wildcard_mime = '%s/*' % mime.split('/')[0]

        if mime not in self.mimetypes and wildcard_mime not in self.mimetypes:
            msg = _('%(file)s is not a valid file. Allowed file types are : %(types)s') % {
                'file': f,
                'types': ', '.join(self.mimetypes),
            }
            raise ValidationError(msg)
