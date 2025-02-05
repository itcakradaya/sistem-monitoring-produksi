from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now, timedelta
from django.urls import reverse
from .models import Ruangan, ProsesProduksi

def dashboard(request):
    """Menampilkan daftar ruangan produksi yang tersedia."""
    ruangan_list = Ruangan.objects.all()
    context = {'ruangan_list': ruangan_list}
    return render(request, 'produksi_monitoring/dashboard.html', context)

def monitoring_produksi_per_ruangan(request, ruangan_nama):
    """Menampilkan daftar produksi di ruangan tertentu."""
    ruangan = get_object_or_404(Ruangan, nama=ruangan_nama)

    # 🔥 Ambil data berdasarkan status produksi
    proses_produksi = ProsesProduksi.objects.filter(ruangan=ruangan)
    menunggu = proses_produksi.filter(status="Menunggu Proses").order_by('waktu_mulai_produksi')
    diproses = proses_produksi.filter(status__iexact="Sedang Diproses").order_by('waktu_mulai_produksi')
    selesai = proses_produksi.filter(status="Selesai").order_by('-waktu_selesai')

    # ✅ Jika hanya ingin menampilkan produksi selesai dalam 1 bulan terakhir:
    # selesai = selesai.filter(waktu_selesai__gte=now()-timedelta(days=30))

    print(f"DEBUG: {ruangan_nama} - Menunggu: {menunggu.count()}, Diproses: {diproses.count()}, Selesai: {selesai.count()}")

    context = {
        "ruangan": ruangan,
        "proses_menunggu": menunggu,
        "proses_diproses": diproses,
        "proses_selesai": selesai,
    }
    return render(request, 'produksi_monitoring/monitoring_ruangan.html', context)

def monitoring_ruangan(request, ruangan_nama):
    """Menampilkan monitoring produksi untuk ruangan tertentu."""
    ruangan = get_object_or_404(Ruangan, nama=ruangan_nama)
    print(f"DEBUG: Ruangan ditemukan -> {ruangan}")

    # 🔄 Perbarui status otomatis jika waktu mulai produksi telah tercapai
    updated_count = ProsesProduksi.objects.filter(
        status="Menunggu Proses", waktu_mulai_produksi__lte=now()
    ).update(status="Sedang Diproses")

    print(f"DEBUG: {updated_count} item diperbarui menjadi 'Sedang Diproses'.")

    # 🔥 Ambil ulang data setelah update agar perubahan status terbaca
    proses_produksi = ProsesProduksi.objects.filter(ruangan=ruangan)
    print(f"DEBUG: Total proses produksi ditemukan -> {proses_produksi.count()}")

    menunggu = proses_produksi.filter(status="Menunggu Proses").order_by('waktu_mulai_produksi')
    diproses = proses_produksi.filter(status__iexact="Sedang Diproses").order_by('waktu_mulai_produksi')
    selesai = proses_produksi.filter(status="Selesai").order_by('-waktu_selesai')

    print(f"DEBUG: Proses Menunggu -> {menunggu.count()}, Sedang Diproses -> {diproses.count()}, Selesai -> {selesai.count()}")

    context = {
        "ruangan": ruangan,
        "proses_menunggu": menunggu,
        "proses_diproses": diproses,
        "proses_selesai": selesai,
    }

    return render(request, "produksi_monitoring/monitoring_ruangan.html", context)

def pindah_ke_tahap_berikutnya(request, produksi_id):
    """Memindahkan batch produksi yang sudah selesai ke tahap berikutnya."""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if produksi.status == "Sedang Diproses":
        produksi.status = "Selesai"
        produksi.waktu_selesai = now()
        produksi.save()
        produksi.pindah_ke_tahap_berikutnya()

    return redirect(reverse('monitoring_produksi_per_ruangan', args=[produksi.ruangan.nama]))
