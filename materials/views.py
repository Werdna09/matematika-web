from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Grade, Material, MaterialType, Topic


def grade_detail(request, slug):
    grade = get_object_or_404(Grade, slug=slug)

    topics = (
        Topic.objects.filter(
            materials__grades=grade,
            materials__status=Material.Status.PUBLISHED,
        )
        .distinct()
    )

    return render(
        request,
        "materials/grade_detail.html",
        {
            "grade": grade,
            "topics": topics,
        },
    )

def topic_detail(request, grade_slug, topic_slug):
    grade = get_object_or_404(Grade, slug=grade_slug)
    topic = get_object_or_404(Topic, slug=topic_slug)

    material_types = (
        MaterialType.objects.filter(
            materials__topic=topic,
            materials__grades=grade,
            materials__status=Material.Status.PUBLISHED,
        )
        .distinct()
    )

    for material_type in material_types:
        material_type.public_materials = (
            material_type.materials.filter(
                topic=topic,
                grades=grade,
                status=Material.Status.PUBLISHED,
            )
            .prefetch_related("grades", "tags")
            .distinct()
        )

    return render(
        request,
        "materials/topic_detail.html",
        {
            "grade": grade,
            "topic": topic,
            "material_types": material_types,
        },
    )

def material_detail(request, slug):
    material = get_object_or_404(
        Material,
        slug=slug,
        status=Material.Status.PUBLISHED,
    )

    return render(
        request,
        "materials/material_detail.html",
        {
            "material": material,
        },
    )

def search(request):
    query = request.GET.get("q", "").strip()

    selected_grade = request.GET.get("grade", "")
    selected_topic = request.GET.get("topic", "")
    selected_type = request.GET.get("type", "")

    materials = (
        Material.objects.filter(
            status=Material.Status.PUBLISHED,
        )
        .select_related(
            "topic",
            "material_type",
        )
        .prefetch_related(
            "grades",
            "tags",
        )
    )

    if query:
        materials = materials.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(topic__name__icontains=query)
            | Q(material_type__name__icontains=query)
            | Q(tags__name__icontains=query)
            | Q(grades__name__icontains=query)
        )

    if selected_grade:
        materials = materials.filter(
            grades__id=selected_grade
        )

    if selected_topic:
        materials = materials.filter(
            topic__id=selected_topic
        )

    if selected_type:
        materials = materials.filter(
            material_type__id=selected_type
        )

    materials = materials.distinct()

    grades = Grade.objects.all()
    topics = Topic.objects.all()
    material_types = MaterialType.objects.all()

    return render(
        request,
        "materials/search.html",
        {
            "query": query,
            "materials": materials,

            "grades": grades,
            "topics": topics,
            "material_types": material_types,

            "selected_grade_id": (
                int(selected_grade)
                if selected_grade.isdigit()
                else None
            ),

            "selected_topic_id": (
                int(selected_topic)
                if selected_topic.isdigit()
                else None
            ),

            "selected_type_id": (
                int(selected_type)
                if selected_type.isdigit()
                else None
            ),
        },
    )