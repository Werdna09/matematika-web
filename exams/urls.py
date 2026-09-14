from django.urls import path

from . import views


app_name = "exams"

urlpatterns = [
    path("maturita/", views.exam_list, name="exam_list"),
    path("maturita/<slug:slug>/", views.exam_detail, name="exam_detail"),
    path(
        "maturita/<slug:slug>/uloha/<int:number>/",
        views.exam_task_detail,
        name="exam_task_detail",
    ),
]
