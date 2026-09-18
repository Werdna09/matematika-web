from django.shortcuts import get_object_or_404, render

from .models import SideQuest, SideQuestSection


def sidequest_list(request):
    sidequests = (
        SideQuest.objects
        .filter(
            status=SideQuest.Status.PUBLISHED,
        )
        .prefetch_related(
            "tags",
            "sections",
        )
    )

    return render(
        request,
        "sidequests/sidequest_list.html",
        {
            "sidequests": sidequests,
        },
    )


def sidequest_detail(request, slug):
    sidequest = get_object_or_404(
        SideQuest.objects
        .prefetch_related(
            "tags",
            "sections",
        ),
        slug=slug,
        status=SideQuest.Status.PUBLISHED,
    )

    sections = list(
        sidequest.sections.all()
    )

    first_section = (
        sections[0]
        if sections
        else None
    )

    return render(
        request,
        "sidequests/sidequest_detail.html",
        {
            "sidequest": sidequest,
            "sections": sections,
            "first_section": first_section,
        },
    )


def sidequest_section_detail(
    request,
    sidequest_slug,
    section_slug,
):
    sidequest = get_object_or_404(
        SideQuest.objects.prefetch_related(
            "sections",
            "tags",
        ),
        slug=sidequest_slug,
        status=SideQuest.Status.PUBLISHED,
    )

    section = get_object_or_404(
        SideQuestSection,
        sidequest=sidequest,
        slug=section_slug,
    )

    sections = list(
        sidequest.sections.all()
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

    return render(
        request,
        "sidequests/sidequest_section_detail.html",
        {
            "sidequest": sidequest,
            "section": section,
            "previous_section": previous_section,
            "next_section": next_section,
        },
    )
