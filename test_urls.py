#-*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^file-server/', include('filer.server.urls')),
    url(r'^filer-main/', include('filer.urls')),
)
