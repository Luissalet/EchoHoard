export const KIND_LABEL = {
  text: "Texto", url: "URL", email: "Correo", path: "Ruta", code: "Código", number: "Número", image: "Imagen",
};

export const KIND_CHIP = {
  text: "", url: "chip-accent", email: "chip-accent", path: "chip-warn", code: "chip-ok", number: "chip-ok", image: "chip-warn",
};

export function when(epoch) {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toLocaleString("es-ES", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function dayKey(epoch) {
  const date = new Date(epoch * 1000);
  const label = date.toLocaleDateString("es-ES", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function bytes(n) {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = n;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(i ? 1 : 0)} ${units[i]}`;
}
