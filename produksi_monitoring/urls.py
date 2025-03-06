from django.urls import path
from .views import (
    dashboard,
    monitoring_produksi_per_ruangan,
    pindahkan_batch_ke_ruangan_form,
    pilih_ruangan_proses,
    tandai_sedang_diproses,
    operator_tandai_selesai,
    update_progress
)

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('monitoring/<slug:ruangan_nama>/', monitoring_produksi_per_ruangan, name='monitoring_per_ruangan'),
    path('monitoring/pindahkan_batch/<str:nomor_batch>/', pindahkan_batch_ke_ruangan_form, name="pindahkan_batch_ke_ruangan"),
    path('pilih_ruangan_proses/', pilih_ruangan_proses, name="pilih_ruangan_proses"),
    path("tandai_sedang_diproses/<int:produksi_id>/", tandai_sedang_diproses, name="tandai_sedang_diproses"),
    path("operator/tandai-selesai/<int:produksi_id>/", operator_tandai_selesai, name="operator_tandai_selesai"),
    path("update_progress/<int:produksi_id>/", update_progress, name="update_progress"),

]
