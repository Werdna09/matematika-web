from django.urls import path

from . import views


app_name = "sidequests"


urlpatterns = [
    path(
        "bokovky/",
        views.sidequest_list,
        name="sidequest_list",
    ),
    path(
        "bokovky/<slug:slug>/",
        views.sidequest_detail,
        name="sidequest_detail",
    ),
    path(
        "bokovky/<slug:sidequest_slug>/kapitola/<slug:section_slug>/",
        views.sidequest_section_detail,
        name="sidequest_section_detail",
    ),
]
