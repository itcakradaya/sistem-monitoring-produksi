# Generated by Django 4.2.15 on 2025-01-31 15:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produksi_monitoring', '0006_alter_prosesproduksi_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemDescription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=255)),
            ],
        ),
    ]
