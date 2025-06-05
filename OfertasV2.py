import os
import json
import re
import time
import requests
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from autopush import auto_push


# -------------------- CONFIGURACIÓN TELEGRAM --------------------
BOT_TOKEN = "7970307417:AAGwBiI8DlZMuxsGJzeOSaUaxtJ8qE2UAdw"   # <-- tu token de BotFather
CHAT_ID   = "7623988965"                                     # <-- ID del chat o canal

def enviar_telegram(texto):
    """
    Envía un solo mensaje a Telegram usando parse_mode=HTML.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        if not resp.ok:
            print(f"❌ Error al enviar Telegram: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Excepción al enviar Telegram: {e}")

# -------------------- RUTAS Y ARCHIVO DE ESTADO --------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_FEED             = os.path.join(BASE_DIR, "ultimas_ofertas.json")
ARCHIVO_FEED_AGRUPADO    = os.path.join(BASE_DIR, "ultimas_ofertas_agrupado.json")

def cargar_feed_previo():
    """
    Carga el feed previo desde ARCHIVO_FEED (lista de objetos individuales).
    Si no existe o hay error, retorna lista vacía.
    """
    if os.path.exists(ARCHIVO_FEED):
        try:
            with open(ARCHIVO_FEED, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ No se pudo leer '{ARCHIVO_FEED}': {e}")
            return []
    return []

def cargar_feed_agrupado_previo():
    """
    Carga el feed agrupado previo desde ARCHIVO_FEED_AGRUPADO (lista con único objeto).
    Si no existe o hay error, retorna lista vacía.
    """
    if os.path.exists(ARCHIVO_FEED_AGRUPADO):
        try:
            with open(ARCHIVO_FEED_AGRUPADO, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ No se pudo leer '{ARCHIVO_FEED_AGRUPADO}': {e}")
            return []
    return []

def guardar_feed_individual(ofertas_feed):
    """
    Guarda la lista de objetos individuales en ARCHIVO_FEED.
    """
    try:
        with open(ARCHIVO_FEED, "w", encoding="utf-8") as f:
            json.dump(ofertas_feed, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Error al escribir '{ARCHIVO_FEED}': {e}")

def guardar_feed_agrupado(ofertas_feed):
    """
    Toma la lista de objetos individuales y genera un único objeto con
    'mainText' conteniendo todos los nombres separados por comas. Usa la fecha
    y campos del último objeto. Guarda en ARCHIVO_FEED_AGRUPADO como lista de un objeto.
    """
    if not ofertas_feed:
        return

    # Extraer todos los nombres (campo mainText) en orden
    nombres = [item["mainText"] for item in ofertas_feed]
    main_text_agregado = ", ".join(nombres)

    # Tomar última actualización y campos del último objeto
    ultimo = ofertas_feed[-1]
    uid          = ultimo["uid"]
    update_date  = ultimo["updateDate"]
    title_text   = ultimo["titleText"]
    redir_url    = ultimo["redirectionUrl"]

    objeto_unico = {
        "uid": uid,
        "updateDate": update_date,
        "titleText": title_text,
        "mainText": main_text_agregado,
        "redirectionUrl": redir_url
    }

    contenido = [objeto_unico]
    try:
        with open(ARCHIVO_FEED_AGRUPADO, "w", encoding="utf-8") as f:
            json.dump(contenido, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Error al escribir '{ARCHIVO_FEED_AGRUPADO}': {e}")

# -------------------- CONFIGURACIÓN SELENIUM --------------------
def safe_find(parent, by, selector):
    """
    Busca un elemento dentro de 'parent' y devuelve None si no existe.
    """
    try:
        return parent.find_element(by, selector)
    except NoSuchElementException:
        return None

# Configurar ChromeDriver para silenciar logs
servicio = Service(log_path="nul")  # en Windows; en Linux/Mac usar "/dev/null"
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--lang=es")
options.add_argument("--user-agent=Mozilla/5.0")
options.add_argument("--headless")      # Ejecutar en segundo plano
options.add_argument("--disable-gpu")   # Recomendado en headless
options.add_argument("--no-sandbox")    # Para evitar errores en algunos entornos

driver = webdriver.Chrome(service=servicio, options=options)

# -------------------- SCRAPER DE OFERTAS --------------------
vistos = set()            # Para evitar duplicados en esta ejecución
todas_ofertas_texto = []  # Lista de strings "🥩 <b>nombre limpio</b> — precio"
ofertas_feed = []         # Lista de dicts con campos uid, updateDate, titleText, mainText, redirectionUrl

# Regex para quitar variaciones de "x kg" o "XKG" (cualquier caso)
regex_xkg = re.compile(r"\s*[xX]\s*[kK][gG]")

try:
    # 1) Abrir home de Cotodigital
    driver.get("https://www.cotodigital.com.ar")

    # 2) Esperar que cargue al menos un <a>
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "a"))
    )

    # 3) Localizar y hacer hover sobre “Frescos”
    frescos_xpath = "//a[contains(@class,'dropdown-item categorias-generales') and normalize-space(text())='Frescos']"
    enlace_frescos = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, frescos_xpath))
    )
    ActionChains(driver).move_to_element(enlace_frescos).perform()

    # 4) Esperar a que aparezca y clic en “Carnicería”
    carniceria_xpath = "//a[contains(@href,'catalogo-frescos-carniceria') and .//b[contains(text(),'Carniceria')]]"
    enlace_carniceria = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.XPATH, carniceria_xpath))
    )
    enlace_carniceria.click()

    # 5) Esperar a que cargue Carnicería (primer <h3 class="nombre-producto">)
    WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "h3.nombre-producto"))
    )

    # 6) Bucle principal: scroll / extracción de ofertas / paginación
    pagina = 1
    while True:
        print(f"\n===== Página {pagina} =====")

        # 6.1) Esperar al menos un título de producto
        try:
            WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "h3.nombre-producto"))
            )
        except TimeoutException:
            print("⚠️ Timeout: no aparecieron los títulos en esta página.")
            break

        # 6.2) Scroll progresivo para lazy-loading
        altura = 0
        conteo_prev = 0
        while True:
            driver.execute_script(f"window.scrollTo(0, {altura});")
            altura += 500
            time.sleep(1)
            titulos_actuales = driver.find_elements(By.CSS_SELECTOR, "h3.nombre-producto")
            if len(titulos_actuales) > conteo_prev:
                conteo_prev = len(titulos_actuales)
                continue
            else:
                break

        # 6.3) Capturar todos los títulos <h3 class="nombre-producto">
        titulos = driver.find_elements(By.CSS_SELECTOR, "h3.nombre-producto")
        print(f"🛒 Se encontraron {len(titulos)} títulos en esta página.")

        ofertas_en_pagina = 0

        for titulo_elem in titulos:
            nombre_original = titulo_elem.text.strip()
            # Eliminar cualquier variación de "x kg" (case-insensitive)
            nombre = regex_xkg.sub("", nombre_original).strip()

            if nombre in vistos:
                continue

            # 6.4) Subir al contenedor padre del producto
            bloque = safe_find(titulo_elem, By.XPATH, "./ancestor::div[2]")
            if not bloque:
                vistos.add(nombre)
                continue

            # 6.5) Intentar obtener un ID único (data-product-id si existe, sino usar nombre limpio)
            prod_id = bloque.get_attribute("data-product-id") or nombre
            if prod_id in vistos:
                continue

            # 6.6) Verificar etiqueta “Oferta”
            es_oferta = False
            oferta_elem = safe_find(bloque, By.CSS_SELECTOR, "small.offer-crum")
            if oferta_elem and "oferta" in oferta_elem.text.strip().lower():
                es_oferta = True

            if not es_oferta:
                vistos.add(prod_id)
                continue

            # 6.7) Extraer precio (primer "$" en <h4 class="card-title">)
            precio = "Precio no disponible"
            precios_h4 = bloque.find_elements(By.CSS_SELECTOR, "h4.card-title")
            for ph in precios_h4:
                texto_precio = ph.text.strip()
                if "$" in texto_precio:
                    precio = texto_precio
                    break

            # 6.8) Añadir cadena para Telegram
            todas_ofertas_texto.append(f"🥩 <b>{nombre}</b> — {precio}")

            # 6.9) Obtener URL de redirección (link al producto)
            redir_url = None
            try:
                enlace_prod = bloque.find_element(By.CSS_SELECTOR, "a[href*='/sitios/cdigi/producto/']")
                href = enlace_prod.get_attribute("href")
                if href.startswith("/"):
                    href = "https://www.cotodigital.com.ar" + href
                redir_url = href
            except Exception:
                redir_url = "https://www.cotodigital.com.ar"

            # 6.10) Fecha de actualización en ISO 8601 UTC
            update_date = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

            # 6.11) Crear objeto para el feed individual
            ofertas_feed.append({
                "uid": prod_id,
                "updateDate": update_date,
                "titleText": f"Oferta: {nombre}",
                "mainText": nombre,
                "redirectionUrl": redir_url
            })

            vistos.add(prod_id)
            ofertas_en_pagina += 1

        if ofertas_en_pagina == 0:
            print("🔍 Esta página no tiene productos en oferta.")

        # 6.12) Paginación: clic en “Siguiente”
        try:
            siguiente_xpath = "//a[contains(@class,'page-back-next') and normalize-space(text())='Siguiente']"
            btn_siguiente = driver.find_element(By.XPATH, siguiente_xpath)
            clases = btn_siguiente.get_attribute("class") or ""
            if "disabled" in clases:
                print("\n🏁 Paginación deshabilitada. Finalizando recorrido.")
                break

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_siguiente)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", btn_siguiente)

            pagina += 1
            WebDriverWait(driver, 15).until(EC.staleness_of(titulos[0]))
            time.sleep(2)
            continue

        except (NoSuchElementException, TimeoutException):
            print("\n🏁 No hay más páginas. Finalizando recorrido.")
            break

finally:
    driver.quit()

# -------------------- COMPARAR CON OFERTAS PREVIAS Y ENVÍO CONDICIONAL --------------------

# -------------------- COMPARAR CON OFERTAS PREVIAS Y ENVÍO CONDICIONAL --------------------

feed_individual_previo = cargar_feed_previo()
prev_uids_ind = {item["uid"] for item in feed_individual_previo if isinstance(item, dict) and "uid" in item}
new_uids_ind = {item["uid"] for item in ofertas_feed}

if prev_uids_ind == new_uids_ind:
    print("🔍 No hay cambios respecto a las últimas ofertas guardadas. No envío Telegram.")
else:
    # Guardar feed individual completo
    guardar_feed_individual(ofertas_feed)

    # Guardar feed agrupado
    guardar_feed_agrupado(ofertas_feed)

    # Enviar mensaje a Telegram
    encabezado = f"<b>Ofertas encontradas ({len(todas_ofertas_texto)})</b>:\n\n"
    cuerpo = "\n".join(todas_ofertas_texto)
    texto_final = encabezado + cuerpo

    enviar_telegram(texto_final)
    print("✅ Envié el mensaje agrupado de ofertas por Telegram.")

    # —————————— Aquí llamamos a auto_push.py ——————————
    try:
        from autopush import auto_push

        # Ruta a tu repositorio local (donde está el .git y donde se guardan los JSON)
        repo_folder = r"C:\Users\PC\Desktop\asistente jarvis\proyectoCoto\flash-ofertas-coto"

        ok = auto_push(
            repo_folder,
            commit_message="Auto: actualizando JSON de últimas ofertas",
            branch="main"
        )
        if ok:
            print("✅ auto_push.py se ejecutó correctamente.")
        else:
            print("❌ Ocurrió un error al ejecutar auto_push.py.")

    except ImportError as imp_e:
        print(f"❌ No pude importar auto_push.py: {imp_e}")
    except Exception as ex:
        print(f"❌ Excepción al llamar a auto_push(): {ex}")