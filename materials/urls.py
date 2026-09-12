from django.urls import path

from . import views


app_name = "materials"

urlpatterns = [
    path(
        "rocnik/<slug:slug>/",
        views.grade_detail,
        name="grade_detail",
    ),
    path(
        "material/<slug:material_slug>/<slug:section_slug>/",
        views.material_section_detail,
        name="material_section_detail",
    ),
    path(
        "material/<slug:slug>/",
        views.material_detail,
        name="material_detail",
    ),
    path(
        "hledat/",
        views.search,
        name="search",
    ),
    path(
        "rocnik/<slug:grade_slug>/tema/<slug:topic_slug>/",
        views.topic_detail,
        name="topic_detail",
    ),
]