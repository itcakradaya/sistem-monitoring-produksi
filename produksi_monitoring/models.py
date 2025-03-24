from django.db import models
from django.db import transaction
from django.utils.timezone import now
from django.contrib.auth.models import User
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

class Operator(models.Model):
    nama = models.CharField(max_length=255, unique=True)
    kategori = models.CharField(max_length=50, choices=[
        ("Penimbangan","Penimbangan"),
        ("Proses", "Proses"),
        ("Filling", "Filling"),
        ("Labelling","Labelling")
        ]
    )

    def __str__(self):
        return f"{self.nama} ({self.kategori})"
class ProsesProduksi(models.Model):
    STATUS_CHOICES = [
        ('Menunggu', 'Menunggu Proses'),
        ('Sedang diproses', 'Sedang Diproses'),
        ('Menunggu Verifikasi Admin', 'Menunggu Verifikasi Admin'),
        ('Selesai di Ruangan Ini', 'Selesai di Ruangan Ini'),
        ('Siap Dipindahkan', 'Siap Dipindahkan'),
        ('Selesai Produksi', 'Selesai Produksi'),
    ]
    status = models.CharField(
        max_length=30,
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
    
    def progress_percentage(self):
        if self.jumlah > 0:
            return (self.progress / self.jumlah) * 100
        return 0  # Mencegah error jika jumlah 0
    @property
    def progress_display(self):
        return f"{self.progress_percentage():.0f}%" 
    
    satuan = models.CharField(max_length=10, choices=[
        ('kg', 'Kilogram'), ('pcs', 'Pieces'), ('liter', 'Liter'), ('pack', 'Pack'),
    ], default='kg')

      # ✅ Tambahkan untuk Ruang Labelling
    jumlah_kemasan = models.PositiveIntegerField(null=True, blank=True)
    satuan_kemasan = models.CharField(max_length=10, choices=[
        ('pcs', 'Pieces'), ('karton', 'Karton'),
    ], null=True, blank=True)

    ruangan = models.ForeignKey("Ruangan", on_delete=models.CASCADE, default='Ruang Penimbangan')
    waktu_dibuat = models.DateTimeField(auto_now_add=True)
    waktu_mulai_produksi = models.DateTimeField(blank=True, null=True)
    waktu_selesai = models.DateTimeField(blank=True, null=True)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, null=True, blank=True)
    progress = models.PositiveIntegerField(default=0)

    def update_progress(self, jumlah_terproses):
        """Update progress produksi berdasarkan jumlah yang diproses"""

        if jumlah_terproses < 1:
            raise ValueError("Jumlah yang diproses harus lebih dari 0")

        self.progress = min(self.progress + jumlah_terproses, self.jumlah)

        if self.progress >= self.jumlah:
            self.progress = self.jumlah
            self.status = f"Selesai Diproses di {self.ruangan.nama}"
            self.waktu_selesai = now()

            # ✅ Pastikan transaksi aman dan tidak ada duplikasi
            with transaction.atomic():
                riwayat, created = RiwayatProduksi.objects.get_or_create(
                    nomor_batch=self.nomor_batch,
                    nama_produk=self.nama,
                    jumlah=self.jumlah,
                    satuan=self.satuan,
                    ruangan=self.ruangan,
                    operator=self.operator,
                    waktu_mulai_produksi=self.waktu_mulai_produksi,
                    waktu_selesai=self.waktu_selesai
                )

                if created:
                    print(f"DEBUG: Batch {self.nomor_batch} berhasil ditambahkan ke RiwayatProduksi.")

         # ✅ Simpan perubahan di database
        self.save()

    def __str__(self):
        return f"{self.nomor_batch} - {self.nama.description}"
    
    
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

    def set_selesai_di_ruangan(self):
        """Atur status selesai berdasarkan ruangan saat ini"""
        self.status = f"Selesai Diproses di {self.ruangan.nama}"    

    def pindah_ke_tahap_berikutnya(self):
        """Memindahkan batch ke tahap berikutnya"""
        if self.ruangan.tahap_berikutnya:
            existing_batch = ProsesProduksi.objects.filter(
                nomor_batch=self.nomor_batch,
                ruangan=self.ruangan.tahap_berikutnya
            ).exists()

            if not existing_batch:
                ProsesProduksi.objects.create(
                    nomor_batch=self.nomor_batch,
                    nama=self.nama,
                    jumlah=self.jumlah,
                    satuan=self.satuan,
                    status="Menunggu",  # Status baru setelah dipindah
                    ruangan=self.ruangan.tahap_berikutnya,
                    waktu_mulai_produksi=None,
                    operator=None  # Operator ditentukan nanti
                )
                print(f"✅ Batch {self.nomor_batch} dipindahkan ke {self.ruangan.tahap_berikutnya.nama}")
            else:
                print(f"⚠️ Batch {self.nomor_batch} sudah ada di {self.ruangan.tahap_berikutnya.nama}")
        else:
            print(f"⚠️ Tidak ada tahap berikutnya untuk batch {self.nomor_batch}")


    def __str__(self):
        return f"{self.nomor_batch} - {self.nama} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Proses Produksi"
        verbose_name_plural = "Proses Produksi"

class RiwayatProduksi(models.Model):
    nomor_batch = models.CharField(max_length=20)
    nama_produk = models.ForeignKey(ItemDescription, on_delete=models.CASCADE)
    jumlah = models.PositiveIntegerField()
    satuan = models.CharField(max_length=10)
    ruangan = models.ForeignKey(Ruangan, on_delete=models.CASCADE)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, null=True, blank=True)
    waktu_mulai_produksi = models.DateTimeField()
    waktu_selesai = models.DateTimeField()

    def __str__(self):
        return f"Riwayat: {self.nomor_batch} di {self.ruangan.nama}"
