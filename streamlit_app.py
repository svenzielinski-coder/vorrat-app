import streamlit as st
from PIL import Image
import requests
from pyzxing import read_barcode
import json
import uuid
from pathlib import Path

DATA_FILE = Path("vorrat.json")

st.set_page_config(page_title="Vorrat", layout="centered")
st.title("🥫 Vorrats- & Bestandsverwaltung")

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

items = load_items()

critical = [i for i in items if i["quantity"] <= i["min_level"]]
if critical:
    st.error(f"⚠️ {len(critical)} Artikel sind unter/auf Minimum!")
else:
    st.success("✅ Alles im grünen Bereich")

location_filter = st.segmented_control(
    "Standort",
    options=["Alle", "Abstellkammer", "Vorratsraum"],
    default="Alle"
)

query = st.text_input("Suche", placeholder="z.B. Reis, Milch, Nudeln …").strip().lower()

def matches_filters(item):
    if location_filter != "Alle" and item["location"] != location_filter:
        return False
    if query and query not in item["name"].lower():
        return False
    return True

st.subheader("➕ Artikel hinzufügen")
with st.form("add_item", clear_on_submit=True):
    name = st.text_input("Artikelname", placeholder="z.B. Nudeln")
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

    if st.form_submit_button("Speichern"):
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
            st.rerun()

st.subheader("🔴 Kritisch")
crit_filtered = [i for i in items if i["quantity"] <= i["min_level"] and matches_filters(i)]
if not crit_filtered:
    st.caption("Keine kritischen Artikel (mit aktuellem Filter).")
else:
    for item in crit_filtered:
        st.markdown(
            f"**{item['name']}** — {item['quantity']} {item['unit']} "
            f"(Min {item['min_level']} {item['unit']}) · {item['location']}"
        )

st.subheader("📦 Alle Artikel")
shown = [i for i in items if matches_filters(i)]
if not shown:
    st.caption("Noch keine Artikel vorhanden (oder Filter zu streng).")
else:
    for item in shown:
        is_critical = item["quantity"] <= item["min_level"]
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
                item["quantity"] = max(0.0, item["quantity"] - 1.0)
                save_items(items)
                st.rerun()
            if b2.button("➕", key=f"inc_{item['id']}"):
                item["quantity"] += 1.0
                save_items(items)
                st.rerun()
            if b3.button("🗑️", key=f"del_{item['id']}"):
                items = [x for x in items if x["id"] != item["id"]]
                save_items(items)
                st.rerun()
