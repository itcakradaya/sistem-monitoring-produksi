from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now
from django.urls import reverse
from django.utils.text import slugify
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import F, Q
from .models import Ruangan, ProsesProduksi, Operator, RiwayatProduksi, IdempotencyKey, Operator
import uuid
from .helpers import ensure_labelling_shadow_from

def get_produksi_data(request):
    qs = (
        ProsesProduksi.objects
        .filter(ruangan__nama__iexact="Penimbangan")
        .select_related("nama", "operator")  # FK prefetch ke 1 query
        .only(
            "nomor_batch", "jumlah", "waktu_selesai", "hasil_akhir",
            "nama__description", "operator__nama"
        )
    )

    data = []
    for p in qs:
        data.append({
            "nomor_batch": p.nomor_batch,
            "nama_produk": p.nama.description if p.nama_id else None,
            "jumlah": p.jumlah,
            "waktu_selesai": p.waktu_selesai,          # JsonResponse pakai DjangoJSONEncoder → OK
            "operator": p.operator.nama if p.operator_id else None,
            "hasil_akhir": p.hasil_akhir,
        })

    return JsonResponse(data, safe=False)



def dashboard(request):
    """Menampilkan daftar ruangan produksi yang tersedia."""
    ruangan_list = Ruangan.objects.all()
    return render(request, 'produksi_monitoring/dashboard.html', {"ruangan_list": ruangan_list})

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import now
from datetime import timedelta

@login_required
def monitoring_produksi_per_ruangan(request, ruangan_slug):
    ruangan = get_object_or_404(Ruangan, slug=ruangan_slug)
    is_operator = request.user.groups.filter(name__iexact='operator').exists()

    auto_qs = (
        ProsesProduksi.objects
        .filter(status="Menunggu", waktu_mulai_produksi__lte=now())
        .exclude(ruangan__nama__icontains="labell")
        .select_related("ruangan")
    )

    for p in auto_qs:
        p.status = "Sedang Diproses"
        if not p.waktu_mulai_produksi:
            p.waktu_mulai_produksi = now()
        p.save(update_fields=["status", "waktu_mulai_produksi"])

        # jika sumbernya Filling → buat shadow di Labelling
        if "fill" in (p.ruangan.nama or "").lower():
            try:
                ensure_labelling_shadow_from(p)
            except Exception:
                pass

    # Dataset utama per ruangan
    proses_produksi = ProsesProduksi.objects.filter(ruangan=ruangan)
    menunggu    = proses_produksi.filter(status="Menunggu").order_by('waktu_mulai_produksi')
    diproses    = proses_produksi.filter(status="Sedang Diproses").order_by('waktu_mulai_produksi')
    siap_pindah = proses_produksi.filter(status="Siap Dipindahkan").order_by('-waktu_selesai')

    # Masih disiapkan seperti kode kamu (walau belum dipakai di template)
    tujuh_hari_lalu = now() - timedelta(days=7)
    batch_pernah_di_ruangan = ProsesProduksi.objects.filter(
        nomor_batch__in=proses_produksi.values_list('nomor_batch', flat=True),
        waktu_selesai__gte=tujuh_hari_lalu
    ).values_list('nomor_batch', flat=True).distinct()

    # Ambil & terapkan limit
    limit = request.GET.get('limit', '10')
    def apply_limit(qs):
        if limit == 'semua':
            return qs
        try:
            return qs[:int(limit)]
        except (TypeError, ValueError):
            return qs[:10]

    # Context dasar
    context = {
        "ruangan": ruangan,
        "proses_menunggu": menunggu,
        "proses_diproses": diproses,
        "proses_siap_pindah": siap_pindah,
        "limit": limit,
        "is_operator": is_operator,
    }

    # Cabang khusus Labelling
    if "labelling" in (ruangan.nama or "").lower():
        riwayat_labelling = apply_limit(
            ProsesProduksi.objects.filter(
                ruangan=ruangan, status="Selesai Produksi"
            ).order_by('-waktu_selesai')
        )

        # hitung akurasi tampilan
        for item in riwayat_labelling:
            if item.estimasi_jumlah_kemasan:
                try:
                    item.akurasi_persen = round(
                        (item.jumlah_kemasan or 0) * 100 / item.estimasi_jumlah_kemasan, 2
                    )
                except ZeroDivisionError:
                    item.akurasi_persen = None
            else:
                item.akurasi_persen = None

        # Operator khusus kategori Labelling saja
        operator_list = Operator.objects.filter(
            Q(kategori__iexact='Labelling') | Q(kategori__icontains='label')
        ).order_by('nama')

        context.update({
            "proses_selesai": None,               # nonaktifkan riwayat umum
            "riwayat_produksi": riwayat_labelling,
            "operator_list": operator_list,
        })
    else:
        # Ruangan lain → pakai RiwayatProduksi
        riwayat_queryset = apply_limit(
            RiwayatProduksi.objects.filter(ruangan=ruangan)
                                   .select_related('ruangan')
                                   .order_by('-waktu_selesai')
        )

        context.update({
            "proses_selesai": riwayat_queryset,
            "riwayat_produksi": None,
            "operator_list": Operator.objects.none(),  # tidak dipakai di non-labelling
        })

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
@require_POST
def tandai_sedang_diproses(request, produksi_id):
    """
    Menandai proses jadi 'Sedang Diproses'.
    Jika sumbernya Filling, pastikan nomor batch muncul juga di Ruang Labelling (status 'Menunggu').
    """
    with transaction.atomic():
        # Lock row untuk hindari double-click / race
        produksi = get_object_or_404(
            ProsesProduksi.objects.select_for_update(),
            id=produksi_id
        )

        if produksi.status != "Menunggu":
            messages.error(request, "Batch ini tidak bisa ditandai sedang diproses.")
            return redirect(reverse("monitoring_per_ruangan", args=[slugify(produksi.ruangan.nama)]))

        # Update status & waktu mulai (jaga kalau sudah ada nilainya)
        produksi.status = "Sedang Diproses"
        if not produksi.waktu_mulai_produksi:
            produksi.waktu_mulai_produksi = now()

        # Amanin jika model punya field progress
        if hasattr(produksi, "progress") and (produksi.progress is None or produksi.progress < 0):
            produksi.progress = 0

        produksi.save()

        # Jika dari Filling → buat/mastikan “shadow” di Labelling (status Menunggu)
        try:
            ensure_labelling_shadow_from(produksi)
        except Exception:
            # jangan ganggu alur utama kalau gagal bikin shadow
            pass

    messages.success(request, f"Batch {produksi.nomor_batch} sekarang sedang diproses.")
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
        "operator_list": Operator.objects.filter(
            Q(kategori__iexact='Labelling') | Q(kategori__icontains='label')
        ).order_by("nama"),
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
        "operator_list": Operator.objects.filter(
            Q(kategori__iexact='Labelling') | Q(kategori__icontains='label')
        ).order_by("nama"),
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
            try:
                if "filling" in nama_ruangan:
                    ensure_labelling_shadow_from(produksi)
            except Exception:
                pass
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
    produksi = get_object_or_404(ProsesProduksi, nomor_batch=nomor_batch, ruangan__nama__icontains='labell',)

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

@login_required
@require_POST
def update_progress_labelling(request, pk):
    """
    Tambah jumlah_kemasan untuk batch di Ruang Labelling.

    - Idempotensi: tolak duplikasi berdasarkan request id (rid)
    - SOFT guard : jika > estimasi -> tetap diterima, ditandai overrun=True
    - HARD cap   : jika > 150% dari estimasi -> ditolak (jika estimasi ada)
    """
    rid = (
        request.POST.get("rid")
        or request.headers.get("X-Request-ID")
        or uuid.uuid4().hex
    )

    # default supaya aman jika return lebih awal
    sisa_sebelum = None
    sisa_setelah = None
    overrun = False
    estimasi = 0
    tambah = 0

    with transaction.atomic():
        # --- Idempotensi ---
        _, created = IdempotencyKey.objects.get_or_create(
            key=rid, defaults={"action": "labelling_update"}
        )
        if not created:
            return JsonResponse({"ok": True, "duplicate": True, "rid": rid})

        # --- Lock row & validasi ruangan ---
        proses = get_object_or_404(
            ProsesProduksi.objects.select_for_update(), pk=pk
        )
        nama_ruang = (proses.ruangan.nama or "").lower()
        if "labell" not in nama_ruang:
            return JsonResponse(
                {"ok": False, "message": "Hanya untuk Ruang Labelling", "rid": rid},
                status=400,
            )

        # --- Ambil & validasi input jumlah ---
        raw = request.POST.get("jumlah", request.POST.get("jumlah_kemasan", "0"))
        try:
            tambah = int(raw)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "message": "Jumlah tidak valid", "rid": rid}, status=400)
        if tambah <= 0:
            return JsonResponse({"ok": False, "message": "Jumlah harus > 0", "rid": rid}, status=400)

        # --- Ambil angka dasar ---
        estimasi = int(proses.estimasi_jumlah_kemasan or 0)
        current  = int(proses.jumlah_kemasan or 0)

        # --- HARD cap 150% bila ada estimasi ---
        allowed_tambahan = None
        max_total150 = None
        if estimasi:
            max_total150 = int(estimasi * 1.5)
            allowed_tambahan = max(0, max_total150 - current)
            if tambah > allowed_tambahan:
                return JsonResponse(
                    {
                        "ok": False,
                        "message": f"Melebihi batas akurasi 150%. Maks tambahan saat ini: {allowed_tambahan}.",
                        "allowed_tambahan": allowed_tambahan,
                        "rid": rid,
                    },
                    status=400,
                )

        # --- SOFT guard: tandai overrun bila > sisa (kalau estimasi ada) ---
        # gunakan property sisa_kemasan jika tersedia
        sisa_prop = getattr(proses, "sisa_kemasan", None)
        try:
            sisa_sebelum = int(sisa_prop) if sisa_prop is not None else None
        except (TypeError, ValueError):
            sisa_sebelum = None
        overrun = bool(sisa_sebelum is not None and tambah > sisa_sebelum)

        # --- Update nilai ---
        new_total = current + tambah
        proses.jumlah_kemasan = new_total

        # auto set mulai produksi jika masih menunggu
        if proses.status == "Menunggu":
            proses.status = "Sedang Diproses"  # konsisten dengan template/logic lain
            if not proses.waktu_mulai_produksi:
                proses.waktu_mulai_produksi = now()

        proses.save(update_fields=["jumlah_kemasan", "status", "waktu_mulai_produksi"])

        # hitung sisa_setelah & allowed_tambahan baru untuk UI
        if estimasi:
            sisa_setelah = max(estimasi - new_total, 0)
            allowed_tambahan = max(0, int(estimasi * 1.5) - new_total)

    return JsonResponse(
        {
            "ok": True,
            "rid": rid,
            "ditambahkan": tambah,
            "total_baru": int(proses.jumlah_kemasan or 0),
            "sisa_sebelum": sisa_sebelum,
            "sisa_setelah": sisa_setelah,
            "overrun": overrun,
            "max_total150": max_total150,           # total maksimum (bukan sisa)
            "allowed_tambahan": allowed_tambahan,   # sisa ruang sampai 150% SESUDAH update
        }
    )
