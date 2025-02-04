from django.urls import path
from .views import dashboard, monitoring_produksi_per_ruangan 

urlpatterns = [
    path('', dashboard, name='dashboard'),  # Dashboard utama
    path('monitoring/<str:ruangan_nama>/', monitoring_produksi_per_ruangan, name='monitoring_per_ruangan'),
]
