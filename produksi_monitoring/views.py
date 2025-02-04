from django.shortcuts import render, get_object_or_404
from django.utils.timezone import now, timedelta
from .models import Ruangan, ProsesProduksi

def monitoring_produksi_per_ruangan(request, ruangan_nama):
    ruangan = get_object_or_404(Ruangan, nama=ruangan_nama)

    # 🔥 Ambil data dan pisahkan statusnya
    proses_produksi = ProsesProduksi.objects.filter(ruangan=ruangan)
    menunggu = proses_produksi.filter(status__iexact="Menunggu").order_by('waktu_mulai_produksi')
    diproses = proses_produksi.filter(status__iexact="Sedang Diproses").order_by('waktu_mulai_produksi')

    # ✅ Ambil proses selesai dengan urutan terbaru
    selesai = proses_produksi.filter(
        status__iexact="Selesai", 
        waktu_selesai__isnull=False
    ).order_by('-waktu_selesai')  # 🔥 Urutkan dari yang terbaru ke yang lama

    # ✅ Jika hanya ingin menampilkan produksi selesai dalam 1 bulan terakhir, aktifkan baris ini:
    # selesai = selesai.filter(waktu_selesai__gte=now()-timedelta(days=30))

    # 🔥 Debugging untuk memastikan data benar-benar ada
    print(f"DEBUG: monitoring_produksi_per_ruangan -> Proses Menunggu: {menunggu.count()}")
    print(f"DEBUG: monitoring_produksi_per_ruangan -> Proses Sedang Diproses: {diproses.count()}")
    print(f"DEBUG: monitoring_produksi_per_ruangan -> Proses Selesai: {selesai.count()}")

    context = {
        "ruangan": ruangan,
        "proses_menunggu": menunggu,
        "proses_diproses": diproses,
        "proses_selesai": selesai,
    }
    return render(request, 'produksi_monitoring/monitoring_ruangan.html', context)


def dashboard(request):
    ruangan_list = Ruangan.objects.all()
    context = {'ruangan_list': ruangan_list}
    return render(request, 'produksi_monitoring/dashboard.html', context)


def monitoring_ruangan(request, ruangan_nama):
    ruangan = get_object_or_404(Ruangan, nama=ruangan_nama)
    print(f"DEBUG: Ruangan ditemukan -> {ruangan}")

    # 🔥 UPDATE OTOMATIS STATUS
    ProsesProduksi.objects.filter(
        status__iexact="Menunggu", waktu_mulai_produksi__lte=now()
    ).update(status="Sedang Diproses")
    print("DEBUG: Status 'Menunggu' yang waktunya sudah lewat diubah menjadi 'Sedang Diproses'.")

    # 🔥 Ambil ulang data setelah update agar perubahan status terbaca
    proses_produksi = ProsesProduksi.objects.filter(ruangan=ruangan)
    print(f"DEBUG: Total proses produksi ditemukan -> {proses_produksi.count()}")

    # ✅ Ambil data dengan pemisahan status
    menunggu = proses_produksi.filter(status__iexact="Menunggu").order_by('waktu_mulai_produksi')
    diproses = proses_produksi.filter(status__iexact="Sedang Diproses").order_by('waktu_mulai_produksi')

    selesai = proses_produksi.filter(
        status__iexact="Selesai", 
        waktu_selesai__isnull=False
    ).order_by('-waktu_selesai')  # 🔥 Urutkan dari yang terbaru ke yang lama

    # ✅ Jika hanya ingin menampilkan produksi selesai dalam 1 bulan terakhir, aktifkan baris ini:
    # selesai = selesai.filter(waktu_selesai__gte=now()-timedelta(days=30))

    print(f"DEBUG: Proses Menunggu -> {menunggu.count()}")
    print(f"DEBUG: Proses Sedang Diproses -> {diproses.count()}")
    print(f"DEBUG: Proses Selesai -> {selesai.count()}")

    context = {
        "ruangan": ruangan,
        "proses_menunggu": menunggu,
        "proses_diproses": diproses,
        "proses_selesai": selesai,
    }

    return render(request, "produksi_monitoring/monitoring_ruangan.html", context)
