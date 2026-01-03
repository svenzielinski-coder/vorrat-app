import json
import uuid
from pathlib import Path

import streamlit as st
from PIL import Image
import requests
from pyrxing import read_barcode

DATA_FILE = Path("vorrat.json")

st.set_page_config(page_title="Vorrat", layout="centered")
st.title("🥫 Vorrats- & Bestandsverwaltung")

# -----------------------------
# Daten speichern / laden
# -----------------------------
def load_items():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_items(items):
    DATA_FILE.write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

# -----------------------------
# Open Food Facts Lookup
# -----------------------------
@st.cache_data(ttl=60 * 60 * 24)  # 24h Cache
def off_lookup(barcode: str):
    # OFF API v2 Produkt-Endpunkt
    url = f"https://world.openfoodfacts.net/api/v2/product/{barcode}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()

    # status=1 => gefunden
    if data.get("status") != 1:
        return None

    product = data.get("product", {}) or {}
    name = (
        product.get("product_name_de")
        or product.get("product_name")
        or product.get("generic_name_de")
        or product.get("generic_name")
    )
    brand = product.get("brands")

    display = name.strip() if isinstance(name, str) and name.strip() else None
    if display and brand:
        display = f"{display} ({brand})"
    return display

# -----------------------------
# Items laden
# -----------------------------
items = load_items()

# -----------------------------
# Status / Warnung
# -----------------------------
critical_all = [i for i in items if float(i.get("quantity", 0)) <= float(i.get("min_level", 0))]
if critical_all:
    st.error(f"⚠️ {len(critical_all)} Artikel sind unter/auf Minimum!")
else:
    st.success("✅ Alles im grünen Bereich")

# -----------------------------
# Filter
# -----------------------------
st.write("")
location_filter = st.segmented_control(
    "Standort",
    options=["Alle", "Abstellkammer", "Vorratsraum"],
    default="Alle"
)

query = st.text_input("Suche", placeholder="z.B. Reis, Milch, Nudeln …").strip().lower()

def matches_filters(item):
    if location_filter != "Alle" and item.get("location") != location_filter:
        return False
    if query and query not in str(item.get("name", "")).lower():
        return False
    return True

# -----------------------------
# SCAN: Kamera -> Barcode -> Produktname
# -----------------------------
st.subheader("📷 Scannen (Barcode)")

img_file = st.camera_input("Barcode fotografieren")

if img_file is not None:
    img = Image.open(img_file)

    try:
        res = read_barcode(img)  # kann PIL.Image lesen
    except Exception as e:
        st.error(f"Scan-Fehler: {e}")
        res = None

    if not res:
        st.warning("❌ Kein Barcode erkannt. Tipp: näher ran, ruhig halten, gutes Licht, Barcode gerade ins Bild.")
    else:
        # pyrxing gibt ein Objekt zurück, das i.d.R. .text hat
        barcode = getattr(res, "text", None) or getattr(res, "data", None) or str(res)
        barcode = str(barcode).strip()
        st.success(f"✅ Barcode erkannt: {barcode}")

        # Produktnamen holen
        product_name = None
        try:
            product_name = off_lookup(barcode)
        except Exception:
            product_name = None

        if product_name:
            st.info(f"Gefunden: **{product_name}**")
            st.session_state["prefill_name"] = product_name
        else:
            st.info("Kein Treffer bei Open Food Facts – du kannst den Namen manuell eingeben.")
            st.session_state["prefill_name"] = f"Barcode {barcode}"

# -----------------------------
# Artikel hinzufügen
# -----------------------------
st.subheader("➕ Artikel hinzufügen")

with st.form("add_item", clear_on_submit=True):
    prefill = st.session_state.get("prefill_name", "")
    name = st.text_input("Artikelname", value=prefill, placeholder="z.B. Nudeln")

    c1, c2 = st.columns(2)
    with c1:
        location = st.selectbox("Standort", ["Abstellkammer", "Vorratsraum"])
    with c2:
        unit = st.selectbox("Einheit", ["Stk", "Pack", "g", "ml"])

    c3, c4 = st.columns(2)
    with c3:
        quantity = st.number_input("Aktueller Bestand", min_value=0.0, step=1.0)
    with c4:
        min_level = st.number_input("Minimum", min_value=0.0, step=1.0)

    category = st.text_input("Kategorie (optional)", placeholder="z.B. Pasta, Konserve …")

    submitted = st.form_submit_button("Speichern")

    if submitted:
        if not name.strip():
            st.warning("Bitte einen Artikelnamen eingeben.")
        else:
            items.insert(0, {
                "id": str(uuid.uuid4()),
                "name": name.strip(),
                "location": location,
                "unit": unit,
                "quantity": float(quantity),
                "min_level": float(min_level),
                "category": category.strip() or None
            })
            save_items(items)
            st.session_state["prefill_name"] = ""  # Prefill leeren
            st.rerun()

# -----------------------------
# Kritisch-Liste
# -----------------------------
st.subheader("🔴 Kritisch")

crit_filtered = [
    i for i in items
    if float(i.get("quantity", 0)) <= float(i.get("min_level", 0)) and matches_filters(i)
]

if not crit_filtered:
    st.caption("Keine kritischen Artikel (mit aktuellem Filter).")
else:
    for item in crit_filtered:
        st.markdown(
            f"**{item['name']}** — {item['quantity']} {item['unit']} "
            f"(Min {item['min_level']} {item['unit']}) · {item['location']}"
        )

# -----------------------------
# Alle Artikel
# -----------------------------
st.subheader("📦 Alle Artikel")

shown = [i for i in items if matches_filters(i)]
if not shown:
    st.caption("Noch keine Artikel vorhanden (oder Filter zu streng).")
else:
    for item in shown:
        is_critical = float(item.get("quantity", 0)) <= float(item.get("min_level", 0))

        with st.container(border=True):
            top = st.columns([3, 2])
            with top[0]:
                st.markdown(f"### {item['name']} {'🔴' if is_critical else '🟢'}")
                meta = []
                if item.get("category"):
                    meta.append(item["category"])
                meta.append(item["location"])
                st.caption(" · ".join(meta))

            with top[1]:
                st.write(f"**Bestand:** {item['quantity']} {item['unit']}")
                st.write(f"**Minimum:** {item['min_level']} {item['unit']}")

            b1, b2, b3 = st.columns([1, 1, 1])

            if b1.button("➖", key=f"dec_{item['id']}"):
                item["quantity"] = max(0.0, float(item["quantity"]) - 1.0)
                save_items(items)
                st.rerun()

            if b2.button("➕", key=f"inc_{item['id']}"):
                item["quantity"] = float(item["quantity"]) + 1.0
                save_items(items)
                st.rerun()

            if b3.button("🗑️", key=f"del_{item['id']}"):
                items = [x for x in items if x["id"] != item["id"]]
                save_items(items)
                st.rerun()
