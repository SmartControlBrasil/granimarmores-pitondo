from django import forms
from django.contrib.auth import get_user_model

from after_sales.models import AfterSalesCase
from after_sales.models import MediaUsageConsent
from after_sales.models import WarrantyRecord
from commercial.lead_models import Lead
from customers.models import Customer
from materials.models import Material
from materials.models import MaterialSlab
from media_library.models import BeforeAfterPair
from media_library.models import CollectionType
from media_library.models import MediaAsset
from media_library.models import MediaCategory
from media_library.models import MediaCollection
from media_library.models import MediaTag
from media_library.models import PublicationCandidate
from media_library.models import PublicationChannel
from media_library.models import TechnicalReviewStatus
from production.models import DeliverySchedule
from production.models import InstallationSchedule
from production.models import ProductionOrder
from production.models import ProductionPiece
from production.models import ProductionStage
from production.models import SalesOrder
from quotes.models import Quote

User = get_user_model()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MediaUploadForm(forms.Form):
    file = forms.FileField()
    title = forms.CharField(required=False, max_length=220)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    alt_text = forms.CharField(required=False, max_length=255)
    category = forms.ModelChoiceField(queryset=MediaCategory.objects.filter(is_active=True), required=False)
    tags = forms.ModelMultipleChoiceField(
        queryset=MediaTag.objects.filter(is_active=True),
        required=False,
    )
    capture_date = forms.DateField(required=False)
    customer = forms.ModelChoiceField(queryset=Customer.objects.filter(is_active=True), required=False)
    lead = forms.ModelChoiceField(queryset=Lead.objects.all(), required=False)
    quote = forms.ModelChoiceField(queryset=Quote.objects.all(), required=False)
    sales_order = forms.ModelChoiceField(queryset=SalesOrder.objects.all(), required=False)
    production_order = forms.ModelChoiceField(queryset=ProductionOrder.objects.all(), required=False)
    production_piece = forms.ModelChoiceField(queryset=ProductionPiece.objects.all(), required=False)
    production_stage = forms.ModelChoiceField(queryset=ProductionStage.objects.filter(is_active=True), required=False)
    material = forms.ModelChoiceField(queryset=Material.objects.filter(is_active=True), required=False)
    slab = forms.ModelChoiceField(queryset=MaterialSlab.objects.filter(is_active=True), required=False)
    delivery_schedule = forms.ModelChoiceField(queryset=DeliverySchedule.objects.all(), required=False)
    installation_schedule = forms.ModelChoiceField(queryset=InstallationSchedule.objects.all(), required=False)
    after_sales_case = forms.ModelChoiceField(queryset=AfterSalesCase.objects.all(), required=False)
    warranty = forms.ModelChoiceField(queryset=WarrantyRecord.objects.all(), required=False)
    consent = forms.ModelChoiceField(queryset=MediaUsageConsent.objects.all(), required=False)
    reuse_duplicate = forms.BooleanField(
        required=False,
        label="Reutilizar arquivo existente se checksum idêntico",
    )


class MediaMultiUploadForm(forms.Form):
    files = forms.FileField(widget=MultipleFileInput(attrs={"multiple": True}))
    category = forms.ModelChoiceField(queryset=MediaCategory.objects.filter(is_active=True), required=False)
    tags = forms.ModelMultipleChoiceField(
        queryset=MediaTag.objects.filter(is_active=True),
        required=False,
    )
    customer = forms.ModelChoiceField(queryset=Customer.objects.filter(is_active=True), required=False)
    sales_order = forms.ModelChoiceField(queryset=SalesOrder.objects.all(), required=False)
    production_order = forms.ModelChoiceField(queryset=ProductionOrder.objects.all(), required=False)
    installation_schedule = forms.ModelChoiceField(queryset=InstallationSchedule.objects.all(), required=False)
    after_sales_case = forms.ModelChoiceField(queryset=AfterSalesCase.objects.all(), required=False)
    material = forms.ModelChoiceField(queryset=Material.objects.filter(is_active=True), required=False)
    reuse_duplicate = forms.BooleanField(required=False)


class ClassifyForm(forms.Form):
    category = forms.ModelChoiceField(queryset=MediaCategory.objects.filter(is_active=True))
    tags = forms.ModelMultipleChoiceField(
        queryset=MediaTag.objects.filter(is_active=True),
        required=False,
    )
    title = forms.CharField(required=False, max_length=220)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    alt_text = forms.CharField(required=False, max_length=255)


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[
            (TechnicalReviewStatus.APPROVED, "Aprovar tecnicamente"),
            (TechnicalReviewStatus.REJECTED, "Rejeitar"),
            (TechnicalReviewStatus.PENDING, "Manter pendente"),
        ],
    )
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class NotesForm(forms.Form):
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ReasonForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))


class CollectionForm(forms.ModelForm):
    class Meta:
        model = MediaCollection
        fields = [
            "name",
            "description",
            "collection_type",
            "customer",
            "sales_order",
            "production_order",
            "after_sales_case",
        ]


class CollectionItemForm(forms.Form):
    asset = forms.ModelChoiceField(queryset=MediaAsset.objects.exclude(status="deleted"))
    caption = forms.CharField(required=False, max_length=255)
    is_cover = forms.BooleanField(required=False)
    display_order = forms.IntegerField(required=False, initial=0)


class BeforeAfterForm(forms.ModelForm):
    class Meta:
        model = BeforeAfterPair
        fields = [
            "before_asset",
            "after_asset",
            "title",
            "description",
            "collection",
            "customer",
            "sales_order",
            "approved_for_portfolio",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        images = MediaAsset.objects.filter(media_type="image").exclude(status="deleted")
        self.fields["before_asset"].queryset = images
        self.fields["after_asset"].queryset = images


class PublicationCandidateForm(forms.ModelForm):
    class Meta:
        model = PublicationCandidate
        fields = ["asset", "channel", "planned_date", "caption", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = MediaAsset.objects.exclude(status__in=["deleted", "rejected"])
        self.fields["channel"].choices = PublicationChannel.choices
