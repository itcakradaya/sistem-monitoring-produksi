from django.urls import path
from . import views
from .views import (
    dashboard,
    monitoring_produksi_per_ruangan,
    pindahkan_batch_ke_ruangan_form,
    pilih_ruangan_proses,
    tandai_sedang_diproses,
    update_progress,
    tandai_selesai_labelling,
    operator_tentukan_hasil_akhir,
)

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('get_produksi_data/', views.get_produksi_data, name='get_produksi_data'),

    # Monitoring index harus sebelum slug
    path("monitoring/", views.monitoring_index, name="monitoring_index"),
    # urls.py
    path("monitoring/<slug:ruangan_slug>/", monitoring_produksi_per_ruangan, name='monitoring_per_ruangan'),

    # Update progress dan status produksi oleh operator
    path("update_progress/<int:produksi_id>/", update_progress, name="update_progress"),
    path("tandai_sedang_diproses/<int:produksi_id>/", tandai_sedang_diproses, name="tandai_sedang_diproses"),

    # Admin memindahkan batch
    path('monitoring/pindahkan_batch/<str:nomor_batch>/', pindahkan_batch_ke_ruangan_form, name="pindahkan_batch_ke_ruangan"),
    path('pilih_ruangan_proses/', pilih_ruangan_proses, name="pilih_ruangan_proses"),

    # Operator menandai selesai di ruangan labelling
    path("tandai_selesai_labelling/<str:nomor_batch>/", tandai_selesai_labelling, name="tandai_selesai_labelling"),

    # Operator tentukan hasil akhir
    path("operator/hasil-akhir/<int:produksi_id>/", operator_tentukan_hasil_akhir, name="operator_tentukan_hasil_akhir"),
]
