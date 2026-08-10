from django.contrib import messages
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
                notification_sent = send_public_contact_notification(
                    customer,
                    contact_request,
                    request=request,
                )
                if notification_sent:
                    messages.success(
                        request,
                        "Mensagem enviada com sucesso. Em breve entraremos em contato.",
                    )
                else:
                    messages.error(
                        request,
                        "Não foi possível enviar sua mensagem no momento. "
                        "Tente novamente ou entre em contato pelo telefone/WhatsApp.",
                    )
                return redirect("institutional:contato")

    return render(request, page_template("contact"))


def politica_de_privacidade(request):
    return render(request, page_template("privacy_policy"))


def quotation(request):
    return render(request, page_template("quotation"))


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
