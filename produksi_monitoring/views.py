from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now
from django.urls import reverse
from django.utils.text import slugify
from .models import Ruangan, ProsesProduksi

def dashboard(request):
    """Menampilkan daftar ruangan produksi yang tersedia."""
    ruangan_list = Ruangan.objects.all()
    context = {'ruangan_list': ruangan_list}
    return render(request, 'produksi_monitoring/dashboard.html', context)

def monitoring_produksi_per_ruangan(request, ruangan_nama):
    """Menampilkan daftar produksi di ruangan tertentu, termasuk batch yang pernah melewati ruangan ini."""
    ruangan = get_object_or_404(Ruangan, nama__iexact=ruangan_nama.replace("-", " "))

    # 🔄 Perbarui status otomatis jika waktu mulai produksi telah tercapai
    updated_count = ProsesProduksi.objects.filter(
        status="Menunggu", waktu_mulai_produksi__lte=now()
    ).update(status="Sedang Diproses")

    print(f"DEBUG: {updated_count} item diperbarui menjadi 'Sedang Diproses'.")

    # 🔥 Ambil data produksi saat ini di ruangan ini
    proses_produksi = ProsesProduksi.objects.filter(ruangan=ruangan)
    menunggu = proses_produksi.filter(status="Menunggu").order_by('waktu_mulai_produksi')
    diproses = proses_produksi.filter(status="Sedang Diproses").order_by('waktu_mulai_produksi')
    siap_pindah = proses_produksi.filter(status="Siap Dipindahkan").order_by('-waktu_selesai')

    # 🔹 Ambil batch yang pernah diproses di ruangan ini
    batch_yang_pernah_di_ruangan = ProsesProduksi.objects.filter(
        nomor_batch__in=ProsesProduksi.objects.filter(
            ruangan__nama=ruangan_nama
        ).values_list('nomor_batch', flat=True)
    ).values_list('nomor_batch', flat=True).distinct()

    # 🔹 Ambil riwayat produksi untuk batch tersebut, meskipun selesai di ruangan lain
    selesai = ProsesProduksi.objects.filter(
        nomor_batch__in=batch_yang_pernah_di_ruangan,
        status__in=["Selesai", "Selesai Produksi"]
    ).order_by('-waktu_selesai')

    print(f"DEBUG: Ruangan: {ruangan_nama}, Total Selesai: {selesai.count()}")
    for produk in selesai:
        print(f"DEBUG: Batch: {produk.nomor_batch}, Selesai di {produk.ruangan.nama}, Waktu: {produk.waktu_selesai}")

    context = {
        "ruangan": ruangan,
        "proses_menunggu": menunggu,
        "proses_diproses": diproses,
        "proses_siap_pindah": siap_pindah,
        "proses_selesai": selesai,  # ⬅️ Tampilkan batch yang pernah melewati ruangan ini
    }
    return render(request, 'produksi_monitoring/monitoring_ruangan.html', context)


def monitoring_ruangan(request, ruangan_nama):
    """Menampilkan monitoring produksi untuk ruangan tertentu."""
    ruangan = get_object_or_404(Ruangan, nama__iexact=ruangan_nama.replace("-", " "))

    print(f"DEBUG: Ruangan ditemukan -> {ruangan}")

    # 🔄 Perbarui status otomatis jika waktu mulai produksi telah tercapai
    updated_count = ProsesProduksi.objects.filter(
        status="Menunggu", waktu_mulai_produksi__lte=now()
    ).update(status="Sedang Diproses")

    print(f"DEBUG: {updated_count} item diperbarui menjadi 'Sedang Diproses'.")

    # 🔥 Ambil ulang data setelah update agar perubahan status terbaca
    proses_produksi = ProsesProduksi.objects.filter(ruangan=ruangan)

    menunggu = proses_produksi.filter(status="Menunggu").order_by('waktu_mulai_produksi')
    diproses = proses_produksi.filter(status="Sedang Diproses").order_by('waktu_mulai_produksi')
    siap_pindah = proses_produksi.filter(status="Siap Dipindahkan").order_by('-waktu_selesai')

    # 🔹 Ambil semua batch yang pernah diproses di ruangan ini
    selesai = ProsesProduksi.objects.filter(
        nomor_batch__in=proses_produksi.values_list('nomor_batch', flat=True),
        status__in=["Selesai", "Selesai Produksi"]
    ).order_by('-waktu_selesai')

    print(f"DEBUG: {ruangan_nama} - Menunggu: {menunggu.count()}, Sedang Diproses: {diproses.count()}, "
          f"Siap Dipindahkan: {siap_pindah.count()}, Selesai (di semua ruangan): {selesai.count()}")

    context = {
        "ruangan": ruangan,
        "proses_menunggu": menunggu,
        "proses_diproses": diproses,
        "proses_siap_pindah": siap_pindah,
        "proses_selesai": selesai,  # ⬅️ Memastikan batch selesai selalu muncul
    }
    return render(request, "produksi_monitoring/monitoring_ruangan.html", context)

def tandai_siap_dipindahkan(request, produksi_id):
    """Menandai batch yang sedang diproses menjadi 'Siap Dipindahkan'."""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if produksi.status == "Sedang Diproses":
        produksi.status = "Siap Dipindahkan"
        produksi.waktu_selesai = now()  # Simpan waktu selesai
        produksi.save()
        print(f"DEBUG: {produksi.nomor_batch} sekarang 'Siap Dipindahkan'.")
    else:
        print(f"DEBUG: {produksi.nomor_batch} tidak bisa ditandai siap dipindahkan.")

    return redirect(reverse('monitoring_per_ruangan', args=[slugify(produksi.ruangan.nama)]))

def pindahkan_batch_ke_ruangan(request, produksi_id):
    """Menampilkan jendela pop-up untuk memilih ruangan tujuan dan memindahkan batch."""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if request.method == "POST":
        ruangan_id = request.POST.get("ruangan_tujuan")
        ruangan_tujuan = get_object_or_404(Ruangan, id=ruangan_id)

        # Cukup update ruangan dan status tanpa membuat data baru
        produksi.ruangan = ruangan_tujuan
        produksi.status = "Menunggu"
        produksi.waktu_mulai_produksi = None
        produksi.save()

        print(f"DEBUG: {produksi.nomor_batch} berhasil dipindahkan ke {ruangan_tujuan.nama}.")

        return redirect("admin:produksi_monitoring_prosesproduksi_changelist")  # Tutup pop-up

    ruangan_list = Ruangan.objects.exclude(id=produksi.ruangan.id)
    return render(request, "produksi_monitoring/popup_pindah_ruangan.html", {"produksi": produksi, "ruangan_list": ruangan_list})

def pilih_ruangan_proses(request):
    """Popup untuk memilih ruangan tujuan jika batch berasal dari Ruang Penimbangan."""
    batch_ids = request.session.get('batch_to_move', [])

    if not batch_ids:
        return redirect("admin:produksi_monitoring_prosesproduksi_changelist")

    batch_list = ProsesProduksi.objects.filter(pk__in=batch_ids)

    # **🔹 Cek apakah ada ruangan untuk tujuan proses**
    ruangan_list = Ruangan.objects.exclude(nama__icontains="penimbangan")  # Jangan tampilkan ruang penimbangan

    if request.method == "POST":
        ruangan_id = request.POST.get("ruangan_tujuan")
        ruangan_tujuan = get_object_or_404(Ruangan, id=ruangan_id)

        for batch in batch_list:
            batch.ruangan = ruangan_tujuan
            batch.status = "Menunggu"
            batch.waktu_mulai_produksi = None
            batch.waktu_selesai = now()
            batch.save()

        del request.session['batch_to_move']  # Hapus session setelah diproses
        return redirect("admin:produksi_monitoring_prosesproduksi_changelist")

    return render(request, "produksi_monitoring/popup_pilih_ruangan.html", {
        "batch_list": batch_list, 
        "ruangan_list": ruangan_list  # ✅ Pastikan variabel ini dikirim
    })