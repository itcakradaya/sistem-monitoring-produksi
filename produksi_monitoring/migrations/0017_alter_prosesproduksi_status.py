# Generated by Django 4.2.15 on 2025-02-09 10:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produksi_monitoring', '0016_alter_mesin_options_alter_ruangan_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prosesproduksi',
            name='status',
            field=models.CharField(choices=[('Menunggu', 'Menunggu Proses'), ('Sedang diproses', 'Sedang Diproses'), ('Siap Dipindahkan', 'Siap Dipindahkan'), ('Selesai', 'Selesai')], default='Menunggu', max_length=20),
        ),
    ]
