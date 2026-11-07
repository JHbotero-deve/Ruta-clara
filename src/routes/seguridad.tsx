import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/AppShell";
import { pageHead } from "@/lib/seo";

export const Route = createFileRoute("/seguridad")({
  head: pageHead("Seguridad", "Cómo Ruta Clara procesará las etiquetas: lectura local, sin códigos y con permisos mínimos."),
  component: SecurityPage,
});

const ITEMS = [
  ["Procesamiento local previsto", "El OCR se ejecutará en el dispositivo, solo sobre el recorte de la zona inferior de texto. Las imágenes no se envían a servicios externos."],
  ["Códigos excluidos por diseño", "La app no lee, decodifica, almacena ni transmite QR, códigos de barras ni identificadores codificados. No incluye librerías para hacerlo."],
  ["Solo tres campos", "Dirección, cliente/destinatario y nombre de la unidad. Cualquier otro campo se rechaza y no se infieren identificadores."],
  ["Permisos mínimos", "La cámara solo se solicitará al pulsar “Iniciar escaneo”. Esta versión demo no pide ningún permiso."],
  ["Sin imágenes originales", "La imagen completa no se guarda. El recorte temporal se elimina después de extraer el texto."],
  ["Claves solo en servidor", "Las claves de validación de direcciones y rutas vivirán en el servidor, nunca en la app."],
  ["Registro sin datos sensibles", "Los eventos registrarán acciones y estados, nunca nombres, direcciones ni imágenes."],
];

function SecurityPage() {
  return (
    <AppShell title="Seguridad y privacidad" subtitle="Controles previstos · pendientes de pruebas de seguridad">
      <div className="space-y-2">
        {ITEMS.map(([t, d]) => (
          <div key={t} className="rounded-lg border bg-card p-4">
            <p className="text-sm font-semibold">{t}</p>
            <p className="mt-1 text-sm text-muted-foreground">{d}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">Ningún sistema es infalible. Estos controles reducen riesgos; no garantizan seguridad absoluta.</p>
    </AppShell>
  );
}