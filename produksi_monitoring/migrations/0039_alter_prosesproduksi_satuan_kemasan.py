# Generated by Django 4.2.15 on 2025-03-25 07:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produksi_monitoring', '0038_alter_prosesproduksi_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prosesproduksi',
            name='satuan_kemasan',
            field=models.CharField(blank=True, choices=[('Pcs', 'Pieces'), ('Karton', 'Karton')], max_length=10, null=True),
        ),
    ]
