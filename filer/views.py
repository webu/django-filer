#-*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
from django import forms
from django.contrib.admin import widgets
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.forms.models import modelform_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils import six
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from .models import Folder, Image, Clipboard, tools, FolderRoot
from . import settings as filer_settings
from .utils.files import handle_upload, UploadException
from .utils.loader import load_object


class NewFolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ('name',)
        widgets = {
            'name': widgets.AdminTextInputWidget,
        }


def popup_status(request):
    return '_popup' in request.REQUEST or 'pop' in request.REQUEST


def selectfolder_status(request):
    return 'select_folder' in request.REQUEST


def popup_param(request, separator="?"):
    if popup_status(request):
        return "%s_popup=1" % separator
    else:
        return ""


def selectfolder_param(request, separator="&"):
    if selectfolder_status(request):
        return "%sselect_folder=1" % separator
    else:
        return ""


def _userperms(item, request):
    r = []
    ps = ['read', 'edit', 'add_children']
    for p in ps:
        attr = "has_%s_permission" % p
        if hasattr(item, attr):
            x = getattr(item, attr)(request)
            if x:
                r.append(p)
    return r


@login_required
def edit_folder(request, folder_id):
    # TODO: implement edit_folder view
    folder = None
    return render_to_response('admin/filer/folder/folder_edit.html', {
        'folder': folder,
        'is_popup': popup_status(request),
        'select_folder': selectfolder_status(request),
    }, context_instance=RequestContext(request))


@login_required
def edit_image(request, folder_id):
    # TODO: implement edit_image view
    folder = None
    return render_to_response('filer/image_edit.html', {
        'folder': folder,
        'is_popup': popup_status(request),
        'select_folder': selectfolder_status(request),
    }, context_instance=RequestContext(request))


@login_required
def make_folder(request, folder_id=None):
    if not folder_id:
        folder_id = request.REQUEST.get('parent_id', None)
    if folder_id:
        folder = Folder.objects.get(id=folder_id)
    else:
        folder = None

    if request.user.is_superuser:
        pass
    elif folder is None:
        # regular users may not add root folders unless configured otherwise
        if not filer_settings.FILER_ALLOW_REGULAR_USERS_TO_ADD_ROOT_FOLDERS:
            raise PermissionDenied
    elif not folder.has_add_children_permission(request):
        # the user does not have the permission to add subfolders
        raise PermissionDenied

    if request.method == 'POST':
        new_folder_form = NewFolderForm(request.POST)
        if new_folder_form.is_valid():
            new_folder = new_folder_form.save(commit=False)
            if (folder or FolderRoot()).contains_folder(new_folder.name):
                new_folder_form._errors['name'] = new_folder_form.error_class([_('Folder with this name already exists.')])
            else:
                new_folder.parent = folder
                new_folder.owner = request.user
                new_folder.save()
                return render_to_response('admin/filer/dismiss_popup.html')
    else:
        new_folder_form = NewFolderForm()
    return render_to_response('admin/filer/folder/new_folder_form.html', {
        'new_folder_form': new_folder_form,
        'is_popup': popup_status(request),
        'select_folder': selectfolder_status(request),
    }, context_instance=RequestContext(request))


class UploadFileForm(forms.ModelForm):
    class Meta:
        model = Image
        exclude = ()


@login_required
def upload(request):
    return render_to_response('filer/upload.html', {
                    'title': 'Upload files',
                    'is_popup': popup_status(request),
                    'select_folder': selectfolder_status(request),
                    }, context_instance=RequestContext(request))


@login_required
def paste_clipboard_to_folder(request):
    if request.method == 'POST':
        folder = Folder.objects.get(id=request.POST.get('folder_id'))
        clipboard = Clipboard.objects.get(id=request.POST.get('clipboard_id'))
        if folder.has_add_children_permission(request):
            tools.move_files_from_clipboard_to_folder(clipboard, folder)
            tools.discard_clipboard(clipboard)
        else:
            raise PermissionDenied
    return HttpResponseRedirect('%s?order_by=-modified_at%s%s' % (
                                request.REQUEST.get('redirect_to', ''),
                                popup_param(request, separator='&'),
                                selectfolder_param(request)))


@login_required
def discard_clipboard(request):
    if request.method == 'POST':
        clipboard = Clipboard.objects.get(id=request.POST.get('clipboard_id'))
        tools.discard_clipboard(clipboard)
    return HttpResponseRedirect('%s%s%s' % (
                                request.POST.get('redirect_to', ''),
                                popup_param(request),
                                selectfolder_param(request)))


@login_required
def delete_clipboard(request):
    if request.method == 'POST':
        clipboard = Clipboard.objects.get(id=request.POST.get('clipboard_id'))
        tools.delete_clipboard(clipboard)
    return HttpResponseRedirect('%s%s%s' % (
                                request.POST.get('redirect_to', ''),
                                popup_param(request),
                                selectfolder_param(request)))


@login_required
def clone_files_from_clipboard_to_folder(request):
    if request.method == 'POST':
        clipboard = Clipboard.objects.get(id=request.POST.get('clipboard_id'))
        folder = Folder.objects.get(id=request.POST.get('folder_id'))
        tools.clone_files_from_clipboard_to_folder(clipboard, folder)
    return HttpResponseRedirect('%s%s%s' % (
                                request.POST.get('redirect_to', ''),
                                popup_param(request),
                                selectfolder_param(request)))

@csrf_exempt
@login_required
def ajax_upload(request):
    mimetype = "application/json"
    response_params = {
        'content_type': mimetype,
    }
    try:
        if not request.is_ajax():
            raise UploadException("Request is not an AJAX request.")

        upload, filename, is_raw = handle_upload(request)
        filename = filename.split('\\')[-1].split('/')[-1]
        # find the file type
        for filer_class in filer_settings.FILER_FILE_MODELS:
            FileSubClass = load_object(filer_class)
            #TODO: What if there are more than one that qualify?
            if FileSubClass.matches_file_type(filename, upload, request):
                FileForm = modelform_factory(
                    model=FileSubClass,
                    fields=('original_filename', 'owner', 'file')
                )
                break
        uploadform = FileForm({'original_filename': filename,
                               'owner': request.user.pk},
                              {'file': upload})
        if uploadform.is_valid():
            file_obj = uploadform.save(commit=False)
            # Enforce the FILER_IS_PUBLIC_DEFAULT
            file_obj.is_public = filer_settings.FILER_IS_PUBLIC_DEFAULT
            folder_key = request.GET.get('folder_key', None)
            if folder_key :
                from .utils.folders import get_default_folder_getter
                folder = get_default_folder_getter().get(folder_key, request)
                if folder:
                    if not folder.has_add_children_permission(request):
                        # the user does not have the permission to add elements into the folder
                        raise PermissionDenied
                    file_obj.folder = folder
            file_obj.save()
            json_response = {
                'thumbnail': file_obj.icons['48'],
                'label': str(file_obj),
                'pk':file_obj.pk,
            }
            return HttpResponse(json.dumps(json_response), **response_params)
        else:
            form_errors = '; '.join(['%s: %s' % (
                field,
                ', '.join(errors)) for field, errors in list(uploadform.errors.items())
            ])
            raise UploadException("AJAX request not valid: form invalid '%s'" % (form_errors,))
    except UploadException as e:
        return HttpResponse(json.dumps({'error': str(e)}),
                            **response_params)
