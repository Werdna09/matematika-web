from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Grade, Material, MaterialSection, MaterialType, Topic


PRACTICE_TYPE_SLUG = "procvicovani"


def _published_source_material(material):
    source = material.source_material

    if (
        source is not None
        and source.status == Material.Status.PUBLISHED
    ):
        return source

    return None


def _published_practice_material(material):
    if material.source_material_id:
        return None

    return (
        material.derived_materials
        .filter(
            status=Material.Status.PUBLISHED,
        )
        .filter(
            Q(material_type__slug=PRACTICE_TYPE_SLUG)
            | Q(material_type__name__iexact="Procvičování")
        )
        .prefetch_related("sections")
        .order_by("pk")
        .first()
    )


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
        Material.objects
        .select_related(
            "topic",
            "material_type",
            "source_material",
        )
        .prefetch_related(
            "grades",
            "tags",
            "sections",
        ),
        slug=slug,
        status=Material.Status.PUBLISHED,
    )

    sections = list(
        material.sections.all()
    )

    first_section = (
        sections[0]
        if sections
        else None
    )

    source_material = _published_source_material(
        material
    )

    practice_material = _published_practice_material(
        material
    )

    practice_first_section = (
        practice_material.sections.first()
        if practice_material is not None
        else None
    )

    is_practice = (
        material.material_type.slug
        == PRACTICE_TYPE_SLUG
    )

    return render(
        request,
        "materials/material_detail.html",
        {
            "material": material,
            "sections": sections,
            "first_section": first_section,
            "source_material": source_material,
            "practice_material": practice_material,
            "practice_first_section": practice_first_section,
            "is_practice": is_practice,
        },
    )


def material_section_detail(request, material_slug, section_slug):
    material = get_object_or_404(
        Material.objects
        .select_related(
            "topic",
            "material_type",
            "source_material",
        )
        .prefetch_related(
            "grades",
            "sections",
        ),
        slug=material_slug,
        status=Material.Status.PUBLISHED,
    )

    section = get_object_or_404(
        MaterialSection,
        material=material,
        slug=section_slug,
    )

    sections = list(
        material.sections.all()
    )

    current_index = sections.index(
        section
    )

    previous_section = (
        sections[current_index - 1]
        if current_index > 0
        else None
    )

    next_section = (
        sections[current_index + 1]
        if current_index < len(sections) - 1
        else None
    )

    source_material = _published_source_material(
        material
    )

    practice_material = _published_practice_material(
        material
    )

    practice_first_section = (
        practice_material.sections.first()
        if practice_material is not None
        else None
    )

    is_practice = (
        material.material_type.slug
        == PRACTICE_TYPE_SLUG
    )

    return render(
        request,
        "materials/material_section_detail.html",
        {
            "material": material,
            "section": section,
            "previous_section": previous_section,
            "next_section": next_section,
            "source_material": source_material,
            "practice_material": practice_material,
            "practice_first_section": practice_first_section,
            "is_practice": is_practice,
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
