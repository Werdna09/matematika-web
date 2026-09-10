from django.shortcuts import get_object_or_404, render
from django.db.models import Q


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

    materials = Material.objects.none()

    if query:
        materials = (
            Material.objects.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(topic__name__icontains=query)
                | Q(material_type__name__icontains=query)
                | Q(tags__name__icontains=query)
                | Q(grades__name__icontains=query),
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
            .distinct()
        )

    return render(
        request,
        "materials/search.html",
        {
            "query": query,
            "materials": materials,
        },
    )