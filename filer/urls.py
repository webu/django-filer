#-*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from .views import ajax_upload

urlpatterns = patterns('',
    url(r'^direct_upload/$', ajax_upload, name='filer_direct_upload',),
)
