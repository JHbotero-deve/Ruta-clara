from src.routes import parse_delivery_label_endpoint


def test_parse_address_with_municipality_on_same_line():
    parsed = parse_delivery_label_endpoint(
        {"text": "Direccion: Carrera 32b 10-110. Medellín\nReferencia: Vizcaya real 2.419\nDestinatario: Lucrecia Inés Vasquez"},
        current_user=None,
    )
    assert parsed["direccion"] == "Carrera 32B #10-110"
    assert parsed["municipio"] == "Medellín"
    assert parsed["referencia"] == "Vizcaya real 2.419"


def test_parse_short_colombian_street_prefix_with_city_suffix():
    parsed = parse_delivery_label_endpoint(
        {"text": "Dirección: Cra 45 #12-30, Medellín\nBarrio: Laureles"},
        current_user=None,
    )
    assert parsed["direccion"] == "Carrera 45 #12-30"
    assert parsed["municipio"] == "Medellín"
