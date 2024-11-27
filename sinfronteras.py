# Función para convertir fechas relativas a absolutas
def convertir_fecha_relativa(fecha_relativa):
    ahora = datetime.now()
    
    # Buscar la cantidad de tiempo y el tipo (horas, días, etc.)
    match = re.search(r'(\d+)\s*(hora|horas|día|días|minuto|minutos|semana|semanas)\s*atrás', fecha_relativa)
    
    if match:
        cantidad = int(match.group(1))
        unidad = match.group(2)
        
        if 'hora' in unidad:
            fecha = ahora - timedelta(hours=cantidad)
        elif 'día' in unidad:
            fecha = ahora - timedelta(days=cantidad)
        elif 'minuto' in unidad:
            fecha = ahora - timedelta(minutes=cantidad)
        elif 'semana' in unidad:
            fecha = ahora - timedelta(weeks=cantidad)
        else:
            return ahora  # Si no es un formato reconocido, retorna la fecha y hora actuales.
        
        return fecha.strftime('%Y-%m-%d %H:%M:%S')
    else:
        # Si no hay coincidencia, asumir que es la fecha actual
        return ahora.strftime('%Y-%m-%d %H:%M:%S')

# Función para verificar si una noticia ya existe en la base de datos
# Función para verificar si una noticia ya existe en la base de datos usando la URL
def noticia_existe(url):
    query = "SELECT COUNT(*) FROM noticias WHERE url = %s"
    cursor.execute(query, (url,))
    result = cursor.fetchone()
    return result[0] > 0


# Función para insertar o actualizar una noticia en la base de datos
def insert_noticia(title, date, content, image, url, source, full_content):
    # Obtener la fecha actual para el scraping
    fecha_scraping = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Verificamos si la noticia ya existe usando la URL como identificador único
    if noticia_existe(url):
        # Si la noticia existe, actualizamos los campos
        print(f"Noticia encontrada: {title}. Se actualizará.")
        query = """
        UPDATE noticias 
        SET title = %s, date = %s, content = %s, image = %s, source = %s, full_content = %s, fecha_scraping = %s
        WHERE url = %s
        """
        values = (title, date, content, image, source, full_content, fecha_scraping, url)
    else:
        # Si la noticia no existe, la insertamos
        print(f"Insertando noticia: {title}.")
        query = """
        INSERT INTO noticias (title, date, content, image, url, source, full_content, fecha_scraping) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (title, date, content, image, url, source, full_content, fecha_scraping)

    # Ejecutamos la consulta
    cursor.execute(query, values)
    db.commit()
    print(f"Operación completada para la noticia: {title}")
    
# Scraping del contenido detallado de Diario Sin Fronteras
def scrape_noticia_detallada_diariosinfronteras(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Buscamos el contenido detallado dentro del bloque con la clase 'post-content-bd'
    full_content = soup.find('div', class_='post-content-bd').get_text(separator="\n").strip()
    
    return full_content

# Scraping de Diario Sin Fronteras (Noticias) por categoría
def scrape_diariosinfronteras_por_categoria(categoria_url, categoria_nombre):
    response = requests.get(categoria_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    articles = soup.find_all('div', class_='layout-wrap')
    for article in articles:
        title = article.find('h3', class_='entry-title').text.strip()
        fecha_relativa = article.find('div', class_='post-date-bd').find('span').text.strip()
        date = convertir_fecha_relativa(fecha_relativa)  # Convertimos la fecha relativa a un formato estándar
        content = article.find('div', class_='post-excerpt').text.strip()
        image = article.find('img')['src']
        url = article.find('a')['href']

        # Scrape full content from Diario Sin Fronteras
        full_content = scrape_noticia_detallada_diariosinfronteras(url)
        
        # Insertar la noticia con el contenido detallado
        insert_noticia(title, date, content, image, url, categoria_nombre, full_content)
        
# Scraping de las categorías de Diario Sin Fronteras
def scrape_categorias_diariosinfronteras():
    url = "https://diariosinfronteras.com.pe/category/tacna/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    categorias = []

    # Busca el ul con el id 'menu-primary'
    menu = soup.find('ul', id='menu-primary')

    # Si encuentra el ul
    if menu:
        # Busca todos los elementos li dentro del ul
        for li in menu.find_all('li'):
            # Dentro del li, encuentra el enlace a
            a_tag = li.find('a')
            # Encuentra el span con la clase 'menu-label' que contiene el nombre de la categoría
            span_tag = a_tag.find('span', class_='menu-label') if a_tag else None
            
            if a_tag and span_tag:
                categoria = span_tag.text.strip()  # Extrae el texto del span (nombre de la categoría)
                url_categoria = a_tag['href']  # Extrae el href (URL de la categoría)
                categorias.append({'nombre': categoria, 'url': url_categoria})

    return categorias

# Scraping de todas las categorías y sus noticias
def scrape_todas_las_categorias():
    categorias = scrape_categorias_diariosinfronteras()
    
    # Iterar sobre cada categoría y extraer las noticias
    for categoria in categorias:
        categoria_url = categoria['url']
        categoria_nombre = categoria['nombre']
        scrape_diariosinfronteras_por_categoria(categoria_url, categoria_nombre)