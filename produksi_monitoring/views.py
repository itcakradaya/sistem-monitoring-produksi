from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now, timedelta
from django.urls import reverse
from django.utils.text import slugify
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Ruangan, ProsesProduksi, Operator, RiwayatProduksi  
from django.http import JsonResponse

def get_produksi_data(request):
    # Ambil seluruh data produksi di ruang penimbangan
    produksi_data = ProsesProduksi.objects.filter(ruangan__nama="Penimbangan").values(
        'nomor_batch',
        'nama_produk__description',  # Menampilkan nama produk
        'jumlah',
        'waktu_selesai',
        'operator__nama',  # Menampilkan nama operator
        'hasil_akhir'
    )
    
    # Mengirimkan data dalam format JSON
    return JsonResponse(list(produksi_data), safe=False)

def dashboard(request):
    """Menampilkan daftar ruangan produksi yang tersedia."""
    ruangan_list = Ruangan.objects.all()
    return render(request, 'produksi_monitoring/dashboard.html', {"ruangan_list": ruangan_list})

@login_required
def monitoring_produksi_per_ruangan(request, ruangan_slug):
    ruangan = get_object_or_404(Ruangan, slug=ruangan_slug)
    is_operator = request.user.groups.filter(name='operator').exists()


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
    # Ambil jumlah tampilan dari parameter GET
    limit = request.GET.get('limit', '10')

    riwayat_queryset = RiwayatProduksi.objects.filter(
        ruangan=ruangan
    ).select_related('ruangan').order_by('-waktu_selesai')

    # Batasi jumlah hasil sesuai pilihan user
    if limit != 'semua':
        try:
            limit_int = int(limit)
            riwayat_queryset = riwayat_queryset[:limit_int]
        except ValueError:
            riwayat_queryset = riwayat_queryset[:10]

    selesai = riwayat_queryset
    riwayat_labelling = None
    if "labelling" in ruangan.nama.lower():
        if limit != 'semua':
            try:
                limit_int = int(limit)
                riwayat_labelling = ProsesProduksi.objects.filter(
                    ruangan=ruangan,
                    status="Selesai Produksi"
                ).order_by('-waktu_selesai')[:limit_int]
            except ValueError:
                riwayat_labelling = ProsesProduksi.objects.filter(
                    ruangan=ruangan,
                    status="Selesai Produksi"
                ).order_by('-waktu_selesai')[:10]
        else:
            riwayat_labelling = ProsesProduksi.objects.filter(
                ruangan=ruangan,
                status="Selesai Produksi"
            ).order_by('-waktu_selesai')
        riwayat_labelling = None  # default None
    selesai = None  # default None

    if "labelling" in ruangan.nama.lower():
        # tampilkan khusus untuk Labelling
        if limit != 'semua':
            try:
                limit_int = int(limit)
                riwayat_labelling = ProsesProduksi.objects.filter(
                    ruangan=ruangan,
                    status="Selesai Produksi"
                ).order_by('-waktu_selesai')[:limit_int]
            except ValueError:
                riwayat_labelling = ProsesProduksi.objects.filter(
                    ruangan=ruangan,
                    status="Selesai Produksi"
                ).order_by('-waktu_selesai')[:10]
        else:
            riwayat_labelling = ProsesProduksi.objects.filter(
                ruangan=ruangan,
                status="Selesai Produksi"
            ).order_by('-waktu_selesai')

        # Hitung akurasi
        for item in riwayat_labelling:
            if item.estimasi_jumlah_kemasan and item.jumlah_kemasan:
                try:
                    item.akurasi_persen = round((item.jumlah_kemasan / item.estimasi_jumlah_kemasan) * 100, 2)
                except ZeroDivisionError:
                    item.akurasi_persen = 0
            else:
                item.akurasi_persen = None
    else:
        # ruangan lain pakai RiwayatProduksi
        riwayat_queryset = RiwayatProduksi.objects.filter(
            ruangan=ruangan
        ).select_related('ruangan').order_by('-waktu_selesai')

        if limit != 'semua':
            try:
                limit_int = int(limit)
                riwayat_queryset = riwayat_queryset[:limit_int]
            except ValueError:
                riwayat_queryset = riwayat_queryset[:10]

        selesai = riwayat_queryset

    if "labelling" in ruangan.nama.lower():
        return render(request, "produksi_monitoring/monitoring_ruangan.html", {
            "ruangan": ruangan,
            "proses_menunggu": menunggu,
            "proses_diproses": diproses,
            "proses_siap_pindah": siap_pindah,
            "proses_selesai": None,  # ⛔ Jangan tampilkan RiwayatProduksi
            "riwayat_produksi": riwayat_labelling,
            "limit": limit,
            "is_operator": is_operator, 
        })
    else:
        return render(request, "produksi_monitoring/monitoring_ruangan.html", {
            "ruangan": ruangan,
            "proses_menunggu": menunggu,
            "proses_diproses": diproses,
            "proses_siap_pindah": siap_pindah,
            "proses_selesai": selesai,
            "riwayat_produksi": None,  # ⛔ Jangan tampilkan ProsesProduksi untuk ruangan selain Labelling
            "limit": limit,
            "is_operator": is_operator, 
    })

    context = {
        "ruangan": ruangan,
        "proses_menunggu": menunggu,
        "proses_diproses": diproses,
        "proses_siap_pindah": siap_pindah,
        "limit": limit,
    }

    if "labelling" in ruangan.nama.lower():
        context["riwayat_produksi"] = riwayat_labelling
    else:
        context["proses_selesai"] = selesai

    return render(request, "produksi_monitoring/monitoring_ruangan.html", context)





      
      
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
def tandai_sedang_diproses(request, produksi_id):
    """Operator menandai proses produksi sebagai 'Sedang Diproses'."""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if produksi.status == "Menunggu":
        produksi.status = "Sedang Diproses"
        produksi.waktu_mulai_produksi = now()
        produksi.progress = 0
        produksi.save()

        messages.success(request, f"Batch {produksi.nomor_batch} sekarang sedang diproses.")
    else:
        messages.error(request, "Batch ini tidak bisa ditandai sedang diproses.")

    return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

@login_required
def pindahkan_batch_ke_ruangan_form(request, nomor_batch):
    """Menampilkan halaman pindah batch dengan form pemilihan ruangan dan operator"""
    print(f"✅ DEBUG: Mencari produksi dengan Nomor Batch={nomor_batch}")

    produksi = get_object_or_404(ProsesProduksi, nomor_batch=nomor_batch)
    if produksi.hasil_akhir == "Reject":
        messages.error(request, "Batch ini telah ditandai 'Reject' dan tidak bisa dipindahkan ke ruangan lain.")
        return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

    
    # ✅ Cek apakah batch berasal dari Labelling
    if produksi.ruangan.nama.lower() == "labelling":
        messages.error(request, "Batch dari ruang Labelling tidak bisa dipindahkan ke ruangan sebelumnya.")
        return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

    # Validasi pemindahan berdasarkan jenis ruangan
    if "proses" in produksi.ruangan.nama.lower():
        if produksi.hasil_akhir != "Release":
            messages.error(request, "Batch di ruang Proses hanya bisa dipindahkan jika hasil akhir adalah 'Release'.")
            return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))
    else:
        if produksi.status not in ["Selesai Produksi", f"Selesai Diproses di {produksi.ruangan.nama}"]:
            messages.error(request, "Batch hanya bisa dipindahkan setelah selesai diproses.")
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
def update_progress(request, produksi_id):
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if request.method == "POST":
        nama_ruangan = produksi.ruangan.nama.lower()

        # 💡 Ruang Labelling → input jumlah kemasan manual
        if "jumlah_kemasan" in request.POST:
            jumlah = int(request.POST.get("jumlah_kemasan", 0))
            satuan = request.POST.get("satuan_kemasan", "")
            if jumlah < 1:
                messages.error(request, "Jumlah kemasan harus lebih dari 0.")
                return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

            produksi.jumlah_kemasan = (produksi.jumlah_kemasan or 0) + jumlah
            produksi.satuan_kemasan = satuan
            produksi.save()
            messages.success(request, "Jumlah kemasan berhasil disimpan.")
            return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

        # 💡 Ruang lain → input jumlah_terproses
        jumlah_terproses = int(request.POST.get("jumlah_terproses", 0))

        if jumlah_terproses > 0:
            if produksi.progress + jumlah_terproses > produksi.jumlah:
                sisa = produksi.jumlah - produksi.progress
                messages.error(request, f"Jumlah terproses ({jumlah_terproses}) melebihi sisa target produksi ({sisa}).")
                return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

            produksi.progress += jumlah_terproses
            produksi.waktu_mulai_produksi = produksi.waktu_mulai_produksi or now()

        # ✅ Cek jika progress sudah selesai → otomatis update
        if produksi.progress >= produksi.jumlah:
            produksi.progress = produksi.jumlah  # pastikan pas
            produksi.waktu_mulai_produksi = produksi.waktu_mulai_produksi or now()

            if "proses" in nama_ruangan:
                messages.info(request, "Produksi sudah mencapai jumlah maksimal. Silakan pilih hasil akhir (Release / Reject).")
            elif "filling" in nama_ruangan or "penimbangan" in nama_ruangan:
                produksi.status = f"Selesai Diproses di {produksi.ruangan.nama}"
                produksi.waktu_selesai = now()

                # ⏺️ Tambahkan ke riwayat jika belum ada
                RiwayatProduksi.objects.get_or_create(
                    nomor_batch=produksi.nomor_batch,
                    nama_produk=produksi.nama,
                    jumlah=produksi.jumlah,
                    satuan=produksi.satuan,
                    ruangan=produksi.ruangan,
                    operator=produksi.operator,
                    waktu_mulai_produksi=produksi.waktu_mulai_produksi,
                    waktu_selesai=produksi.waktu_selesai,
                    hasil_akhir="Release"
                )
                messages.success(request, f"Produksi di {produksi.ruangan.nama} telah selesai.")
            else:
                messages.warning(request, "Nama ruangan tidak dikenali. Status tidak diperbarui otomatis.")

        produksi.save()
        messages.success(request, f"Batch {produksi.nomor_batch} berhasil diupdate.")
        return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))


@login_required
def operator_tentukan_hasil_akhir(request, produksi_id):
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if request.method == "POST":
        hasil = request.POST.get("hasil_akhir")
        if hasil in ["Release", "Reject"]:
            produksi.hasil_akhir = hasil
            produksi.status = f"Selesai Diproses di {produksi.ruangan.nama}"
            produksi.waktu_selesai = now()
            produksi.save()

            # ⬇️ Catat ke riwayat
            RiwayatProduksi.objects.get_or_create(
                nomor_batch=produksi.nomor_batch,
                nama_produk=produksi.nama,
                jumlah=produksi.jumlah,
                satuan=produksi.satuan,
                ruangan=produksi.ruangan,
                operator=produksi.operator,
                waktu_mulai_produksi=produksi.waktu_mulai_produksi,
                waktu_selesai=produksi.waktu_selesai,
                hasil_akhir=produksi.hasil_akhir,
            )

            # ➕ Jika Release dan ada tahap selanjutnya, buat batch baru otomatis
            if hasil == "Release" and produksi.ruangan.tahap_berikutnya:
                ProsesProduksi.objects.create(
                    nomor_batch=produksi.nomor_batch,
                    nama=produksi.nama,
                    jumlah=produksi.jumlah,
                    satuan=produksi.satuan,
                    ruangan=produksi.ruangan.tahap_berikutnya,
                    status="Menunggu",
                )

            messages.success(request, f"Hasil akhir batch {produksi.nomor_batch} ditandai sebagai '{hasil}'.")
        else:
            messages.error(request, "Pilihan hasil akhir tidak valid.")
        
        return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))


@login_required
def tandai_siap_dipindahkan(request, produksi_id):
    """Menandai batch sedang diproses menjadi siap dipindahkan (tidak digunakan jika pakai Release)."""
    produksi = get_object_or_404(ProsesProduksi, id=produksi_id)

    if produksi.status == "Sedang Diproses":
        produksi.status = "Siap Dipindahkan"
        produksi.waktu_selesai = now()
        produksi.save()
        print(f"DEBUG: {produksi.nomor_batch} sekarang 'Siap Dipindahkan'.")
    else:
        print(f"DEBUG: {produksi.nomor_batch} tidak bisa ditandai siap dipindahkan.")

    return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))


@login_required
def tandai_selesai_labelling(request, nomor_batch):
    """Operator ruang labelling menandai batch selesai produksi."""
    produksi = get_object_or_404(ProsesProduksi, nomor_batch=nomor_batch)

    if produksi.jumlah_kemasan is None or produksi.jumlah_kemasan <= 0:
        messages.error(request, "Silakan input jumlah kemasan sebelum menandai selesai!")
        return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

    produksi.status = "Selesai Produksi"
    produksi.waktu_selesai = now()
    produksi.save()

    # Tambah ke RiwayatProduksi jika belum ada
    RiwayatProduksi.objects.get_or_create(
        nomor_batch=produksi.nomor_batch,
        nama_produk=produksi.nama,
        jumlah=produksi.jumlah,
        satuan=produksi.satuan,
        ruangan=produksi.ruangan,
        operator=produksi.operator,
        waktu_mulai_produksi=produksi.waktu_mulai_produksi,
        waktu_selesai=produksi.waktu_selesai,
        hasil_akhir="Release"  # Default untuk labelling dianggap berhasil
    )

    messages.success(request, f"Batch {produksi.nomor_batch} telah ditandai selesai produksi.")
    return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

def monitoring_index(request):
    ruangan_penimbangan = Ruangan.objects.filter(nama__icontains='Penimbangan').first()
    ruang_proses = Ruangan.objects.filter(nama__icontains='Proses')
    ruang_filling = Ruangan.objects.filter(nama__icontains='Filling')
    ruang_labelling = Ruangan.objects.filter(nama__icontains='Labelling')

    context = {
        'ruangan_penimbangan': ruangan_penimbangan,
        'ruang_proses': ruang_proses,
        'ruang_filling': ruang_filling,
        'ruang_labelling': ruang_labelling,
    }
    return render(request, 'monitoring/index.html', context)
