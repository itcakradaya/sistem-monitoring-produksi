from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, path
from django.utils import timezone
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from produksi_monitoring.models import ItemDescription, ProsesProduksi, Ruangan, Mesin, Operator

admin.site.index_title = "Manajemen Proses Produksi"


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ('nama', 'kategori')
    search_fields = ('nama', 'kategori')


@admin.register(Ruangan)
class RuanganAdmin(admin.ModelAdmin):
    list_display = ('nama', 'kode_ruangan', 'tahap_berikutnya')
    search_fields = ('nama', 'kode_ruangan')
    prepopulated_fields = {'link_khusus': ('nama',)}


@admin.register(Mesin)
class MesinAdmin(admin.ModelAdmin):
    list_display = ('kode_mesin', 'nama_mesin')
    search_fields = ('kode_mesin', 'nama_mesin')


### ✅ Form Kustom untuk Proses Produksi
class ProsesProduksiForm(forms.ModelForm):
    class Meta:
        model = ProsesProduksi
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default ruangan ke Penimbangan saat create
        if not self.instance.pk:
            try:
                ruang_penimbangan = Ruangan.objects.get(nama__icontains="penimbangan")
                self.fields['ruangan'].initial = ruang_penimbangan
            except Ruangan.DoesNotExist:
                pass

        if not self.instance.pk:
            self.fields['status'].initial = "Menunggu"
            self.fields['status'].widget.attrs.update({
                'readonly': True,
                'style': 'background-color: #e9ecef; cursor: not-allowed;'
            })

    def clean_nomor_batch(self):
        nomor_batch = self.cleaned_data.get('nomor_batch')
        if ProsesProduksi.objects.exclude(pk=self.instance.pk).filter(nomor_batch=nomor_batch).exists():
            raise ValidationError("Nomor batch ini sudah digunakan. Silakan gunakan nomor batch lain.")
        return nomor_batch


@admin.register(ItemDescription)
class ItemDescriptionAdmin(admin.ModelAdmin):
    search_fields = ['description', 'barcode']


### ✅ Aksi Kustom
@admin.action(description="Pilih Ruangan & Operator Berikutnya")
def pilih_ruangan_dan_operator(modeladmin, request, queryset):
    batch_to_move = []
    for proses in queryset:
        if not proses.status.startswith("Selesai Diproses di"):
            modeladmin.message_user(request, "Hanya batch yang telah selesai diproses di ruangan yang bisa dipindahkan.", level="error")
            return
        batch_to_move.append(proses.pk)

    request.session['batch_to_move'] = batch_to_move
    return redirect(reverse("admin:pilih_ruangan_proses"))


### ✅ VIEW untuk pemilihan ruangan & operator
@admin.site.admin_view
def pilih_ruangan_proses(request):
    batch_ids = request.session.get('batch_to_move', [])

    if not batch_ids:
        messages.error(request, "Tidak ada batch yang bisa dipindahkan.")
        return redirect("admin:produksi_monitoring_prosesproduksi_changelist")

    batch_list = ProsesProduksi.objects.filter(pk__in=batch_ids)

    if request.method == "POST":
        ruangan_id = request.POST.get("ruangan_tujuan")
        operator_id = request.POST.get("operator_id")

        if not ruangan_id or not operator_id:
            messages.error(request, "Ruangan dan Operator harus dipilih!")
            return redirect(request.path)

        ruangan_tujuan = get_object_or_404(Ruangan, id=ruangan_id)
        operator_tujuan = get_object_or_404(Operator, id=operator_id)

        for produksi in batch_list:
            produksi.ruangan = ruangan_tujuan
            produksi.operator = operator_tujuan
            produksi.status = "Menunggu"
            produksi.waktu_mulai_produksi = None
            produksi.save()

        messages.success(request, f"{len(batch_list)} batch berhasil dipindahkan ke {ruangan_tujuan.nama}.")
        return redirect("admin:produksi_monitoring_prosesproduksi_changelist")

    return render(request, "admin/pilih_ruangan.html", {
        "batch_list": batch_list,
        "ruangan_list": Ruangan.objects.exclude(nama__icontains="penimbangan"),
        "operator_list": Operator.objects.all(),
    })


### ✅ Admin: ProsesProduksi
@admin.register(ProsesProduksi)
class ProsesProduksiAdmin(admin.ModelAdmin):
    autocomplete_fields = ['nama', 'operator']
    search_fields = ['nama__description', 'nomor_batch']
    form = ProsesProduksiForm
    list_display = (
        'nomor_batch', 'nama', 'ruangan', 'status_display', 'jumlah',
        'satuan', 'waktu_dibuat', 'get_waktu_selesai', 'tahap_berikutnya', 'tombol_pindah'
    )
    list_filter = ('status', 'ruangan')
    ordering = ('-waktu_dibuat',)
    readonly_fields = ('waktu_selesai',)
    actions = [pilih_ruangan_dan_operator]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("pilih_ruangan_proses/", self.admin_site.admin_view(pilih_ruangan_proses), name="pilih_ruangan_proses"),
        ]
        return custom_urls + urls

    def tombol_pindah(self, obj):
        if obj.status.startswith("Selesai Diproses di") and obj.ruangan.tahap_berikutnya:
            pindah_url = reverse('admin:pindahkan_batch_ke_ruangan', args=[obj.nomor_batch])
            return format_html('<a href="{}" class="btn btn-success">Pindahkan</a>', pindah_url)
        return "-"
    tombol_pindah.short_description = "Pindahkan Ke Ruangan Berikutnya"

    def status_display(self, obj):
        return dict(ProsesProduksi.STATUS_CHOICES).get(obj.status, obj.status)
    status_display.short_description = "Status"

    def get_waktu_selesai(self, obj):
        return obj.waktu_selesai if obj.waktu_selesai else "Belum selesai"
    get_waktu_selesai.short_description = "Waktu Selesai"

    def tahap_berikutnya(self, obj):
        return obj.ruangan.tahap_berikutnya.nama if obj.ruangan.tahap_berikutnya else "Tahap Akhir"
    tahap_berikutnya.short_description = "Tahap Berikutnya"
