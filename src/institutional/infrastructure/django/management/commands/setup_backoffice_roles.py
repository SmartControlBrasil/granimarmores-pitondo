from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from src.institutional.application.services.access_policy import ADMINISTRATOR
from src.institutional.application.services.access_policy import SALES_MANAGER
from src.institutional.application.services.access_policy import SALESPERSON
from src.institutional.application.services.access_policy import VIEWER

COMMERCIAL_WRITE_PERMISSIONS = {
    "add_opportunity",
    "change_opportunity",
    "delete_opportunity",
    "view_opportunity",
    "add_opportunityauditlog",
    "change_opportunityauditlog",
    "delete_opportunityauditlog",
    "view_opportunityauditlog",
    "add_quote",
    "change_quote",
    "delete_quote",
    "view_quote",
    "add_quoteitem",
    "change_quoteitem",
    "delete_quoteitem",
    "view_quoteitem",
    "view_quotesequence",
    "add_quotedocument",
    "change_quotedocument",
    "delete_quotedocument",
    "view_quotedocument",
    "add_quotedelivery",
    "change_quotedelivery",
    "delete_quotedelivery",
    "view_quotedelivery",
}

COMMERCIAL_SALES_PERMISSIONS = {
    "add_opportunity",
    "change_opportunity",
    "view_opportunity",
    "view_opportunityauditlog",
    "add_quote",
    "change_quote",
    "view_quote",
    "add_quoteitem",
    "change_quoteitem",
    "delete_quoteitem",
    "view_quoteitem",
    "add_quotedocument",
    "change_quotedocument",
    "view_quotedocument",
    "add_quotedelivery",
    "change_quotedelivery",
    "view_quotedelivery",
}

COMMERCIAL_READ_PERMISSIONS = {
    "view_opportunity",
    "view_opportunityauditlog",
    "view_quote",
    "view_quoteitem",
    "view_quotedocument",
    "view_quotedelivery",
}

GROUP_PERMISSIONS = {
    ADMINISTRATOR: {
        "view_contactrequest",
        "change_contactrequest",
        "assign_contactrequest",
        "add_contactrequestnote",
        "change_contactrequestnote",
        "delete_contactrequestnote",
        "view_contactrequestnote",
        "add_contactrequestauditlog",
        "change_contactrequestauditlog",
        "delete_contactrequestauditlog",
        "view_contactrequestauditlog",
        *COMMERCIAL_WRITE_PERMISSIONS,
    },
    SALES_MANAGER: {
        "view_contactrequest",
        "change_contactrequest",
        "assign_contactrequest",
        "add_contactrequestnote",
        "view_contactrequestnote",
        "view_contactrequestauditlog",
        *COMMERCIAL_WRITE_PERMISSIONS,
    },
    SALESPERSON: {
        "view_contactrequest",
        "change_contactrequest",
        "add_contactrequestnote",
        "view_contactrequestnote",
        "view_contactrequestauditlog",
        *COMMERCIAL_SALES_PERMISSIONS,
    },
    VIEWER: {
        "view_contactrequest",
        "view_contactrequestnote",
        "view_contactrequestauditlog",
        *COMMERCIAL_READ_PERMISSIONS,
    },
}


class Command(BaseCommand):
    help = "Cria/atualiza grupos e permissões do backoffice comercial."

    @transaction.atomic
    def handle(self, *args, **options):
        created_groups = 0
        updated_groups = 0
        for group_name, codenames in GROUP_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            permissions = Permission.objects.filter(
                content_type__app_label="institutional",
                codename__in=codenames,
            )
            group.permissions.set(permissions)
            if created:
                created_groups += 1
            else:
                updated_groups += 1

        if options.get("verbosity", 1) > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Perfis do backoffice configurados. Criados: {created_groups}. Atualizados: {updated_groups}.",
                ),
            )
