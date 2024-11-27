import time
from datetime import datetime

import mysql.connector
from bs4 import BeautifulSoup
from selenium import webdriver

# Configuración de Selenium
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Ejecuta en segundo plano
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# Inicializar el navegador
driver = webdriver.Chrome(options=options)

# Conexión a la base de datos
db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="noticias_db",
    port="3308"
)
db_cursor = db_connection.cursor()

# URLs de categorías para scraping
categories = {
    "Derecho": "https://www.elperuano.pe/derecho",
    "Economía": "https://www.elperuano.pe/economia",
    "Actualidad": "https://www.elperuano.pe/actualidad",
    "Politica": "https://www.elperuano.pe/politica",
    "Pais": "https://www.elperuano.pe/pais",
    "Mundo": "https://www.elperuano.pe/mundo",
    "Deporte": "https://www.elperuano.pe/deportes",
    "Cultural": "https://www.elperuano.pe/cultural",
    "Opinión": "https://www.elperuano.pe/opinion",
    "Editorial": "https://www.elperuano.pe/editorial",
    "Especial": "https://www.elperuano.pe/central"
}

def noticia_existe(url):
    db_cursor.execute("SELECT COUNT(*) FROM noticias WHERE url = %s", (url,))
    return db_cursor.fetchone()[0] > 0

def guardar_noticia(data):
    query = """
        INSERT INTO noticias (title, date, content, image, url, full_content, source, fecha_scraping, diario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        data['title'], data['date'], data['content'], data['image'], data['url'],
        data['full_content'], data['source'], data['fecha_scraping'], data['diario']
    )
    db_cursor.execute(query, values)
    db_connection.commit()

def obtener_contenido_completo(url_noticia):
    driver.get(url_noticia)
    time.sleep(3)  # Esperar a que se cargue el contenido
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Modifica el selector según el contenedor del texto completo
    full_content_tag = soup.find("div", class_="contenido")  # Cambia este selector si es necesario
    full_content = full_content_tag.get_text(separator="\n").strip() if full_content_tag else "Contenido no disponible"
    return full_content

def scrape_category(url, source):
    print(f"Scraping categoría: {source} - URL: {url}")
    
    # Usar Selenium para cargar la página de categoría
    driver.get(url)
    time.sleep(5)  # Esperar a que el contenido dinámico se cargue

    # Obtener el HTML renderizado
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    noticias = soup.find_all("div", class_="card z-depth-0 card-600 borderadius6-600 cursornoticia")

    if not noticias:
        print("No se encontraron noticias con el selector proporcionado.")
        return

    for noticia in noticias:
        title_tag = noticia.find("a", class_="titular")
        date_tag = noticia.find("span", class_="card-title3")
        content_tag = noticia.find("a", class_="bajada")
        image_tag = noticia.find("img", class_="fotonoticiah fotobackground")
        
        # Construir URL completa
        url_noticia = "https://www.elperuano.pe/" + title_tag['href'] if title_tag else None

        # Verificación de existencia de cada campo antes de extraer
        title = title_tag.text.strip() if title_tag else "Título no disponible"
        # Convert date to the format YYYY-MM-DD
        date_str = date_tag.text.strip() if date_tag else "Fecha no disponible"
        try:
            # Assuming date format as 'DD/MM/YYYY' from the website; adjust format as necessary
            date = datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            date = "Fecha no disponible"
        content = content_tag.text.strip() if content_tag else "Resumen no disponible"
        image = image_tag['src'] if image_tag else None

        if url_noticia and not noticia_existe(url_noticia):
            # Llamar a la función para obtener el contenido completo
            full_content = obtener_contenido_completo(url_noticia)

            data = {
                'title': title,
                'date': date,
                'content': content,
                'image': image,
                'url': url_noticia,
                'full_content': full_content,
                'source': source,
                'fecha_scraping': datetime.now(),
                'diario': "El Peruano"
            }
            guardar_noticia(data)
            print(f"Noticia guardada: {title}")
        else:
            print(f"Noticia ya existe o no se encontró URL: {url_noticia}")

# Ejecutar scraping en cada categoría
for source, category_url in categories.items():
    scrape_category(category_url, source=source)

# Cerrar conexión de base de datos y navegador
db_cursor.close()
db_connection.close()
driver.quit()