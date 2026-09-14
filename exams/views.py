from django.shortcuts import get_object_or_404, render

from .models import Exam, ExamTask


def exam_list(request):
    exams = Exam.objects.filter(
        status=Exam.Status.PUBLISHED,
    ).prefetch_related("tasks")

    return render(
        request,
        "exams/exam_list.html",
        {
            "exams": exams,
        },
    )


def exam_detail(request, slug):
    exam = get_object_or_404(
        Exam.objects.prefetch_related("tasks"),
        slug=slug,
        status=Exam.Status.PUBLISHED,
    )

    tasks = list(exam.tasks.all())
    first_task = tasks[0] if tasks else None

    return render(
        request,
        "exams/exam_detail.html",
        {
            "exam": exam,
            "tasks": tasks,
            "first_task": first_task,
        },
    )


def exam_task_detail(request, slug, number):
    exam = get_object_or_404(
        Exam.objects.prefetch_related("tasks"),
        slug=slug,
        status=Exam.Status.PUBLISHED,
    )

    task = get_object_or_404(
        ExamTask,
        exam=exam,
        number=number,
    )

    tasks = list(exam.tasks.all())
    current_index = tasks.index(task)

    previous_task = (
        tasks[current_index - 1]
        if current_index > 0
        else None
    )

    next_task = (
        tasks[current_index + 1]
        if current_index < len(tasks) - 1
        else None
    )

    return render(
        request,
        "exams/exam_task_detail.html",
        {
            "exam": exam,
            "task": task,
            "tasks": tasks,
            "previous_task": previous_task,
            "next_task": next_task,
        },
    )
