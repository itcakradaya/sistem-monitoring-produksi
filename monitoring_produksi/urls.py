from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('monitoring/', include('produksi_monitoring.urls')),  # Hubungkan ke aplikasi monitoring
]

# Jika dalam mode DEBUG, tambahkan URL untuk mengakses file statis dengan aman
if settings.DEBUG:
    static_dirs = getattr(settings, 'STATICFILES_DIRS', [])
    if static_dirs:  
        urlpatterns += static(settings.STATIC_URL, document_root=static_dirs[0])