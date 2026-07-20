from django.contrib import messages
from django.shortcuts import render


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
    required_fields = ["nome", "telefone", "cidade", "ambiente", "mensagem"]
    if request.method == "POST":
        missing_fields = [field for field in required_fields if not request.POST.get(field, "").strip()]
        consent = request.POST.get("privacidade")
        website = request.POST.get("website", "").strip()

        if website:
            messages.error(request, "Não foi possível processar a solicitação. Tente novamente.")
        elif missing_fields:
            messages.error(request, "Preencha os campos obrigatórios para solicitar a avaliação.")
        elif not consent:
            messages.error(request, "Confirme o consentimento para contato antes de enviar.")
        else:
            messages.success(request, "Solicitação recebida. A equipe poderá usar os dados informados para retornar o contato.")

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
