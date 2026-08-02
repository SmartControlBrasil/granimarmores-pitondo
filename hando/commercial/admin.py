from django.contrib import admin

from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from commercial.models import ContactChannel
from commercial.models import LossReason
from commercial.models import ProjectType
from commercial.models import ServiceRegion

admin.site.register(CommercialSource)
admin.site.register(ProjectType)
admin.site.register(CommercialPartner)
admin.site.register(LossReason)
admin.site.register(ServiceRegion)
admin.site.register(ContactChannel)
