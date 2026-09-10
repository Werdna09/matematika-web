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
        "material/<slug:slug>/",
        views.material_detail,
        name="material_detail",
    ),
]