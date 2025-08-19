# produksi_monitoring/helpers.py
from django.db import transaction
from django.db.models import Q
from .models import ProsesProduksi, Ruangan, Operator


def ensure_labelling_shadow_from(proses_filling: ProsesProduksi) -> bool:
    """
    Pastikan nomor_batch dari RUANG FILLING juga muncul di RUANG LABELLING (status 'Menunggu').
    Idempotent: kalau sudah ada, tidak membuat duplikat.
    Return:
      True  -> baru dibuat
      False -> tidak dibuat (sudah ada / bukan dari Filling / tak ada ruangan Labelling)
    """
    # Validasi dasar
    if not proses_filling or not getattr(proses_filling, "ruangan", None):
        return False

    # Hanya jalankan untuk sumber dari Filling (sesuaikan keyword jika nama ruang berbeda)
    nama_asal = (proses_filling.ruangan.nama or "").lower()
    if "fill" not in nama_asal:  # contoh: "Filling", "Pengisian (Filling)", dst.
        return False

    # Cari ruangan Labelling (pakai 'labell' agar match "labelling"/"labeling")
    ruangan_lab = Ruangan.objects.filter(nama__icontains="labell").first()
    if not ruangan_lab:
        return False

    # Jangan buat shadow kalau ternyata kita sudah berada di ruangan Labelling
    if ruangan_lab.id == proses_filling.ruangan_id:
        return False

    # Cegah duplikasi (nomor_batch yang sama di ruangan Labelling)
    exists = ProsesProduksi.objects.filter(
        nomor_batch=proses_filling.nomor_batch,
        ruangan=ruangan_lab,
    ).exists()
    if exists:
        return False

    # (Opsional) pilih operator default kategori Labelling
    default_op = Operator.objects.filter(
        Q(kategori__iexact="Labelling") | Q(kategori__icontains="label")
    ).order_by("nama").first()

    # Buat shadow dalam transaksi supaya aman terhadap race condition
    with transaction.atomic():
        # double-check di dalam transaksi
        if ProsesProduksi.objects.select_for_update().filter(
            nomor_batch=proses_filling.nomor_batch,
            ruangan=ruangan_lab,
        ).exists():
            return False

        obj = ProsesProduksi(
            nomor_batch=proses_filling.nomor_batch,
            nama=getattr(proses_filling, "nama", None),
            jumlah=getattr(proses_filling, "jumlah", None),
            satuan=getattr(proses_filling, "satuan", None),
            ruangan=ruangan_lab,
            status="Menunggu",
        )

        # Copy field terkait kemasan bila model memiliki field-nya
        if hasattr(proses_filling, "estimasi_jumlah_kemasan"):
            obj.estimasi_jumlah_kemasan = proses_filling.estimasi_jumlah_kemasan
        if hasattr(proses_filling, "satuan_kemasan"):
            obj.satuan_kemasan = proses_filling.satuan_kemasan

        if default_op:
            obj.operator = default_op

        obj.save()

    return True
