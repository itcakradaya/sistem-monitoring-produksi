# Generated by Django 4.2.15 on 2025-02-03 07:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produksi_monitoring', '0010_alter_ruangan_jenis_proses'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prosesproduksi',
            name='status',
            field=models.CharField(choices=[('Menunggu', 'Menunggu Proses'), ('Sedang diproses', 'Sedang Diproses')], default='menunggu', max_length=20),
        ),
    ]
