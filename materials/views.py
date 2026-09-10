from django.shortcuts import get_object_or_404, render

from .models import Grade, Material, Topic


def grade_detail(request, slug):
    grade = get_object_or_404(Grade, slug=slug)

    topics = Topic.objects.filter(
        materials__grades=grade,
        materials__status=Material.Status.PUBLISHED,
    ).distinct()

    for topic in topics:
        topic.public_materials = topic.materials.filter(
            grades=grade,
            status=Material.Status.PUBLISHED,
        ).select_related("material_type")

    return render(
        request,
        "materials/grade_detail.html",
        {
            "grade": grade,
            "topics": topics,
        },
    )