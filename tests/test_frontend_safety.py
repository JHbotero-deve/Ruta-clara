from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_safety_layer_does_not_override_the_primary_ocr_flow():
    safety = (ROOT / "static" / "safety.js").read_text(encoding="utf-8")
    assert "window.processParsedGuide=" not in safety
    assert "window.handleGuideFormSubmit=" not in safety
    assert "const originalSaveLocation" not in safety


def test_offline_delivery_sync_uses_the_persistent_session_token():
    safety = (ROOT / "static" / "safety.js").read_text(encoding="utf-8")
    assert "localStorage.getItem('ruta_clara_token')" in safety
    assert "sessionStorage.getItem('ruta_clara_token')" not in safety


def test_service_worker_invalidates_the_old_safety_script_cache():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    worker = (ROOT / "static" / "sw.js").read_text(encoding="utf-8")
    assert "/static/safety.js?v=2" in index
    assert "ruta-clara-v7" in worker
    assert "'/static/safety.js?v=2'" in worker


def test_private_qr_and_barcode_detection_remains_disabled():
    safety = (ROOT / "static" / "safety.js").read_text(encoding="utf-8")
    assert "window.barcodeDetector=null" in safety
    assert "window.startBarcodeDetectionLoop=function(){}" in safety


def test_live_gps_errors_are_visible_to_the_driver():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "Error actualizando GPS:" in index
    assert "Permite la ubicación del celular" in index
