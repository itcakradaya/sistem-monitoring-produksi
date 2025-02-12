from django.core.management.base import BaseCommand
from produksi_monitoring.models import ItemDescription

class Command(BaseCommand):
    help = "Menghapus semua data ItemDescription"

    def handle(self, *args, **kwargs):
        total_deleted, _ = ItemDescription.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"✅ Berhasil menghapus {total_deleted} item dari ItemDescription!"))
