from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.shortcuts import render

from src.institutional.application.contact_requests import (
    PublicContactIdentityConflict,
)
from src.institutional.application.contact_requests import (
    PublicContactValidationError,
)
from src.institutional.application.contact_requests import (
    persist_public_contact_request,
)
from src.institutional.application.contact_requests import (
    record_public_contact_identity_conflict,
)
from src.institutional.application.contact_requests import (
    send_public_contact_notification,
)
from src.institutional.application.contact_requests import (
    validate_public_contact_request,
)


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


def contato(request):
    if request.method == "POST":
        website = request.POST.get("website", "").strip()

        if website:
            messages.success(request, "Solicitação recebida. Nossa equipe entrará em contato.")
            return redirect("institutional:contato")

        try:
            contact_request = validate_public_contact_request(request.POST)
        except PublicContactValidationError as exc:
            messages.error(request, str(exc))
        else:
            try:
                customer, _ = persist_public_contact_request(
                    contact_request,
                    request=request,
                )
            except PublicContactIdentityConflict as exc:
                record_public_contact_identity_conflict(
                    contact_request,
                    request=request,
                )
                messages.error(request, str(exc))
            else:
                transaction.on_commit(
                    lambda: send_public_contact_notification(
                        customer,
                        contact_request,
                        request=request,
                    ),
                )
                messages.success(
                    request,
                    "Solicitação recebida. Nossa equipe entrará em contato.",
                )
                return redirect("institutional:contato")

    return render(request, page_template("contact"))


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
