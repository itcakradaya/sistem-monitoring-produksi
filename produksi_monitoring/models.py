from django.db import models
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.utils.text import slugify

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
    slug = models.SlugField(max_length=255, unique=True, blank=True)  

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nama)  # ✅ otomatis buat slug dari nama
        super().save(*args, **kwargs)

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
        ("Penimbangan", "Penimbangan"),
        ("Proses", "Proses"),
        ("Filling", "Filling"),
        ("Labelling", "Labelling"),
    ])

    def __str__(self):
        return f"{self.nama} ({self.kategori})"

class ProsesProduksi(models.Model):
    STATUS_CHOICES = [
        ('Menunggu', 'Menunggu Proses'),
        ('Sedang diproses', 'Sedang Diproses'),
        ('Menunggu Verifikasi Admin', 'Menunggu Verifikasi Admin'),
        ('Siap Dipindahkan', 'Siap Dipindahkan'),
        ('Selesai Produksi', 'Selesai Produksi'),
    ]

    HASIL_AKHIR_CHOICES = [
        ('', 'Belum Ditetapkan'),
        ('Release', 'Release'),
        ('Reject', 'Reject'),
    ]

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Menunggu', db_index=True)
    hasil_akhir = models.CharField(max_length=10, choices=HASIL_AKHIR_CHOICES, default='', blank=True)

    nama = models.ForeignKey(ItemDescription, on_delete=models.CASCADE)
    nomor_batch = models.CharField(max_length=20, unique=False, null=False, blank=False, db_index=True)
    jumlah = models.PositiveIntegerField()
    satuan = models.CharField(max_length=10, choices=[
        ('kg', 'Kilogram'), ('pcs', 'Pieces'), ('liter', 'Liter'), ('pack', 'Pack')
    ], default='kg')

    estimasi_jumlah_kemasan = models.PositiveIntegerField(null=True, blank=True)
    jumlah_kemasan = models.PositiveIntegerField(null=True, blank=True)
    satuan_kemasan = models.CharField(max_length=10, choices=[
        ('Pcs', 'Pcs'), ('Karton', 'Karton')
    ], null=True, blank=True)

    ruangan = models.ForeignKey(Ruangan, on_delete=models.CASCADE, db_index=True)
    waktu_dibuat = models.DateTimeField(auto_now_add=True)
    waktu_mulai_produksi = models.DateTimeField(null=True, blank=True)
    waktu_selesai = models.DateTimeField(null=True, blank=True)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, null=True, blank=True)
    progress = models.PositiveIntegerField(default=0)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['nomor_batch', 'ruangan'],
                name='uniq_nomor_batch_per_ruangan',
            ),
        ]  
    def __str__(self):
    
        return f"{self.nomor_batch} - {self.nama.description}"
    
    @property
    def progress_percentage(self):
        if self.jumlah > 0:
            return round((self.progress / self.jumlah) * 100, 2)
        return 0

    def clean(self):
        # Unik per ruangan, bukan global
        qs = ProsesProduksi.objects.filter(
            nomor_batch=self.nomor_batch,
            ruangan=self.ruangan,
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError({"nomor_batch": "Nomor batch sudah ada di ruangan ini."})

        # Validasi khusus saat Labelling menandai selesai
        if (
            self.status == "Selesai Produksi"
            and (self.ruangan and (self.ruangan.nama or "").lower().__contains__("labell"))
            and (not self.jumlah_kemasan or not self.satuan_kemasan)
        ):
            raise ValidationError("Jumlah kemasan dan satuan kemasan harus diisi di ruangan Labelling.")
    

    def save(self, *args, **kwargs):
        self.clean()

        if self.status == "Sedang diproses" and not self.waktu_mulai_produksi:
            self.waktu_mulai_produksi = now()

        super().save(*args, **kwargs)

    def is_labelling(self):
        return self.ruangan.nama.lower() == "labelling"

    @property
    def progress_display(self):
        return f"{(self.progress / self.jumlah * 100):.0f}%" if self.jumlah else "0%"

    @property
    def progress_labelling_display(self):
        if self.jumlah_kemasan and self.jumlah:
            return f"{self.jumlah_kemasan} / {self.jumlah} {self.get_satuan_kemasan_display()}"
        return "-"
    
    @property
    def sisa_kemasan(self):
        """
        Sisa target kemasan untuk ruangan Labelling.
        Dipakai untuk membatasi penambahan agar tidak lewat estimasi.
        """
        if self.estimasi_jumlah_kemasan is None:
            return None
        current = self.jumlah_kemasan or 0
        return max(self.estimasi_jumlah_kemasan - current, 0)

    class Meta:
        verbose_name = "Proses Produksi"
        verbose_name_plural = "Proses Produksi"
        ordering = ("-waktu_dibuat",)

class RiwayatProduksi(models.Model):
    nomor_batch = models.CharField(max_length=20)
    nama_produk = models.ForeignKey(ItemDescription, on_delete=models.CASCADE)
    jumlah = models.PositiveIntegerField()
    satuan = models.CharField(max_length=10)
    ruangan = models.ForeignKey(Ruangan, on_delete=models.CASCADE)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, null=True, blank=True)
    waktu_mulai_produksi = models.DateTimeField()
    waktu_selesai = models.DateTimeField()
    hasil_akhir = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"Riwayat: {self.nomor_batch} di {self.ruangan.nama}"


class IdempotencyKey(models.Model):
    key = models.CharField(max_length=64, unique=True, db_index=True)
    action = models.CharField(max_length=50, default="labelling_update")  # jenis aksi, bisa disesuaikan
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Idempotency Key"
        verbose_name_plural = "Idempotency Keys"

    def __str__(self):
        return f"{self.action}:{self.key[:8]}"
