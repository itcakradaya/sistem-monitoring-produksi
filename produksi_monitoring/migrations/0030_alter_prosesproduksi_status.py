# Generated by Django 4.2.15 on 2025-03-02 18:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produksi_monitoring', '0029_alter_prosesproduksi_operator'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prosesproduksi',
            name='status',
            field=models.CharField(choices=[('Menunggu', 'Menunggu Proses'), ('Sedang diproses', 'Sedang Diproses'), ('Menunggu Verifikasi Admin', 'Menunggu Verifikasi Admin'), ('Siap Dipindahkan', 'Siap Dipindahkan'), ('Selesai Produksi', 'Selesai Produksi')], default='Menunggu', max_length=30),
        ),
    ]
