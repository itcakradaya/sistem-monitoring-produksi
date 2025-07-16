from django.core.management.base import BaseCommand
from produksi_monitoring.models import RiwayatProduksi

class Command(BaseCommand):
    help = 'Menghapus semua data dari RiwayatProduksi (semua ruangan)'

    def handle(self, *args, **options):
        total = RiwayatProduksi.objects.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('Tidak ada data untuk dihapus.'))
            return

        RiwayatProduksi.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Berhasil menghapus {total} data dari RiwayatProduksi.'))
