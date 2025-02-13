from django.core.management.base import BaseCommand
from django.utils import timezone
from produksi_monitoring.models import ProsesProduksi, Ruangan

class Command(BaseCommand):
    help = "Update status produksi secara otomatis saat waktu mulai produksi tercapai untuk Ruang Penimbangan"

    def handle(self, *args, **kwargs):
        now = timezone.now()  # ✅ Ambil waktu sekarang
        self.stdout.write(self.style.NOTICE(f"DEBUG: Waktu sekarang -> {now}"))

        # ✅ Ambil Ruangan Penimbangan
        ruang_penimbangan = Ruangan.objects.filter(nama__icontains="Penimbangan").first()

        if not ruang_penimbangan:
            self.stdout.write(self.style.ERROR("Ruang Penimbangan tidak ditemukan!"))
            return

        # ✅ Cari proses produksi di Ruang Penimbangan yang statusnya masih "Menunggu" dan waktunya sudah lewat
        diproses = ProsesProduksi.objects.filter(
            status="Menunggu",
            waktu_mulai_produksi__lte=now,
            ruangan=ruang_penimbangan  # ✅ Pastikan hanya Ruang Penimbangan
        )

        if diproses.exists():
            self.stdout.write(self.style.SUCCESS(f"DEBUG: {diproses.count()} proses akan diperbarui ke 'Sedang Diproses'"))

            for proses in diproses:
                self.stdout.write(self.style.NOTICE(f"DEBUG: Mengupdate {proses.nomor_batch} - {proses.nama}"))
                proses.status = "Sedang Diproses"
                proses.save(update_fields=['status'])  # ✅ Simpan perubahan di database

        else:
            self.stdout.write(self.style.WARNING("Tidak ada proses produksi di Ruang Penimbangan yang perlu diperbarui."))
