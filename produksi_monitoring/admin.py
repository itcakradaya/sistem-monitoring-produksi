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

class ProsesProduksiForm(forms.ModelForm):
    class Meta:
        model = ProsesProduksi
        fields = '__all__'

@admin.register(ItemDescription)
class ItemDescriptionAdmin(admin.ModelAdmin):
    search_fields = ['description']

### **Aksi: "Tandai Sedang Diproses"**
@admin.action(description="Tandai sebagai Sedang Diproses")
def tandai_sedang_diproses(modeladmin, request, queryset):
    """Menandai batch yang statusnya masih 'Menunggu' menjadi 'Sedang Diproses'."""
    count = 0
    for proses in queryset:
        if proses.status == "Menunggu":
            proses.status = "Sedang Diproses"
            proses.waktu_mulai_produksi = timezone.now()
            proses.save()
            count += 1
    if count > 0:
        modeladmin.message_user(request, f"{count} batch sekarang 'Sedang Diproses'.")
    else:
        modeladmin.message_user(request, "Pastikan batch berstatus 'Menunggu'.", level="error")

### **Aksi: "Tandai Selesai & Pindahkan ke Ruangan Berikutnya"**
@admin.action(description="Tandai Selesai & Pindahkan ke Ruangan Berikutnya")
def tandai_selesai_dan_pindah(modeladmin, request, queryset):
    """Menandai batch selesai di satu ruangan dan memindahkannya ke tahap berikutnya."""
    count = 0
    for proses in queryset:
        if proses.status == "Sedang Diproses" and proses.ruangan.tahap_berikutnya:
            if ProsesProduksi.objects.filter(nomor_batch=proses.nomor_batch, ruangan=proses.ruangan.tahap_berikutnya).exists():
                modeladmin.message_user(request, f"Batch {proses.nomor_batch} sudah ada di {proses.ruangan.tahap_berikutnya.nama}.", level="warning")
                continue  # Skip agar tidak terjadi duplikasi

            # 🔹 Update status, reset waktu, dan pindahkan ke ruangan berikutnya
            proses.status = "Menunggu"
            proses.waktu_mulai_produksi = None
            proses.waktu_selesai = None
            proses.ruangan = proses.ruangan.tahap_berikutnya
            proses.save()

            count += 1

    if count > 0:
        modeladmin.message_user(request, f"{count} batch selesai dan telah dipindahkan ke ruangan berikutnya.")
    else:
        modeladmin.message_user(request, "Pastikan batch berstatus 'Sedang Diproses' dan ada ruangan berikutnya.", level="error")

### **Aksi: "Tandai Selesai Produksi" (Hanya untuk Ruang Labelling)**
@admin.action(description="Tandai Selesai Produksi")
def tandai_selesai_produksi(modeladmin, request, queryset):
    """Menandai batch yang telah selesai di Ruang Labelling sebagai 'Selesai Produksi'."""
    count = 0
    for proses in queryset:
        if proses.status == "Sedang Diproses" and proses.ruangan.tahap_berikutnya is None:
            proses.status = "Selesai Produksi"
            proses.waktu_selesai = timezone.now()
            proses.save()
            count += 1
    if count > 0:
        modeladmin.message_user(request, f"{count} batch telah ditandai sebagai 'Selesai Produksi'.")
    else:
        modeladmin.message_user(request, "Pastikan batch berada di tahap akhir (Ruang Labelling) dan berstatus 'Sedang Diproses'.", level="error")

@admin.register(ProsesProduksi)
class ProsesProduksiAdmin(admin.ModelAdmin):
    autocomplete_fields = ['nama']
    search_fields = ['nama__description', 'nomor_batch']
    form = ProsesProduksiForm
    list_display = ('nomor_batch', 'nama', 'ruangan', 'status_display', 'jumlah', 'satuan', 'waktu_dibuat', 'get_waktu_selesai', 'tahap_berikutnya', 'tombol_pindahkan')
    list_filter = ('status', 'ruangan')
    ordering = ('-waktu_dibuat',)
    readonly_fields = ('waktu_selesai',)

    # ✅ Tambahkan aksi "Tandai Selesai Produksi"
    actions = [tandai_sedang_diproses, tandai_selesai_dan_pindah, tandai_selesai_produksi]

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
        if obj.status == "Selesai" and obj.ruangan.jenis_proses == 'weighing':
            url = reverse("pindahkan_batch_ke_ruangan", args=[obj.pk])
            return format_html(
                '<a href="{}" onclick="window.open(this.href, \"pindah_ruangan\", \"width=600,height=400\"); return false;" '
                'class="btn btn-primary">Pilih Ruangan Proses</a>', url
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

            return render(request, "produksi_monitoring/popup_pindah_ruangan.html", {"pindah_sukses": True})

        ruangan_list = Ruangan.objects.filter(jenis_proses='processing')
        return render(request, "produksi_monitoring/popup_pindah_ruangan.html", {"produksi": produksi, "ruangan_list": ruangan_list})
