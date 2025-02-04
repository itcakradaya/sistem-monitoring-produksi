from django.db import models
from django.utils.timezone import now  # ✅ Pastikan now() diimpor di sini
import string




class Mesin(models.Model):
    kode_mesin = models.CharField(max_length=10, unique=True, null=True)
    nama_mesin = models.CharField(max_length=200, unique=True)
    
    def __str__(self):
        return self.nama_mesin
    class Meta:
        verbose_name = "Mesin"
        verbose_name_plural = "Mesin" 

class Ruangan(models.Model):
    PROSES_CHOICES = [
        ('weighing', 'Weighing'),
        ('processing', 'Processing'),
        ('mixing', 'Mixing'),
        ('filling', 'Filling'),
        ('packaging', 'Packaging'),
        ('labelling', 'Labelling'),
        ('quality_control', 'Quality Control'),
    ]
    kode_ruangan = models.CharField(max_length=10, unique=True, null=True)
    nama = models.CharField(max_length=100, unique=True)
    link_khusus = models.CharField(max_length=255, unique=True)
    mesin = models.ManyToManyField(Mesin, related_name="ruangan")
    jenis_proses = models.CharField(max_length=50, choices=PROSES_CHOICES, default='mixing')

    def __str__(self):
        return self.nama
    class Meta:
        verbose_name = "Ruangan"
        verbose_name_plural = "Ruangan" 
class ItemDescription(models.Model):
    description = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.description
class ProsesProduksi(models.Model):
    STATUS_CHOICES = [
        ('Menunggu', 'Menunggu Proses'),
        ('Sedang diproses', 'Sedang Diproses'),
        
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Menunggu',  # ✅ Tambahkan default agar status tidak kosong
        null=False,  # Pastikan ini False agar tidak ada data kosong
        blank=False,  # Pastikan ini False agar status selalu terisi
    )

    nama = models.ForeignKey(ItemDescription, on_delete=models.CASCADE)  # Pastikan ini ForeignKey!
    nomor_batch = models.CharField(max_length=20, unique=True, blank=True)  # 🔹 Auto-generate
    jumlah = models.PositiveIntegerField()
    satuan = models.CharField(max_length=10, choices=[
        ('kg', 'Kilogram'),
        ('pcs', 'Pieces'),
        ('liter', 'Liter'),
        ('pack', 'Pack'),
    ], default='kg')
    ruangan = models.ForeignKey(Ruangan, on_delete=models.CASCADE)
    mesin = models.ManyToManyField(Mesin, related_name="produk")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='menunggu')
    operator = models.CharField(max_length=200, blank=True, null=True)
    keterangan = models.TextField(blank=True, null=True)
    waktu_dibuat = models.DateTimeField(auto_now_add=True)
    waktu_mulai_produksi = models.DateTimeField(blank=True, null=True)
    waktu_selesai = models.DateTimeField(blank=True, null=True) 


    def generate_kode_produksi(self):
        """
        Membuat kode produksi dengan format:
        [R/S/T/U]MMDD[A1, A2, ..., A9, A0, B1, ..., B9, B0, ...]
        Berdasarkan `waktu_mulai_produksi`, bukan waktu input.
        """
        if not self.waktu_mulai_produksi:
            raise ValueError("Waktu mulai produksi harus ditentukan sebelum generate nomor batch!")

        # Konversi tahun ke huruf (2025 = R, 2026 = S, 2027 = T, ...)
        tahun_awal = 2025
        huruf_tahun = chr(ord('R') + (self.waktu_mulai_produksi.year - tahun_awal))

        bulan_hari = self.waktu_mulai_produksi.strftime("%m%d")  # Ambil bulan dan tanggal (tanpa tahun)
        prefix = f"{huruf_tahun}{bulan_hari}"  # Contoh: "R0203"

        # Hitung jumlah produksi yang sudah ada pada tanggal tersebut
        produksi_hari_ini = ProsesProduksi.objects.filter(
            waktu_mulai_produksi__date=self.waktu_mulai_produksi.date()
        ).count()

        # Buat daftar kode produksi (A1, A2, ..., A9, A0, B1, ..., B9, B0, ...)
        kode_list = [f"{huruf}{angka}" for huruf in string.ascii_uppercase for angka in range(1, 10)] + \
                    [f"{huruf}0" for huruf in string.ascii_uppercase]

        # Ambil kode produksi yang sesuai dengan urutan
        kode_produksi = kode_list[produksi_hari_ini] if produksi_hari_ini < len(kode_list) else "ZZ"

        return f"{prefix}{kode_produksi}"

    def save(self, *args, **kwargs):
        if not self.nomor_batch and self.waktu_mulai_produksi:  # Hanya buat nomor batch jika belum ada dan ada waktu produksi
            self.nomor_batch = self.generate_kode_produksi()
        super().save(*args, **kwargs)  # Simpan ke database

    def __str__(self):
        return f"{self.nomor_batch} - {self.nama}"

    def __str__(self):
        return f"{self.nomor_batch} - {self.nama}"
    def __str__(self):
        return f"{self.nomor_batch} - {self.nama} ({self.get_status_display()})"
    class Meta:
        verbose_name = "Proses Produksi"
        verbose_name_plural = "Proses Produksi" 

