from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now, timedelta
from django.urls import reverse
from django.utils.text import slugify
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.middleware.csrf import get_token
from django.contrib import messages
from .models import Ruangan, ProsesProduksi, Operator, RiwayatProduksi  
from django.db import transaction

def dashboard(request):
    """Menampilkan daftar ruangan produksi yang tersedia."""
    ruangan_list = Ruangan.objects.all()
    return render(request, 'produksi_monitoring/dashboard.html', {"ruangan_list": ruangan_list})

@login_required
def monitoring_produksi_per_ruangan(request, ruangan_nama):
    """Menampilkan monitoring produksi untuk ruangan tertentu."""
    ruangan = get_object_or_404(Ruangan, nama__iexact=ruangan_nama.replace("-", " "))

    # 🔄 Update status otomatis jika produksi sudah waktunya diproses
    ProsesProduksi.objects.filter(status="Menunggu", waktu_mulai_produksi__lte=now()).update(status="Sedang Diproses")

    proses_produksi = ProsesProduksi.objects.filter(ruangan=ruangan)
    menunggu = proses_produksi.filter(status="Menunggu").order_by('waktu_mulai_produksi')
    diproses = proses_produksi.filter(status="Sedang Diproses").order_by('waktu_mulai_produksi')
    siap_pindah = proses_produksi.filter(status="Siap Dipindahkan").order_by('-waktu_selesai')

    tujuh_hari_lalu = now() - timedelta(days=7)
    batch_pernah_di_ruangan = ProsesProduksi.objects.filter(
        nomor_batch__in=proses_produksi.values_list('nomor_batch', flat=True),
        waktu_selesai__gte=tujuh_hari_lalu
    ).values_list('nomor_batch', flat=True).distinct()

    selesai = RiwayatProduksi.objects.filter(
    ruangan=ruangan
    ).select_related('ruangan').order_by('-waktu_selesai')

    for produk in diproses:
        produk.progress_percentage = produk.progress_percentage 
        
    return render(request, "produksi_monitoring/monitoring_ruangan.html", {
        "ruangan": ruangan,
        "proses_menunggu": menunggu,
        "proses_diproses": diproses,
        "proses_siap_pindah": siap_pindah,
        "proses_selesai": selesai,
    })

# ✅ OPERATOR MENANDAI SELESAI
@login_required
def operator_tandai_selesai(request, produksi_id):
    """Operator menandai proses telah selesai dan menunggu verifikasi admin"""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if produksi.status != "Sedang Diproses":
        messages.error(request, "Hanya proses dengan status 'Sedang Diproses' yang bisa ditandai selesai.")
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

    produksi.status = "Menunggu Verifikasi Admin"
    produksi.waktu_selesai = now()
    produksi.save()

    messages.success(request, f"Batch {produksi.nomor_batch} telah ditandai selesai dan menunggu verifikasi admin.")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

@login_required
def pindahkan_batch_ke_ruangan_form(request, nomor_batch):
    """Menampilkan halaman pindah batch dengan form pemilihan ruangan dan operator"""
    print(f"✅ DEBUG: Mencari produksi dengan Nomor Batch={nomor_batch}")

    produksi = get_object_or_404(ProsesProduksi, nomor_batch=nomor_batch)
    
    # ✅ Cek apakah batch berasal dari Labelling
    if produksi.ruangan.nama.lower() == "labelling":
        messages.error(request, "Batch dari ruang Labelling tidak bisa dipindahkan ke ruangan sebelumnya.")
        return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

    if not produksi.status.startswith("Selesai Diproses di"):
        messages.error(request, "Batch hanya bisa dipindahkan setelah selesai diproses di ruangan ini.")
        return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

    if request.method == "POST":
        ruangan_id = request.POST.get("ruangan_tujuan")
        operator_id = request.POST.get("operator_id")

        if not ruangan_id or not operator_id:
            messages.error(request, "Ruangan dan Operator harus dipilih!")
            return redirect("pindahkan_batch_ke_ruangan", nomor_batch=nomor_batch)

        ruangan_tujuan = get_object_or_404(Ruangan, id=ruangan_id)
        operator_tujuan = get_object_or_404(Operator, id=operator_id)

        print(f"✅ DEBUG: Memindahkan batch {produksi.nomor_batch} ke {ruangan_tujuan.nama} dengan operator {operator_tujuan.nama}")

        # ✅ Update produksi
        produksi.ruangan = ruangan_tujuan
        produksi.operator = operator_tujuan
        produksi.status = "Menunggu"
        produksi.waktu_mulai_produksi = None
        produksi.save()

        messages.success(request, f"Batch {produksi.nomor_batch} berhasil dipindahkan ke {ruangan_tujuan.nama}.")
        return redirect("monitoring_per_ruangan", ruangan_nama=slugify(ruangan_tujuan.nama))

    return render(request, "produksi_monitoring/pindahkan_batch.html", {
        "produksi": produksi,
        "ruangan_list": Ruangan.objects.exclude(id=produksi.ruangan.id),
        "operator_list": Operator.objects.all(),
    })


# ✅ PILIH RUANGAN UNTUK PROSES PINDAH BATCH
@login_required
def pilih_ruangan_proses(request):
    """Admin memilih ruangan tujuan dan operator untuk batch yang selesai diproses"""
    batch_ids = request.session.get('batch_to_move', [])

    if not batch_ids:
        messages.error(request, "Tidak ada batch yang bisa dipindahkan.")
        return redirect("admin:produksi_monitoring_prosesproduksi_changelist")

    batch_list = ProsesProduksi.objects.filter(pk__in=batch_ids)

    if request.method == "POST":
        ruangan_id = request.POST.get("ruangan_tujuan")
        operator_id = request.POST.get("operator_id")

        if not ruangan_id or not operator_id:
            messages.error(request, "Ruangan dan Operator harus dipilih!")
            return redirect(request.path)

        ruangan_tujuan = get_object_or_404(Ruangan, id=ruangan_id)
        operator_tujuan = get_object_or_404(Operator, id=operator_id)

        for produksi in batch_list:
            produksi.ruangan = ruangan_tujuan
            produksi.operator = operator_tujuan
            produksi.status = "Menunggu"
            produksi.waktu_mulai_produksi = None
            produksi.save()

        messages.success(request, f"{len(batch_list)} batch berhasil dipindahkan ke {ruangan_tujuan.nama}.")
        return redirect("admin:produksi_monitoring_prosesproduksi_changelist")

    return render(request, "admin/pilih_ruangan.html", {
        "batch_list": batch_list,
        "ruangan_list": Ruangan.objects.exclude(nama__icontains="penimbangan"),
        "operator_list": Operator.objects.all(),
    })

@login_required
def tandai_sedang_diproses(request, produksi_id):
    """Operator menandai proses produksi sebagai 'Sedang Diproses'."""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if produksi.status == "Menunggu":
        produksi.status = "Sedang Diproses"
        produksi.waktu_mulai_produksi = now()
        produksi.progress = 0  # ✅ Pastikan progress bisa di-set ke 0
        produksi.save()

        messages.success(request, f"Batch {produksi.nomor_batch} sekarang sedang diproses.")
    else:
        messages.error(request, "Batch ini tidak bisa ditandai sedang diproses.")

    return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))


@login_required
def update_progress(request, produksi_id):
    """Update progress produksi berdasarkan ruangan saat ini"""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if request.method == "POST":
        jumlah_terproses = int(request.POST.get("jumlah_terproses", 0))

        if jumlah_terproses < 1:
            messages.error(request, "Jumlah yang diproses harus lebih dari 0.")
            return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

        produksi.progress += jumlah_terproses
        if produksi.progress >= produksi.jumlah:
            produksi.progress = produksi.jumlah
            produksi.status = f"Selesai Diproses di {produksi.ruangan.nama}"
            produksi.waktu_selesai = now()

            
            # Simpan ke Riwayat Produksi kalau belum ada
            with transaction.atomic():
                riwayat, created = RiwayatProduksi.objects.get_or_create(
                    nomor_batch=produksi.nomor_batch,
                    nama_produk=produksi.nama,
                    jumlah=produksi.jumlah,
                    satuan=produksi.satuan,
                    ruangan=produksi.ruangan,
                    operator=produksi.operator,
                    waktu_mulai_produksi=produksi.waktu_mulai_produksi,
                    waktu_selesai=produksi.waktu_selesai
                )

        produksi.save()

        messages.success(request, f"Batch {produksi.nomor_batch} selesai diproses di {produksi.ruangan.nama}.")
        return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))



def tandai_selesai_oleh_operator(request, produksi_id):
    """Operator menandai proses produksi selesai dan menunggu verifikasi admin."""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if produksi.status == "Sedang Diproses":
        produksi.status = "Menunggu Verifikasi Admin"
        produksi.waktu_selesai = now()
        produksi.save()
        print(f"DEBUG: {produksi.nomor_batch} sekarang 'Menunggu Verifikasi Admin'.")

    return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

# ✅ MENANDAI PRODUKSI SIAP DIPINDAHKAN
def tandai_siap_dipindahkan(request, produksi_id):
    """Menandai batch yang sedang diproses menjadi 'Siap Dipindahkan'."""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if produksi.status == "Sedang Diproses":
        produksi.status = "Siap Dipindahkan"
        produksi.waktu_selesai = now()
        produksi.save()
        print(f"DEBUG: {produksi.nomor_batch} sekarang 'Siap Dipindahkan'.")
    else:
        print(f"DEBUG: {produksi.nomor_batch} tidak bisa ditandai siap dipindahkan.")

    return redirect(reverse('monitoring_per_ruangan', args=[slugify(produksi.ruangan.nama)]))

@login_required
def tandai_selesai_labelling(request, nomor_batch):
    """Operator menandai batch selesai di ruang labelling"""
    produksi = get_object_or_404(ProsesProduksi, nomor_batch=nomor_batch)

    if produksi.jumlah_kemasan is None or produksi.jumlah_kemasan <= 0:
        messages.error(request, "Silakan input jumlah kemasan sebelum menandai selesai!")
        return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

    produksi.status = "Selesai Produksi"
    produksi.waktu_selesai = now()
    produksi.save()

    messages.success(request, f"Batch {produksi.nomor_batch} telah ditandai selesai produksi.")
    return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))
