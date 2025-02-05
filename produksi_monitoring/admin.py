from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import get_object_or_404
from django.urls import reverse, path
from django.shortcuts import redirect
from django.utils import timezone
from produksi_monitoring.models import ItemDescription, ProsesProduksi, Ruangan, Mesin
from django import forms

admin.site.index_title = "Manajemen Proses Produksi"

@admin.register(Ruangan)
class RuanganAdmin(admin.ModelAdmin):
    list_display = ('nama', 'kode_ruangan', 'tahap_berikutnya')
    search_fields = ('nama', 'kode_ruangan')
    prepopulated_fields = {'link_khusus': ('nama',)}

@admin.register(Mesin)
class MesinAdmin(admin.ModelAdmin):
    list_display = ('kode_mesin', 'nama_mesin')
    search_fields = ('kode_mesin', 'nama_mesin')

class ProsesProduksiForm(forms.ModelForm):
    class Meta:
        model = ProsesProduksi
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Hilangkan opsi "Selesai" dari dropdown status agar admin tidak bisa langsung memilihnya
        if 'status' in self.fields:
            self.fields['status'].choices = [
                choice for choice in self.fields['status'].choices if choice[0] != 'Selesai'
            ]

@admin.register(ItemDescription)
class ItemDescriptionAdmin(admin.ModelAdmin):
    search_fields = ['description']

@admin.action(description="Pindahkan ke tahap berikutnya")
def pindah_ke_tahap_berikutnya(modeladmin, request, queryset):
    """Memindahkan batch yang selesai ke ruangan berikutnya."""
    for proses in queryset:
        if proses.status == "Sedang diproses":
            proses.status = "Selesai"
            proses.waktu_selesai = timezone.now()
            proses.save()
            proses.pindah_ke_tahap_berikutnya()
    modeladmin.message_user(request, "Batch berhasil dipindahkan ke tahap berikutnya.")

@admin.register(ProsesProduksi)
class ProsesProduksiAdmin(admin.ModelAdmin):
    autocomplete_fields = ['nama']
    search_fields = ['nama__description']
    form = ProsesProduksiForm
    list_display = ('nomor_batch', 'nama', 'ruangan', 'status_display', 'jumlah', 'satuan', 'waktu_dibuat', 'get_waktu_selesai', 'tombol_selesaikan')
    list_filter = ('status', 'ruangan')
    search_fields = ('nama__description', 'nomor_batch', 'operator')
    ordering = ('-waktu_dibuat',)
    readonly_fields = ('waktu_selesai',)
    actions = [pindah_ke_tahap_berikutnya]

    def status_display(self, obj):
        if not obj.status:
            return "TIDAK ADA STATUS"
        return dict(ProsesProduksi.STATUS_CHOICES).get(obj.status, obj.status)
    status_display.short_description = "Status"

    def get_waktu_selesai(self, obj):
        return obj.waktu_selesai if obj.waktu_selesai else "Belum selesai"
    get_waktu_selesai.short_description = "Waktu Selesai"

    def tombol_selesaikan(self, obj):
        if obj.status != "Selesai":
            url = reverse("admin:selesaikan_produksi", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="color: white; background: green; padding: 5px 10px; border-radius: 5px;">Selesaikan</a>', url
            )
        return format_html('<span style="color: gray;">Selesai</span>')
    tombol_selesaikan.short_description = "Aksi"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('selesaikan/<int:pk>/', self.admin_site.admin_view(self.selesaikan_proses), name="selesaikan_produksi"),
        ]
        return custom_urls + urls

    def selesaikan_proses(self, request, pk):
        """Aksi untuk menandai produksi selesai & memindahkannya ke tahap berikutnya."""
        proses = get_object_or_404(ProsesProduksi, pk=pk)

        if proses.status == "Menunggu Proses":
            self.message_user(request, f"Proses produksi {proses.nomor_batch} masih 'Menunggu Proses' dan tidak bisa diselesaikan.", level='error')
        elif proses.status != "Selesai":
            proses.status = "Selesai"
            proses.waktu_selesai = timezone.now()
            proses.save(update_fields=['status', 'waktu_selesai'])
            proses.pindah_ke_tahap_berikutnya() 
            self.message_user(request, f"Proses produksi {proses.nomor_batch} berhasil ditandai sebagai 'Selesai' dan dipindahkan ke tahap berikutnya.")

        return redirect(request.META.get("HTTP_REFERER", "admin:produksi_monitoring_prosesproduksi_changelist"))
