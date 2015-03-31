# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from importlib import import_module
from .. import settings as filer_settings

def get_default_folder_getter():
    path = filer_settings.FILER_DEFAULT_FOLDER_GETTER
    getter = None
    if path:
        path = path.split('.')
        classname = path.pop()
        module_path =  '.'.join(path)
        if module_path ==  'filer.utils.folders':
            module = globals()
        else:
            module = import_module(module_path)
        getter = getattr(module, classname, None)
    if not getter:
        raise Exception('FILER_DEFAULT_FOLDER_GETTER improperly configured')
    return getter


class DefaultFolderGetter(object):
    """
    Default Folder getter to configure some "dynamic" folders
    You just have to add a method named as the key attr. exemple :

    @classmethod
    def USER_OWN_FOLDER(cls, request):
        if not request.user.is_authenticated():
            return None
        folder = Folder.objects.filter(owner=request.user, parent_id=USERS_FOLDER_PK)[0:1]
        if not folder:
            folder = Folder()
            folder.name = user.username
            folder.parent_id = USERS_FOLDER_PK
            folder.owner = request.user
            folder.save()
        else:
            folder = folder[0]
        return folder
    """

    @classmethod
    def get(cls, key, request):
        if hasattr(cls, key):
            getter = getattr(cls, key)
            if callable(getter):
                return getter(request)
        return None
