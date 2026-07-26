from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from src.institutional.application.services.contact_notification import (
    notify_contact_request,
)
from src.institutional.application.services.lead_management import record_lead_created
from src.institutional.presentation.forms import ContactRequestForm


PAGE_DIR = "institutional/pages/"


def page_template(name):
    return f"{PAGE_DIR}{name}.html"


def home(request):
    return render(request, page_template("home"))


def sobre(request):
    return render(request, page_template("about"))


def services(request):
    return render(request, page_template("services"))


def projects(request):
    return render(request, page_template("projects"))


def materials(request):
    return render(request, page_template("materials"))


def blog(request):
    return render(request, page_template("blog"))


def blog_article(request, slug):
    articles = {
        "escolher-pedra-bancada-cozinha": page_template("blog/escolher-pedra-bancada-cozinha"),
        "marmore-ou-granito-diferencas": page_template("blog/marmore-ou-granito-diferencas"),
        "cuidados-conservar-bancadas-pedra": page_template("blog/cuidados-conservar-bancadas-pedra"),
    }
    template_name = articles.get(slug)
    if template_name is None:
        return render(request, page_template("blog"), status=404)
    return render(request, template_name)


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR")


def contato(request):
    if request.method == "POST":
        form = ContactRequestForm(request.POST)
        if form.is_valid():
            contact_request = form.save(commit=False)
            contact_request.source_path = request.path
            contact_request.ip_address = _client_ip(request)
            contact_request.user_agent = request.META.get("HTTP_USER_AGENT", "")[:1000]
            contact_request.save()
            record_lead_created(contact_request)
            notify_contact_request(contact_request)
            messages.success(
                request,
                "Solicitação recebida. A equipe poderá usar os dados informados para retornar o contato.",
            )
            return redirect(reverse("institutional:contato"))

        for error in form.non_field_errors():
            messages.error(request, error)
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    else:
        form = ContactRequestForm()

    return render(request, page_template("contact"), {"form": form})


def quotation(request):
    return render(request, page_template("contact"))


def cozinhas(request):
    return render(request, page_template("cozinhas"))


def escadas(request):
    return render(request, page_template("escadas"))


def areas_gourmet(request):
    return render(request, page_template("areas_gourmet"))


def banheiros(request):
    return render(request, page_template("banheiros"))


def projetos_comerciais(request):
    return render(request, page_template("projetos_comerciais"))
