from django.shortcuts import render


def home(request):
    return render(
        request,
        "institutional/pages/home.html",
    )
