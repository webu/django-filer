# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import warnings

from django import forms
from django.contrib.admin.widgets import ForeignKeyRawIdWidget
from django.contrib.admin.sites import site
from django.core.urlresolvers import reverse
from django.db import models
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.six import text_type
from django.utils.translation import ugettext_lazy as _, ungettext_lazy


from filer.utils.compatibility import truncate_words
from filer.models import File
from filer.validators import FileMimetypeValidator
from filer import settings as filer_settings

import logging
logger = logging.getLogger(__name__)


class AdminFileWidget(ForeignKeyRawIdWidget):
    template = 'admin/filer/widgets/admin_file.html'
    choices = None

    def __init__(self, rel, site, *args, **kwargs):
        self.file_lookup_enabled = kwargs.pop('file_lookup_enabled', True)
        self.direct_upload_enabled = kwargs.pop('direct_upload_enabled', False)
        self.direct_upload_folder_key = kwargs.pop('direct_upload_folder_key', None)
        super(AdminFileWidget, self).__init__(rel, site, *args, **kwargs)

    def get_context(self, name, value, attrs=None):
        obj = self.obj_for_value(value)
        css_id = attrs.get('id', 'id_image_x')
        css_id_thumbnail_img = "%s_thumbnail_img" % css_id
        css_id_description_txt = "%s_description_txt" % css_id
        related_url = None
        if value:
            try:
                file_obj = File.objects.get(pk=value)
                related_url = file_obj.logical_folder.\
                                get_admin_directory_listing_url_path()
            except Exception as e:
                # catch exception and manage it. We can re-raise it for debugging
                # purposes and/or just logging it, provided user configured
                # proper logging configuration
                if filer_settings.FILER_ENABLE_LOGGING:
                    logger.error('Error while rendering file widget: %s',e)
                if filer_settings.FILER_DEBUG:
                    raise

        if self.direct_upload_enabled and self.direct_upload_folder_key:
            related_url = reverse(
                'admin:filer-directory_listing_by_key', 
                kwargs={'folder_key':self.direct_upload_folder_key}
            )
        elif not related_url:
            related_url = reverse('admin:filer-directory_listing-last')
        params = self.url_parameters()
        if params:
            lookup_url = '?' + '&amp;'.join(
                                ['%s=%s' % (k, v) for k, v in list(params.items())])
        else:
            lookup_url = ''
        if not 'class' in attrs:
            # The JavaScript looks for this hook.
            attrs['class'] = 'vForeignKeyRawIdAdminField'
        # rendering the super for ForeignKeyRawIdWidget on purpose here because
        # we only need the input and none of the other stuff that
        # ForeignKeyRawIdWidget adds
        hidden_input = super(ForeignKeyRawIdWidget, self).render(
                                                            name, value, attrs)
        filer_static_prefix = filer_settings.FILER_STATICMEDIA_PREFIX
        if not filer_static_prefix[-1] == '/':
            filer_static_prefix += '/'
        context = {
            'hidden_input': hidden_input,
            'lookup_url': '%s%s' % (related_url, lookup_url),
            'thumb_id': css_id_thumbnail_img,
            'span_id': css_id_description_txt,
            'object': obj,
            'lookup_name': name,
            'filer_static_prefix': filer_static_prefix,
            'clear_id': '%s_clear' % css_id,
            'id': css_id,
            'file_lookup_enabled': self.file_lookup_enabled,
            'direct_upload_enabled': self.direct_upload_enabled,
        }
        if self.direct_upload_enabled:
            context.update({
                'direct_upload_name':'%s_direct_upload' % name,
                'json_opts':json.dumps({
                    'msg':{
                        'error':text_type(_('An error occured during the file transfer.')),
                        'wait_sing':text_type(_('Please wait until the file is sent.')),
                        'wait_plur':text_type(_('Please wait until the %(nb_files)d files are sent.')),
                        'no_file_selected':text_type(_('No file selected')),
                    },
                    'url':reverse('filer_direct_upload'),
                    'direct_upload_folder_key':self.direct_upload_folder_key,
                }),
            })

        return context

    def render(self, name, value, attrs=None):
        context = self.get_context(name, value, attrs)
        html = render_to_string(self.template, context)
        return mark_safe(html)

    def label_for_value(self, value):
        obj = self.obj_for_value(value)
        return '&nbsp;<strong>%s</strong>' % truncate_words(obj, 14)

    def obj_for_value(self, value):
        try:
            key = self.rel.get_related_field().name
            obj = self.rel.to._default_manager.get(**{key: value})
        except:
            obj = None
        return obj

    @property
    def media(self):
        kwargs = {
            'css': {
                'all':(filer_settings.FILER_STATICMEDIA_PREFIX + 'css/admin_style.css',),
            },
            'js': [filer_settings.FILER_STATICMEDIA_PREFIX + 'js/widget.js', ],
        }
        if self.file_lookup_enabled:
            kwargs['js'].append(filer_settings.FILER_STATICMEDIA_PREFIX + 'js/popup_handling.js')
        return forms.Media(**kwargs)


class AdminFileFormField(forms.ModelChoiceField):
    widget = AdminFileWidget

    def __init__(self, rel, queryset, to_field_name, *args, **kwargs):
        self.rel = rel
        self.queryset = queryset
        self.to_field_name = to_field_name
        self.max_value = None
        self.min_value = None
        kwargs.pop('widget', None)
        widgetkwargs = {
            'file_lookup_enabled': kwargs.pop('file_lookup_enabled', True),
            'direct_upload_enabled': kwargs.pop('direct_upload_enabled', False),
            'direct_upload_folder_key': kwargs.pop('direct_upload_folder_key', None),
        }

        super(AdminFileFormField, self).__init__(
            queryset, 
            widget=self.widget(rel, site, **widgetkwargs), 
            *args, **kwargs
        )

        if not self.help_text:
            validators = self.validators + self.rel.field.validators
            for validator in validators:
                if isinstance(validator, FileMimetypeValidator):
                    if len(validator.mimetypes) > 1:
                        mimetypes = '%s" and "%s' % (
                            '", "'.join(validator.mimetypes[0:-1]),
                            validator.mimetypes[-1]
                        )
                    else:
                        mimetypes = validator.mimetypes[0]
                    self.help_text = ungettext_lazy(
                        'Only files of type "%(mimetypes)s" are allowed',
                        'Only files of types "%(mimetypes)s" are allowed',
                        len(validator.mimetypes)
                    ) % {
                        'mimetypes': mimetypes
                    }
                    break

    def widget_attrs(self, widget):
        widget.required = self.required
        return {}


class FilerFileField(models.ForeignKey):
    default_model_class =  File

    def __init__(self, **kwargs):
        # We hard-code the `to` argument for ForeignKey.__init__
        if "to" in kwargs.keys():
            old_to = kwargs.pop("to")
            msg = "%s can only be a ForeignKey to %s; %s passed" % (
                self.__class__.__name__, self.default_model_class.__name__, old_to
            )
            warnings.warn(msg, SyntaxWarning)
        kwargs['to'] = self.default_model_class

        default_keys = (
            'form_class', 'file_lookup_enabled', 
            'direct_upload_enabled', 'direct_upload_folder_key'
        )
        self.default_formfield_kwargs = {'form_class': AdminFileFormField, }
        for key in default_keys:
            default_key = 'default_%s' % key
            if default_key in kwargs:
                self.default_formfield_kwargs[key] = kwargs.pop(default_key)
        return super(FilerFileField, self).__init__(**kwargs)

    @property
    def default_form_class(self):
        """
        Returns self.default_formfield_kwargs.get('default_form_class', AdminFileFormField)
        This methods stands here for backward compatibily if some developpers 
        used file_field.default_form_class
        """
        warnings.warn(
            "<FilerFileField instance>.default_form_class is deprecated. "\
            "Please use <FilerFileField instance>.default_formfield_kwargs.get(\'default_form_class\')",
            DeprecationWarning
        )
        return self.default_formfield_kwargs.get('default_form_class', AdminFileFormField)

    def formfield(self, **kwargs):
        # This is a fairly standard way to set up some defaults
        # while letting the caller override them.
        defaults = {'rel': self.rel,}
        defaults.update(self.default_formfield_kwargs)
        defaults.update(kwargs)
        return super(FilerFileField, self).formfield(**defaults)

    def south_field_triple(self):
        "Returns a suitable description of this field for South."
        # We'll just introspect ourselves, since we inherit.
        from south.modelsinspector import introspector
        field_class = "django.db.models.fields.related.ForeignKey"
        args, kwargs = introspector(self)
        # That's our definition!
        return (field_class, args, kwargs)
