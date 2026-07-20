from django.shortcuts import render


def home(request):
    return render(request, "institutional/pages/home.html")


def about(request):
    return render(request, "institutional/pages/about.html")


def services(request):
    return render(request, "institutional/pages/services.html")


def projects(request):
    return render(request, "institutional/pages/projects.html")


def materials(request):
    return render(request, "institutional/pages/materials.html")


def blog(request):
    return render(request, "institutional/pages/blog.html")


def contact(request):
    return render(request, "institutional/pages/contact.html")


def quotation(request):
    return render(request, "institutional/pages/quotation.html")
