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

def test_scanner_retries_geocoding_and_requires_valid_location_before_saving():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    start = index.index("async function processParsedGuide(parsed)")
    end = index.index("async function handleGuideFormSubmit", start)
    flow = index[start:end]
    queries = flow.index("const queries = [")
    retries = flow.index("for (const query of queries)")
    coordinates = flow.index("Number.isFinite(lat)")
    municipality = flow.index("const municipality = parsed.municipio || match.municipality ||")
    save = flow.index("saveLocationAutomatically")
    assert queries < retries < coordinates < municipality < save
    assert "if (!municipality) throw new Error" in flow
def test_scanner_requires_complete_colombian_street_number_before_geocoding():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    start = index.index("async function processParsedGuide(parsed)")
    end = index.index("async function handleGuideFormSubmit", start)
    flow = index[start:end]
    completeness = flow.index("const hasCompleteStreetNumber")
    geocode = flow.index("fetch(`/geocode?query=")
    save = flow.index("saveLocationAutomatically")
    assert completeness < geocode < save
    assert "No se guardó ninguna parada" in flow

def test_continuous_scanner_keeps_camera_open_between_guides():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    capture_start = index.index("async function captureAndReadGuide()")
    capture_end = index.index("async function processUploadedGuide(file)", capture_start)
    capture = index[capture_start:capture_end]
    assert "scannerCaptureBusy" in capture
    assert "processParsedGuide(data)" in capture
    assert "No se guardó" in capture
    assert "stopProScanner()" not in capture
    assert "CAPTURAR SIGUIENTE GUÍA" in capture


def test_continuous_scanner_requests_continuous_focus_and_camera_recovery():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "focusMode: 'continuous'" in index
    assert "async function refocusScannerCamera()" in index
    assert "async function recoverScannerCamera()" in index
    assert "video.addEventListener('click', refocusScannerCamera)" in index
    assert "visibilitychange" in index
