from django.urls import path
from .views import (
    dashboard, 
    monitoring_produksi_per_ruangan, 
    pindahkan_batch_ke_ruangan
  
   )

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('monitoring/<slug:ruangan_nama>/', monitoring_produksi_per_ruangan, name='monitoring_per_ruangan'),
    path('pindahkan_batch/<int:produksi_id>/', pindahkan_batch_ke_ruangan, name="pindahkan_batch_ke_ruangan"),
]
