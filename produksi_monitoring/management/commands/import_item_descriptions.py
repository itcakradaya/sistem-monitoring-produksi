import pandas as pd
from django.core.management.base import BaseCommand
from produksi_monitoring.models import ItemDescription

class Command(BaseCommand):
    help = "Memperbarui Master Item dari file Excel"

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help="Path ke file Excel")

    def handle(self, *args, **options):
        file_path = options['file_path']
        self.stdout.write(f"📂 Membaca file: {file_path}")

        try:
            df = pd.read_excel(file_path, dtype={"Barcode": str, "Item Description": str})
            for _, row in df.iterrows():
                barcode = row["Barcode"]
                description = row["Item Description"]

                item, created = ItemDescription.objects.update_or_create(
                    description=description,  # Pastikan deskripsi unik
                    defaults={"barcode": barcode}
                )

                if created:
                    self.stdout.write(f"✅ Item baru ditambahkan: {description} ({barcode})")
                else:
                    self.stdout.write(f"♻️ Item diperbarui: {description} ({barcode})")

            self.stdout.write("🎉 Update Master Item selesai!")

        except Exception as e:
            self.stderr.write(f"❌ Error saat memproses file: {e}")
