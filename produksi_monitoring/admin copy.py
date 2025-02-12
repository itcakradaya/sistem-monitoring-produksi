from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, path
from django.utils import timezone
from django import forms
from produksi_monitoring.models import ItemDescription, ProsesProduksi, Ruangan, Mesin

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

@admin.register(ItemDescription)
class ItemDescriptionAdmin(admin.ModelAdmin):
    search_fields = ['description', 'barcode']  # 🔍 Bisa mencari berdasarkan barcode

### ✅ **Form Kustom untuk Proses Produksi**
class ProsesProduksiForm(forms.ModelForm):
    class Meta:
        model = ProsesProduksi
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # **1️⃣ Set Ruangan Default ke "Ruang Penimbangan"**
        if not self.instance.pk:  # Jika ini input baru
            try:
                ruang_penimbangan = Ruangan.objects.get(nama__icontains="penimbangan")
                self.fields['ruangan'].initial = ruang_penimbangan
            except Ruangan.DoesNotExist:
                pass  # Jika ruangan tidak ada, biarkan admin memilih sendiri

        # **2️⃣ Status Default "Menunggu" dan Tidak Bisa Dipilih Status Lain**
        if not self.instance.pk:
            self.fields['status'].initial = "Menunggu"
            self.fields['status'].widget.attrs.update({'readonly': True, 'style': 'background-color: #e9ecef; cursor: not-allowed;'})

        # **3️⃣ Nama produk memiliki fitur pencarian barcode**
        self.fields['nama'].widget.attrs.update({'class': 'vTextField'})  # Autocomplete di admin

### ✅ **Aksi untuk Proses Produksi**
@admin.action(description="Tandai sebagai Sedang Diproses")
def tandai_sedang_diproses(modeladmin, request, queryset):
    count = queryset.filter(status="Menunggu").update(status="Sedang Diproses", waktu_mulai_produksi=timezone.now())
    if count:
        modeladmin.message_user(request, f"{count} batch sekarang 'Sedang Diproses'.")
    else:
        modeladmin.message_user(request, "Pastikan batch berstatus 'Menunggu'.", level="error")

@admin.action(description="Pilih Ruangan Tujuan untuk Batch dari Penimbangan")
def pilih_ruangan_proses(modeladmin, request, queryset):
    for proses in queryset:
        if "penimbangan" in proses.ruangan.nama.lower():
            return redirect(reverse("admin:pindahkan_batch_ke_ruangan", args=[proses.pk]))
    modeladmin.message_user(request, "Pastikan batch berada di Ruang Penimbangan.", level="error")

@admin.action(description="Tandai Selesai Produksi")
def tandai_selesai_produksi(modeladmin, request, queryset):
    count = queryset.filter(status="Sedang Diproses", ruangan__tahap_berikutnya=None).update(
        status="Selesai Produksi", waktu_selesai=timezone.now()
    )
    if count:
        modeladmin.message_user(request, f"{count} batch telah ditandai sebagai 'Selesai Produksi'.")
    else:
        modeladmin.message_user(request, "Pastikan batch berada di tahap akhir dan berstatus 'Sedang Diproses'.", level="error")

### ✅ **Admin Model untuk Proses Produksi**
@admin.register(ProsesProduksi)
class ProsesProduksiAdmin(admin.ModelAdmin):
    form = ProsesProduksiForm
    autocomplete_fields = ['nama']
    search_fields = ['nama__description', 'nomor_batch']
    list_display = ('nomor_batch', 'nama', 'ruangan', 'status_display', 'jumlah', 'satuan', 'waktu_dibuat', 'get_waktu_selesai', 'tahap_berikutnya', 'tombol_pindahkan')
    list_filter = ('status', 'ruangan')
    ordering = ('-waktu_dibuat',)
    readonly_fields = ('waktu_selesai',)
    actions = [tandai_sedang_diproses, pilih_ruangan_proses, tandai_selesai_produksi]

    def status_display(self, obj):
        return dict(ProsesProduksi.STATUS_CHOICES).get(obj.status, obj.status)
    status_display.short_description = "Status"

    def get_waktu_selesai(self, obj):
        return obj.waktu_selesai if obj.waktu_selesai else "Belum selesai"
    get_waktu_selesai.short_description = "Waktu Selesai"

    def tahap_berikutnya(self, obj):
        return obj.ruangan.tahap_berikutnya.nama if obj.ruangan.tahap_berikutnya else "Tahap Akhir"
    tahap_berikutnya.short_description = "Tahap Berikutnya"

    def tombol_pindahkan(self, obj):
        if obj.status == "Sedang Diproses" and "penimbangan" in obj.ruangan.nama.lower():
            url = reverse("admin:pindahkan_batch_ke_ruangan", args=[obj.pk])
            return format_html(
                '<a href="{}" class="btn btn-warning">Pilih Ruangan Tujuan</a>', url
            )
        return format_html('<span class="text-muted">Tidak Bisa Dipindahkan</span>')
    tombol_pindahkan.short_description = "Aksi"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('pindahkan_batch/<int:pk>/', self.admin_site.admin_view(self.pindahkan_produksi), name="pindahkan_batch_ke_ruangan"),
        ]
        return custom_urls + urls

    def pindahkan_produksi(self, request, pk):
        produksi = get_object_or_404(ProsesProduksi, pk=pk)
        if request.method == "POST":
            ruangan_id = request.POST.get("ruangan_tujuan")
            ruangan_tujuan = get_object_or_404(Ruangan, id=ruangan_id)
            produksi.ruangan = ruangan_tujuan
            produksi.status = "Menunggu"
            produksi.waktu_selesai = None
            produksi.save()
            return redirect("admin:produksi_monitoring_prosesproduksi_changelist")
        ruangan_list = Ruangan.objects.exclude(id=produksi.ruangan.id)
        return render(request, "produksi_monitoring/popup_pindah_ruangan.html", {"produksi": produksi, "ruangan_list": ruangan_list})
