from django.db import models
from django.utils.timezone import now
import string
from django.core.exceptions import ValidationError

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
    tahap_berikutnya = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.nama
    class Meta:
        verbose_name = "Ruangan"
        verbose_name_plural = "Ruangan"

class ItemDescription(models.Model):
    barcode = models.CharField(max_length=20, unique=True, null=True, blank=True)
    description = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.description

class ProsesProduksi(models.Model):
    STATUS_CHOICES = [
        ('Menunggu', 'Menunggu Proses'),
        ('Sedang diproses', 'Sedang Diproses'),
        ('Siap Dipindahkan', 'Siap Dipindahkan'),
        ('Selesai', 'Selesai'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Menunggu',
        null=False,
        blank=False,
    )
    nama = models.ForeignKey("ItemDescription", on_delete=models.CASCADE)
    nomor_batch = models.CharField(
        max_length=20, 
        unique=True, 
        blank=True, 
        null=False
    )
    jumlah = models.PositiveIntegerField()
    satuan = models.CharField(max_length=10, choices=[
        ('kg', 'Kilogram'), ('pcs', 'Pieces'), ('liter', 'Liter'), ('pack', 'Pack'),
    ], default='kg')
    ruangan = models.ForeignKey("Ruangan", on_delete=models.CASCADE)
    waktu_dibuat = models.DateTimeField(auto_now_add=True)
    waktu_mulai_produksi = models.DateTimeField(blank=True, null=True)
    waktu_selesai = models.DateTimeField(blank=True, null=True)

    def clean(self):
        """Cek apakah nomor batch sudah ada di database, tapi hanya saat batch dibuat"""
        if not self.pk:
            if ProsesProduksi.objects.filter(nomor_batch=self.nomor_batch).exists():
                 raise ValidationError({"nomor_batch": "Nomor batch ini sudah digunakan. Silakan gunakan nomor batch lain."})

    def save(self, *args, **kwargs):
        self.clean()
        # Hanya buat nomor batch jika produksi dimulai di ruangan "Penimbangan"
        if self.status == "Sedang diproses" and not self.waktu_mulai_produksi:
            self.waktu_mulai_produksi = now()  # Set waktu mulai otomatis
      
        if not self.pk:  # Jika proses baru dibuat
            try:
                ruang_penimbangan = Ruangan.objects.get(nama__icontains="Penimbangan")
                self.ruangan = ruang_penimbangan
            except Ruangan.DoesNotExist:
                pass  # Jika ruangan tidak ada, biarkan admin memilih sendiri

        # Jika status "Selesai", otomatis pindahkan ke tahap berikutnya jika belum ada
        if self.status == "Selesai" and self.ruangan.tahap_berikutnya:
            self.pindah_ke_tahap_berikutnya()

        super().save(*args, **kwargs)

    def pindah_ke_tahap_berikutnya(self):
        """Jika batch berada di ruang filling atau labelling, pindahkan otomatis"""
        if self.ruangan.tahap_berikutnya:
            existing_batch = ProsesProduksi.objects.filter(
                nomor_batch=self.nomor_batch,
                ruangan=self.ruangan.tahap_berikutnya
            ).exists()

            if not existing_batch:
                ProsesProduksi.objects.filter(nomor_batch=self.nomor_batch).update(
                    nomor_batch=self.nomor_batch,
                    nama=self.nama,
                    jumlah=self.jumlah,
                    satuan=self.satuan,
                    status="Menunggu",
                    ruangan=self.ruangan.tahap_berikutnya,
                    waktu_mulai_produksi=None,
                )

    def __str__(self):
        return f"{self.nomor_batch} - {self.nama} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Proses Produksi"
        verbose_name_plural = "Proses Produksi"