export const pageHead = (title: string, description: string) => () => ({
  meta: [
    { title: `${title} · Ruta Clara` },
    { name: "description", content: description },
    { property: "og:title", content: `${title} · Ruta Clara` },
    { property: "og:description", content: description },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ],
});