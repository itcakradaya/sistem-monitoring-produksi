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
    list_display = ('nama', 'kode_ruangan')
    search_fields = ('nama', 'kode_ruangan')
    prepopulated_fields = {'link_khusus': ('nama',)}

@admin.register(Mesin)
class MesinAdmin(admin.ModelAdmin):
    list_display = ('kode_mesin', 'nama_mesin')
    search_fields = ('kode_mesin', 'nama_mesin')

# Custom Form untuk menyembunyikan `waktu_selesai` dan menghapus opsi "Selesai" dari dropdown status
class ProsesProduksiForm(forms.ModelForm):
    class Meta:
        model = ProsesProduksi
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pastikan status "Selesai" tidak muncul di dropdown
        if 'status' in self.fields:
            self.fields['status'].choices = [
                choice for choice in self.fields['status'].choices if choice[0] != 'Selesai'
            ]

        # Sembunyikan `waktu_selesai` saat input data baru
        if not self.instance.pk:  # Hanya jika data baru
            self.fields.pop('waktu_selesai', None)

@admin.register(ItemDescription)
class ItemDescriptionAdmin(admin.ModelAdmin):
    search_fields = ['description']  # Agar bisa digunakan di autocomplete


@admin.register(ProsesProduksi)
class ProsesProduksiAdmin(admin.ModelAdmin):
    autocomplete_fields = ['nama']  # Pastikan field 'nama' terkait dengan ItemDescription
    search_fields = ['nama__description']  # Memastikan pencarian berdasarkan teks dalam ItemDescription
    form = ProsesProduksiForm  # Gunakan form custom agar "Selesai" tidak bisa dipilih
    list_display = ('nomor_batch', 'nama', 'ruangan', 'status_display', 'jumlah', 'satuan', 'waktu_dibuat', 'get_waktu_selesai', 'tombol_selesaikan')
    list_filter = ('status', 'ruangan')
    search_fields = ('nama__description', 'nomor_batch', 'operator')
    ordering = ('-waktu_dibuat',)
    readonly_fields = ('waktu_selesai',)  # `waktu_selesai` tidak bisa diubah langsung

    def status_display(self, obj):
        """Menampilkan status dengan format yang benar agar tidak ada yang kosong"""
        if not obj.status:
            return "TIDAK ADA STATUS"
        return dict(ProsesProduksi.STATUS_CHOICES).get(obj.status, obj.status)  # Pastikan format sesuai pilihan
    status_display.short_description = "Status"

    def get_waktu_selesai(self, obj):
        """Menampilkan waktu selesai atau teks 'Belum selesai' jika masih dalam proses"""
        return obj.waktu_selesai if obj.waktu_selesai else "Belum selesai"
    get_waktu_selesai.short_description = "Waktu Selesai"

    def tombol_selesaikan(self, obj):
        """Menampilkan tombol aksi 'Selesaikan' jika proses belum selesai"""
        if obj.status != "Selesai":
            url = reverse("admin:selesaikan_produksi", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="color: white; background: green; padding: 5px 10px; border-radius: 5px;">Selesaikan</a>', url
            )
        return format_html('<span style="color: gray;">Selesai</span>')
    tombol_selesaikan.short_description = "Aksi"

    def get_urls(self):
        """Menambahkan URL khusus untuk aksi 'Selesaikan'"""
        urls = super().get_urls()
        custom_urls = [
            path('selesaikan/<int:pk>/', self.admin_site.admin_view(self.selesaikan_proses), name="selesaikan_produksi"),
        ]
        return custom_urls + urls

    def selesaikan_proses(self, request, pk):
        """Aksi untuk menandai proses produksi sebagai selesai"""
        proses = get_object_or_404(ProsesProduksi, pk=pk)

        # Pastikan proses produksi tidak dalam status 'Menunggu' sebelum menyelesaikan
        if proses.status == "Menunggu":
            self.message_user(request, f"Proses produksi {proses.nomor_batch} masih dalam status 'Menunggu' dan tidak bisa diselesaikan.", level='error')
        elif proses.status != "Selesai":
            proses.status = "Selesai"  # Ubah status menjadi selesai
            proses.waktu_selesai = timezone.now()  # Isi waktu selesai dengan waktu sekarang
            proses.save(update_fields=['status', 'waktu_selesai'])  # Simpan perubahan
            self.message_user(request, f"Proses produksi {proses.nomor_batch} berhasil ditandai sebagai 'Selesai'.")

        return redirect(request.META.get("HTTP_REFERER", "admin:produksi_monitoring_prosesproduksi_changelist"))
