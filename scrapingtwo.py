from datetime import datetime

import mysql.connector
import requests
from bs4 import BeautifulSoup

# Configuración de la conexión a la base de datos
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'noticias_db',
    'port' : '3308'
}

# Función para obtener la conexión a la base de datos
def get_db_connection():
    return mysql.connector.connect(**db_config)

# Función para insertar un artículo en la base de datos
def insert_article(title, url, date_published, image_url, category, description, full_content, diario):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Formatear la fecha de publicación
        formatted_date = format_date(date_published)

        # Verificar si el artículo ya existe en la base de datos
        check_query = "SELECT COUNT(*) FROM noticias WHERE url = %s"
        cursor.execute(check_query, (url,))
        exists = cursor.fetchone()[0]

        if not exists:
            # Inserta los datos del artículo en la tabla noticias, incluyendo el diario
            query = """
            INSERT INTO noticias (title, url, date, image, source, content, full_content, fecha_scraping, diario)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            fecha_scraping = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(query, (title, url, formatted_date, image_url, category, description, full_content, fecha_scraping, diario))
            conn.commit()
            print(f"Artículo insertado: {title}")

    except mysql.connector.Error as err:
        print(f"Error al insertar el artículo: {err}")
    finally:
        cursor.close()
        conn.close()

# Función para formatear la fecha
def format_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S%z').strftime('%Y-%m-%d')
    except ValueError as e:
        print(f"Error al formatear la fecha: {e}")
        return None

# Verificar si el artículo ya existe en la base de datos
def article_exists_in_db(url):
    conn = get_db_connection()
    cursor = conn.cursor()

    check_query = "SELECT COUNT(*) FROM noticias WHERE url = %s"
    cursor.execute(check_query, (url,))
    exists = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return exists > 0

# Scraping de las categorías del Diario Correo
def scrape_categories(base_url):
    response = requests.get(base_url)
    if response.status_code != 200:
        print(f"Failed to retrieve the page: {base_url}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    category_links = []
    category_container = soup.find('ul', class_='header__featured')
    if category_container:
        for a_tag in category_container.find_all('a', href=True):
            if a_tag['href'].startswith('/'):
                category_links.append(f"{base_url}{a_tag['href']}")

    return category_links

# Scraping de artículos de una categoría
def scrape_articles_from_category(category_url, category_name):
    response = requests.get(category_url)
    if response.status_code != 200:
        print(f"Failed to retrieve the page: {category_url}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    article_links = []
    for a_tag in soup.find_all('a', href=True):
        if '/edicion/' in a_tag['href'] and a_tag['href'] != category_url:
            article_links.append(a_tag['href'])

    # Para cada enlace de artículo en la categoría
    for link in set(article_links):
        full_url = f"https://diariocorreo.pe{link}" if not link.startswith('http') else link
        if not article_exists_in_db(full_url):
            scrape_article(full_url, category_name)  # Extrae todos los detalles del artículo
        else:
            print(f"El artículo ya existe en la base de datos: {full_url}")

# Scraping de un artículo
def scrape_article(url, category_name):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to retrieve the page: {url}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Extraer título
    title_tag = soup.find('h1', itemprop='name')
    title = title_tag.get_text(strip=True) if title_tag else 'No title found'

    # Extraer fecha
    time_tag = soup.find('time')
    date = time_tag.get('datetime') if time_tag else None

    # Extraer contenido breve (descripción o resumen)
    description_tag = soup.find('p', itemprop='description')
    description = description_tag.get_text(strip=True) if description_tag else "Resumen no encontrado"

    # Extraer contenido completo
    content_div = soup.find('div', {'id': 'contenedor'})
    full_content_paragraphs = content_div.find_all('p') if content_div else []
    full_content = ' '.join(p.get_text(strip=True) for p in full_content_paragraphs)

    # Extraer imagen
    img_tag = soup.find('img', class_='s-multimedia__image')
    img_url = img_tag.get('data-src', img_tag.get('src', 'No image found')) if img_tag else 'No image found'

    # Almacenar en la base de datos con el atributo de diario
    if full_content:  # Solo almacenar si hay contenido
        insert_article(title, url, date, img_url, category_name, description, full_content, "Diario Correo")


# Función principal
def main():
    base_url = 'https://diariocorreo.pe'
    category_links = scrape_categories(base_url)
    if category_links:
        for category in category_links:
            category_name = category.split('/')[-2].upper()
            print(f"Scraping category: {category_name}")
            scrape_articles_from_category(category, category_name)
        print("Extracción y almacenamiento completado.")
    else:
        print("No se encontraron categorías.")

# Ejecutar la función principal
if __name__ == '__main__':
    main()
