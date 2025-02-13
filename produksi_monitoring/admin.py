from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, path
from django.utils import timezone
from django import forms
from produksi_monitoring.models import ItemDescription, ProsesProduksi, Ruangan, Mesin
from django.core.exceptions import ValidationError

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
        self.fields['nomor_batch'].required = True
    def clean_nomor_batch(self):
        nomor_batch = self.cleaned_data.get('nomor_batch')
        if ProsesProduksi.objects.exclude(pk=self.instance.pk).filter(nomor_batch=nomor_batch).exists():
            raise ValidationError("Nomor batch ini sudah digunakan. Silakan gunakan nomor batch lain.")

        return nomor_batch

    # Hanya validasi duplikasi jika batch ini **baru dibuat** (bukan pindah ruangan)
        if self.instance.pk is None:
            if ProsesProduksi.objects.filter(nomor_batch=nomor_batch).exists():
                raise ValidationError("Nomor batch ini sudah digunakan. Silakan gunakan nomor batch lain.")

        return nomor_batch


@admin.register(ItemDescription)
class ItemDescriptionAdmin(admin.ModelAdmin):
    search_fields = ['description', 'barcode']

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
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import admin
from produksi_monitoring.models import ProsesProduksi

@admin.action(description="Tandai Selesai & Pindahkan ke Ruangan Berikutnya")
def tandai_selesai_dan_pindah(modeladmin, request, queryset):
    batch_penimbangan = []
    batch_lain = []

    for proses in queryset:
        if "penimbangan" in proses.ruangan.nama.lower():  # Jika berasal dari Ruang Penimbangan
            batch_penimbangan.append(proses.pk)
        else:
            batch_lain.append(proses)

    # **1️⃣ Tangani Batch dari Ruangan Lain Secara Otomatis**
    for proses in batch_lain:
        if proses.status == "Sedang Diproses" and proses.ruangan.tahap_berikutnya:
            if ProsesProduksi.objects.filter(nomor_batch=proses.nomor_batch, ruangan=proses.ruangan.tahap_berikutnya).exists():
                modeladmin.message_user(request, f"Batch {proses.nomor_batch} sudah ada di {proses.ruangan.tahap_berikutnya.nama}.", level="warning")
                continue

            # ✅ Pindahkan batch ke tahap berikutnya
            proses.ruangan = proses.ruangan.tahap_berikutnya

            # ✅ Jika ruangan berikutnya adalah Penimbangan, ubah status ke "Menunggu"
            if "penimbangan" in proses.ruangan.nama.lower():
                proses.status = "Menunggu"
                proses.waktu_mulai_produksi = None
            else:
                # ✅ Jika bukan, langsung tandai sebagai "Sedang Diproses"
                proses.status = "Sedang Diproses"
                proses.waktu_mulai_produksi = timezone.now()

            # Simpan perubahan
            proses.waktu_selesai = timezone.now()
            proses.save()

            modeladmin.message_user(request, f"Batch {proses.nomor_batch} berhasil dipindahkan ke {proses.ruangan.nama}.", level="success")

    # **2️⃣ Jika Batch Berasal dari Penimbangan, Arahkan ke Pemilihan Ruangan**
    if batch_penimbangan:
        request.session['batch_to_move'] = batch_penimbangan
        return redirect("pilih_ruangan_proses")  # Arahkan ke halaman pemilihan ruangan

    modeladmin.message_user(request, "Batch telah berhasil dipindahkan ke tahap berikutnya.")

    

@admin.action(description="Pilih Ruangan Tujuan untuk Batch dari Penimbangan")
def pilih_ruangan_proses(modeladmin, request, queryset):
    for proses in queryset:
        if "penimbangan" in proses.ruangan.nama.lower():
            request.session['batch_to_move'] = [proses.pk for proses in queryset]
            return redirect("admin:pilih_ruangan_proses")
    modeladmin.message_user(request, "Pastikan batch berada di Ruang Penimbangan.", level="error")

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
    operator = ProsesProduksi.operator
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