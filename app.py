import io
import re

import matplotlib
import pandas as pd

matplotlib.use('Agg')  # Usar el backend Agg antes de importar pyplot
import secrets
from datetime import datetime, timedelta
from functools import wraps
from threading import Thread

import matplotlib.pyplot as plt
import pandas as pd
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from flask import (Flask, Response, abort, flash, jsonify, redirect,
                   render_template, request, send_file, send_from_directory,
                   url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from gensim.models import Word2Vec
from gensim.utils import simple_preprocess
from sklearn.metrics.pairwise import cosine_similarity
from weasyprint import HTML
from werkzeug.security import check_password_hash, generate_password_hash

# Importación de funciones y configuración de base de datos desde `database.py`
from database import \
    get_noticias_count_by_date_range  # Renombrar correctamente esta función para el conteo de noticias en rango
from database import (  # Funciones para Diario Correo; Funciones para El Peruano
    cursor, db, exportar_noticias_a_csv, exportar_noticias_a_csv_diario,
    exportar_noticias_a_csv_peruano, get_all_noticias, get_all_noticias_diario,
    get_all_noticias_peruano, get_categorias, get_categorias_diario,
    get_categorias_peruano, get_categorias_sin_fronteras,
    get_conteo_noticias_por_categoria_sin_fronteras,
    get_noticias_conteo_por_categoria,
    get_noticias_conteo_por_categoria_diario,
    get_noticias_conteo_por_categoria_peruano, get_noticias_por_categoria,
    get_noticias_por_dia, get_noticias_sin_fronteras,
    get_total_noticias_por_categoria, insert_noticia, noticia_existe,
    obtener_noticias_del_dia, obtener_noticias_del_dia_diario,
    obtener_noticias_del_dia_peruano, obtener_noticias_del_dia_sin_fronteras)
from scraping import scrape_todas_las_categorias
from scrapingtwo import main as run_scraper

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'


# Configuración de Flask-Login

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

class User(UserMixin):
    def __init__(self, id, username, password_hash, role_id, is_approved):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role_id = role_id
        self.is_approved = is_approved

    @staticmethod
    def get_user_by_username(username):
        cursor.execute("SELECT id, username, password_hash, role_id, is_approved FROM users WHERE username = %s", (username,))
        user_data = cursor.fetchone()
        if user_data:
            return User(*user_data)  # Esto pasa todos los datos al constructor
        return None


    @staticmethod
    def get_user_by_id(user_id):
        cursor.execute("SELECT id, username, password_hash, role_id FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            return User(user_data[0], user_data[1], user_data[2], user_data[3])
        return None

@login_manager.user_loader
def load_user(user_id):
    cursor.execute("SELECT id, username, password_hash, role_id, is_approved FROM users WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        return User(*user_data)  # Crea el usuario con todos los campos
    return None


# Función para convertir fechas relativas a absolutas
def convertir_fecha_relativa(fecha_relativa):
    ahora = datetime.now()
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
            return ahora
        return fecha.strftime('%Y-%m-%d %H:%M:%S')
    return ahora.strftime('%Y-%m-%d %H:%M:%S')

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash("Ya has iniciado sesión.", "info")
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.get_user_by_username(username)  # Incluye is_approved
        
        if user and check_password_hash(user.password_hash, password):
            if user.is_approved == 0:  # Si no está aprobado
                flash("Tu cuenta está pendiente de aprobación por un administrador.", "warning")
                return redirect(url_for('login'))
            login_user(user)
            flash("Inicio de sesión exitoso", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        else:
            flash("Usuario o contraseña incorrectos", "error")
            return redirect(url_for('login'))

    return render_template('login.html')





@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión correctamente.", "success")
    return redirect(url_for('home'))


# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         role_id = request.form['role_id']
#         password_hash = generate_password_hash(password)
        
#         # Insertar con is_approved = 0
#         cursor.execute(
#             "INSERT INTO users (username, password_hash, role_id, is_approved) VALUES (%s, %s, %s, %s)",
#             (username, password_hash, role_id, 0)
#         )
#         db.commit()
#         flash("Registro exitoso. Por favor, espera la aprobación del administrador.", "success")
#         return redirect(url_for('login'))

#     cursor.execute("SELECT id, name FROM roles")
#     roles = cursor.fetchall()
#     return render_template('register.html', roles=roles)


@app.route('/admin/manage_roles', methods=['GET', 'POST'])
@login_required
def manage_roles():
    if current_user.role_id != 1:  # Solo los administradores pueden acceder
        flash("No tienes permiso para acceder a esta página.", "danger")
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        new_role = request.form.get('new_role')

        try:
            cursor.execute(
                "UPDATE users SET role_id = %s WHERE id = %s",
                (new_role, user_id)
            )
            db.commit()
            flash("Rol actualizado con éxito.", "success")
        except Exception as e:
            flash(f"Error al actualizar el rol: {str(e)}", "danger")

    # Obtener lista de usuarios y roles
    cursor.execute("SELECT id, username, role_id FROM users")
    users = cursor.fetchall()
    roles = [
        (1, "Administrador"),
        (2, "Usuario Premium"),
        (3, "Usuario Regular"),
    ]

    return render_template('manage_roles.html', users=users, roles=roles)



import os

from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de tamaño: 16MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Crear carpeta de uploads si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Función para validar archivos permitidos
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ruta de registro
# Ruta para el registro de usuarios
import requests


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Recibir los datos del formulario
        username = request.form['username']
        password = request.form['password']
        role_id = request.form['role_id']
        payment_proof = request.files.get('payment_proof')
        
        # Datos obtenidos desde la API de RENIEC (ya recibidos desde la vista)
        nombres = request.form['nombres']
        apellido_paterno = request.form['apellido_paterno']
        apellido_materno = request.form['apellido_materno']

        # Validar si el comprobante de pago es válido
        if payment_proof and allowed_file(payment_proof.filename):
            # Guardar archivo de pago
            filename = secure_filename(payment_proof.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            payment_proof.save(file_path)

            # Hash de la contraseña
            password_hash = generate_password_hash(password)

            # Insertar datos del usuario en la base de datos
            try:
                cursor.execute(
                    """INSERT INTO users (username, password_hash, role_id, is_approved, payment_proof_path, nombres, apellido_paterno, apellido_materno) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (username, password_hash, role_id, False, filename, nombres, apellido_paterno, apellido_materno)
                )
                db.commit()
                flash("Registro exitoso. Tu comprobante ha sido enviado para revisión.", "success")
                return redirect(url_for('login'))
            except Exception as e:
                db.rollback()
                flash(f"Error al registrar usuario: {str(e)}", "danger")
        else:
            flash("Debe subir un comprobante válido en formato PNG, JPG, JPEG o GIF.", "danger")

    # Obtener todos los roles disponibles desde la tabla roles (simulado)
    roles = [(2, "Usuario Premium"), (3, "Usuario Regular")]  # Simulación de roles disponibles
    return render_template('register.html', roles=roles)



# Ruta para servir las imágenes subidas
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)





@app.route('/admin/approve_users', methods=['GET', 'POST'])
@login_required
def approve_users():
    if current_user.role_id != 1:  # Solo el administrador puede aprobar
        flash("Acceso denegado.", "error")
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        user_id = request.form['user_id']
        cursor.execute("UPDATE users SET is_approved = 1 WHERE id = %s", (user_id,))
        db.commit()
        flash("Usuario aprobado exitosamente.", "success")

    cursor.execute("SELECT id, username, is_approved FROM users WHERE is_approved = 0")
    unapproved_users = cursor.fetchall()
    return render_template('approve_users.html', users=unapproved_users)


@app.before_request
def restrict_unapproved_users():
    if current_user.is_authenticated and current_user.is_approved == 0:  # Aquí verificamos con 0
        if request.endpoint not in ['logout', 'login', 'register']:
            flash("Tu cuenta está pendiente de aprobación.", "warning")
            return redirect(url_for('logout'))



def requires_roles(*roles):
    """
    Decorador para restringir el acceso a usuarios con roles específicos.
    :param roles: Lista de roles permitidos.
    """
    def wrapper(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Verificar si el usuario está autenticado
            if not current_user.is_authenticated:
                return abort(403)  # Prohibir acceso si no está autenticado

            # Verificar si el rol del usuario está en la lista de roles permitidos
            if current_user.role_id not in roles:
                return abort(403)  # Prohibir acceso si el rol no es permitido
            
            # Si cumple con los roles, ejecutar la función
            return f(*args, **kwargs)
        return wrapped
    return wrapper




@app.route('/admin', methods=['GET'])
@login_required
def admin_page():
    # Obtener el número de página de la solicitud (por defecto la página 1)
    page = request.args.get('page', 1, type=int)
    per_page = 30  # Mostrar 10 noticias por página

    # Obtener el término de búsqueda
    search_query = request.args.get('search', '')

    # Si hay una búsqueda, filtrar las noticias por el título
    if search_query:
        cursor.execute(
            "SELECT * FROM noticias WHERE title LIKE %s LIMIT %s OFFSET %s",
            ('%' + search_query + '%', per_page, (page - 1) * per_page)
        )
    else:
        cursor.execute("SELECT * FROM noticias LIMIT %s OFFSET %s", (per_page, (page - 1) * per_page))

    noticias = cursor.fetchall()

    # Obtener el número total de noticias
    if search_query:
        cursor.execute("SELECT COUNT(*) FROM noticias WHERE title LIKE %s", ('%' + search_query + '%',))
    else:
        cursor.execute("SELECT COUNT(*) FROM noticias")
    
    total_noticias = cursor.fetchone()[0]

    # Calcular el número total de páginas
    total_pages = (total_noticias // per_page) + (1 if total_noticias % per_page > 0 else 0)

    # Incluir los datos del gráfico de noticias por día
    df = get_noticias_por_dia()  # Llamar a la función que obtenga las noticias por día

    # Verificar si la solicitud es AJAX y retornar solo la tabla
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('tabla_noticias.html', noticias=noticias, page=page, total_pages=total_pages)

    # Si no es AJAX, renderizar la página completa
    return render_template(
        'admin.html',
        noticias=noticias,
        page=page,
        total_pages=total_pages,
        search_query=search_query,
        noticias_por_dia=df
    )
    



@app.route('/')
def home():
    # Obtener categorías y noticias
    categorias = get_categorias()
    noticias = get_all_noticias()
    
    # Obtener las noticias del día actual y su recuento
    noticias_del_dia, total_noticias_del_dia = obtener_noticias_del_dia()

    # Procesar las categorías con conteo
    categorias_con_conteo = []
    for categoria in categorias:
        conteo = get_noticias_conteo_por_categoria(categoria)
        categorias_con_conteo.append({
            'nombre': categoria,
            'conteo': conteo
        })

    # Total de noticias en la base de datos
    total_noticias = len(noticias)

    # Renderizar la plantilla con las noticias, categorías, y totales
    return render_template(
        'index.html',
        news=noticias,
        categorias=categorias_con_conteo,
        total_noticias=total_noticias,
        noticias_del_dia=noticias_del_dia,
        total_noticias_del_dia=total_noticias_del_dia
    )


@app.route('/diario_sin_fronteras')
@login_required
@requires_roles(1, 2, 3)
def sinfronteras():
    # Only allow access if the user is logged in
    if not current_user.is_authenticated:
        flash("Por favor, inicie sesión o cree una cuenta para ver todas las noticias de Diario Sin Fronteras.")
        return redirect(url_for('login'))
    
    # Get categories and news specific to "Diario Sin Fronteras"
    categorias = get_categorias_sin_fronteras()
    noticias = get_noticias_sin_fronteras()
    
    # Get today’s news and its count for "Diario Sin Fronteras"
    noticias_del_dia, total_noticias_del_dia = obtener_noticias_del_dia_sin_fronteras()

    # Process categories with count
    categorias_con_conteo = []
    for categoria in categorias:
        conteo = get_conteo_noticias_por_categoria_sin_fronteras(categoria)
        categorias_con_conteo.append({
            'nombre': categoria,
            'conteo': conteo
        })

    # Total number of news in the database for "Diario Sin Fronteras"
    total_noticias = len(noticias)

    # Render the template with news, categories, and totals
    return render_template(
        'diario_sin_fronteras.html',
        news=noticias,
        categorias=categorias_con_conteo,
        total_noticias=total_noticias,
        noticias_del_dia=noticias_del_dia,
        total_noticias_del_dia=total_noticias_del_dia
    )
    

@app.route('/diario_correo')
@login_required
@requires_roles(1, 2, 3)
def diariocorreo():
    # Only allow access if the user is logged in
    if not current_user.is_authenticated:
        flash("Por favor, inicie sesión o cree una cuenta para ver todas las noticias de Diario Correo.")
        return redirect(url_for('login'))
    
    # Get categories and news only from "Diario Correo"
    categorias = get_categorias_diario("Diario Correo")
    noticias = get_all_noticias_diario("Diario Correo")
    
    # Get today’s news and its count for "Diario Correo"
    noticias_del_dia, total_noticias_del_dia = obtener_noticias_del_dia_diario("Diario Correo")

    # Process categories with count
    categorias_con_conteo = []
    for categoria in categorias:
        conteo = get_noticias_conteo_por_categoria_diario(categoria, "Diario Correo")
        categorias_con_conteo.append({
            'nombre': categoria,
            'conteo': conteo
        })

    # Total number of news in the database of Diario Correo
    total_noticias = len(noticias)

    # Render the template with news, categories, and totals
    return render_template(
        'diario_correo.html',
        news=noticias,
        categorias=categorias_con_conteo,
        total_noticias=total_noticias,
        noticias_del_dia=noticias_del_dia,
        total_noticias_del_dia=total_noticias_del_dia
    )


@app.route('/diario_el_peruano')
@login_required
@requires_roles(1, 2)
def diarioelperuano():
    # Only allow access if the user is logged in
    if not current_user.is_authenticated:
        flash("Por favor, inicie sesión o cree una cuenta para ver todas las noticias de El Peruano.")
        return redirect(url_for('login'))
    
    # Get categories and news only from "El Peruano"
    categorias = get_categorias_peruano()
    noticias = get_all_noticias_peruano()
    
    # Get today’s news and its count for "El Peruano"
    noticias_del_dia, total_noticias_del_dia = obtener_noticias_del_dia_peruano()

    # Process categories with count
    categorias_con_conteo = []
    for categoria in categorias:
        conteo = get_noticias_conteo_por_categoria_peruano(categoria)
        categorias_con_conteo.append({
            'nombre': categoria,
            'conteo': conteo
        })

    # Total number of news in the database of El Peruano
    total_noticias = len(noticias)

    # Render the template with news, categories, and totals
    return render_template(
        'diario_el_peruano.html',
        news=noticias,
        categorias=categorias_con_conteo,
        total_noticias=total_noticias,
        noticias_del_dia=noticias_del_dia,
        total_noticias_del_dia=total_noticias_del_dia
    )

    
@app.route('/categoria/<categoria_nombre>')
def noticias_por_categoria(categoria_nombre):
    noticias = get_noticias_por_categoria(categoria_nombre)
    categorias = get_categorias()
    return render_template('index.html', news=noticias, categorias=categorias, categoria_seleccionada=categoria_nombre)



# import nltk
# import pandas as pd
# from nltk.corpus import stopwords
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity

# # Descargar palabras vacías en español si aún no lo has hecho
# nltk.download('stopwords')

# # Obtener las palabras vacías en español
# spanish_stopwords = stopwords.words('spanish')

# # Vectorizador TF-IDF con palabras vacías en español
# vectorizer = TfidfVectorizer(stop_words=spanish_stopwords)

# @app.route('/noticia/<int:noticia_id>')
# def noticia_detallada(noticia_id):
#     # Cargar la noticia actual
#     cursor.execute("SELECT * FROM noticias WHERE id = %s", (noticia_id,))
#     noticia = cursor.fetchone()

#     if noticia:
#         # Obtener noticias relacionadas por categoría
#         categoria = noticia[7]  # Suponiendo que `source` está en la posición 7
#         cursor.execute(
#             "SELECT id, title, content, source, diario, date FROM noticias WHERE source = %s AND id != %s ORDER BY date DESC LIMIT 10",
#             (categoria, noticia_id),
#         )
#         noticias_categoria = cursor.fetchall()

#         # Cargar todas las noticias para similitud por contenido
#         cursor.execute("SELECT id, title, content FROM noticias")
#         noticias = cursor.fetchall()

#         # Preparar datos para recomendaciones basadas en contenido
#         noticias_df = pd.DataFrame(noticias, columns=["id", "title", "content"])
#         noticias_df["combined"] = noticias_df["title"] + " " + noticias_df["content"]

#         # Crear la matriz TF-IDF y calcular similitudes
#         tfidf_matrix = vectorizer.fit_transform(noticias_df["combined"])
#         idx = noticias_df[noticias_df["id"] == noticia_id].index[0]
#         cosine_sim = cosine_similarity(tfidf_matrix[idx], tfidf_matrix).flatten()

#         # Obtener índices de las noticias más similares
#         similar_indices = cosine_sim.argsort()[-6:-1][::-1]  # Excluir la noticia actual
#         recomendaciones_similares = noticias_df.iloc[similar_indices].to_dict("records")

#         return render_template(
#             "detalle.html",
#             noticia=noticia,
#             noticias_categoria=noticias_categoria,
#             recomendaciones_similares=recomendaciones_similares,
#         )
#     else:
#         return "No se encontró la noticia.", 404


@app.route('/noticia/<int:noticia_id>')
def noticia_detallada(noticia_id):
    # Cargar la noticia actual
    cursor.execute("SELECT * FROM noticias WHERE id = %s", (noticia_id,))
    noticia = cursor.fetchone()

    if noticia:
        # Obtener noticias relacionadas por categoría
        categoria = noticia[7]  # Suponiendo que `source` está en la posición 7
        cursor.execute(
            "SELECT id, title, content, source, diario, date FROM noticias WHERE source = %s AND id != %s ORDER BY date DESC LIMIT 10",
            (categoria, noticia_id),
        )
        noticias_categoria = cursor.fetchall()

        # Cargar todas las noticias para similitud por contenido
        cursor.execute("SELECT id, title, content FROM noticias")
        noticias = cursor.fetchall()

        # Preparar datos para Word2Vec
        noticias_df = pd.DataFrame(noticias, columns=["id", "title", "content"])
        noticias_df["combined"] = noticias_df["title"] + " " + noticias_df["content"]

        # Preprocesar los textos
        noticias_df["tokens"] = noticias_df["combined"].apply(simple_preprocess)

        # Entrenar un modelo Word2Vec
        model = Word2Vec(sentences=noticias_df["tokens"], vector_size=100, window=10, min_count=1, workers=4)

        # Generar vectores para cada noticia
        def vectorize_text(tokens):
            vectors = [model.wv[word] for word in tokens if word in model.wv]
            if len(vectors) > 0:
                return sum(vectors) / len(vectors)
            else:
                return None

        noticias_df["vector"] = noticias_df["tokens"].apply(vectorize_text)
        noticias_df = noticias_df.dropna(subset=["vector"])  # Eliminar textos sin vectores

        # Comparar similitud entre la noticia actual y las demás
        current_vector = noticias_df[noticias_df["id"] == noticia_id]["vector"].values[0]
        noticias_df["similarity"] = noticias_df["vector"].apply(lambda x: cosine_similarity([current_vector], [x])[0][0])

        # Obtener las noticias más similares
        recomendaciones_similares = noticias_df[noticias_df["id"] != noticia_id].sort_values(
            by="similarity", ascending=False
        ).head(8).to_dict("records")

        return render_template(
            "detalle.html",
            noticia=noticia,
            noticias_categoria=noticias_categoria,
            recomendaciones_similares=recomendaciones_similares,
        )
    else:
        return "No se encontró la noticia.", 404




@app.route('/estadisticas')
def ver_estadisticas():
     hoy = datetime.now().strftime('%Y-%m-%d')
     ayer = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
     semana_anterior = (datetime.now() - timedelta(weeks=1)).strftime('%Y-%m-%d')
     total_hoy = get_noticias_count_by_date_range(hoy)
     total_ayer = get_noticias_count_by_date_range(ayer, ayer)
     total_semana_anterior = get_noticias_count_by_date_range(semana_anterior, ayer)
     total_noticias = get_noticias_count_by_date_range('1900-01-01')
     noticias_por_categoria = get_total_noticias_por_categoria()
     return render_template('estadisticas.html', 
                            total_hoy=total_hoy, 
                            total_ayer=total_ayer, 
                            total_semana_anterior=total_semana_anterior,
                            total_noticias=total_noticias,
                            noticias_por_categoria=noticias_por_categoria)
    
    
     # Ruta para la vista de noticias del día
#--------REPORTES----------------



@app.route('/graficos/noticias_por_dia', methods=['GET'])
def graficar_noticias_por_dia():
    try:
        # Obtener los parámetros de fecha (opcionales)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="noticias_db",
            port="3308"
        )

        with db_connection.cursor() as local_cursor:
            # Si se proporcionan fechas, filtrar por rango
            if start_date and end_date:
                query = """
                    SELECT DATE(fecha_scraping) as scrape_date, COUNT(*) as total_noticias
                    FROM noticias
                    WHERE fecha_scraping BETWEEN %s AND %s
                    GROUP BY scrape_date
                    ORDER BY scrape_date DESC
                """
                local_cursor.execute(query, (start_date, end_date))
            else:
                # Si no hay fechas, devolver todos los datos
                query = """
                    SELECT DATE(fecha_scraping) as scrape_date, COUNT(*) as total_noticias
                    FROM noticias
                    GROUP BY scrape_date
                    ORDER BY scrape_date DESC
                """
                local_cursor.execute(query)

            result = local_cursor.fetchall()

        # Convertir los datos a JSON
        data = [{"scrape_date": row[0].strftime('%Y-%m-%d'), "total_noticias": row[1]} for row in result]
        db_connection.close()
        return jsonify(data)
    except Exception as e:
        print(f"Error en /graficos/noticias_por_dia: {e}")
        return "Error interno del servidor", 500




    
@app.route('/graficos/distribucion_noticias_por_categoria', methods=['GET'])
def graficar_distribucion_noticias_por_categoria():
    try:
        # Obtener el parámetro de "diario" del frontend
        diario = request.args.get('diario')

        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="noticias_db",
            port="3308"
        )
        with db_connection.cursor() as local_cursor:
            if diario:
                # Si se proporciona un diario, filtrar por él
                query = """
                    SELECT source, COUNT(*) as total_noticias 
                    FROM noticias 
                    WHERE diario = %s
                    GROUP BY source 
                    ORDER BY total_noticias DESC
                """
                local_cursor.execute(query, (diario,))
            else:
                # Si no se proporciona un diario, mostrar todas las categorías
                query = """
                    SELECT source, COUNT(*) as total_noticias 
                    FROM noticias 
                    GROUP BY source 
                    ORDER BY total_noticias DESC
                """
                local_cursor.execute(query)

            result = local_cursor.fetchall()
        
        # Convertir los resultados a formato JSON
        data = [{"source": row[0], "total_noticias": row[1]} for row in result]
        db_connection.close()
        return jsonify(data)
    except Exception as e:
        print(f"Error en /graficos/distribucion_noticias_por_categoria: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500



@app.route('/graficos/distribucion_noticias_por_diario', methods=['GET'])
def graficar_distribucion_noticias_por_diario():
    try:
        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="noticias_db",
            port="3308"
        )
        with db_connection.cursor() as local_cursor:
            query = """
                SELECT diario, COUNT(*) as total_noticias 
                FROM noticias 
                GROUP BY diario 
                ORDER BY total_noticias DESC
            """
            local_cursor.execute(query)
            result = local_cursor.fetchall()

        # Convertir los resultados a formato JSON
        data = [{"diario": row[0], "total_noticias": row[1]} for row in result]
        db_connection.close()
        return jsonify(data)
    except Exception as e:
        print(f"Error en /graficos/distribucion_noticias_por_diario: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500





@app.route('/graficos/longitud_media_por_categoria', methods=['GET'])
def graficar_longitud_media_por_categoria():
    try:
        # Obtener el parámetro "diario" del frontend
        diario = request.args.get('diario')

        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="noticias_db",
            port="3308"
        )
        with db_connection.cursor() as local_cursor:
            if diario:
                # Si se proporciona un diario, filtrar por él
                query = """
                    SELECT source, AVG(CHAR_LENGTH(content)) as avg_length 
                    FROM noticias 
                    WHERE diario = %s
                    GROUP BY source 
                    ORDER BY avg_length DESC
                """
                local_cursor.execute(query, (diario,))
            else:
                # Si no se proporciona un diario, calcular para todos los diarios
                query = """
                    SELECT source, AVG(CHAR_LENGTH(content)) as avg_length 
                    FROM noticias 
                    GROUP BY source 
                    ORDER BY avg_length DESC
                """
                local_cursor.execute(query)

            result = local_cursor.fetchall()

        # Convertir los resultados a formato JSON
        data = [{"source": row[0], "avg_length": row[1]} for row in result]
        db_connection.close()
        return jsonify(data)
    except Exception as e:
        print(f"Error en /graficos/longitud_media_por_categoria: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500



@app.route('/graficos/top_sources_week', methods=['GET'])
def graficar_top_sources_week():
    try:
        # Obtener los parámetros "diario", "start_date" y "end_date" desde el frontend
        diario = request.args.get('diario')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Crear conexión independiente
        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="noticias_db",
            port="3308"
        )
        with db_connection.cursor() as local_cursor:
            if start_date and end_date:
                if diario:
                    # Filtrar por diario y rango de fechas
                    query = """
                        SELECT source, COUNT(*) as total 
                        FROM noticias 
                        WHERE fecha_scraping BETWEEN %s AND %s AND diario = %s
                        GROUP BY source 
                        ORDER BY total DESC 
                        LIMIT 5
                    """
                    local_cursor.execute(query, (start_date, end_date, diario))
                else:
                    # Filtrar solo por rango de fechas
                    query = """
                        SELECT source, COUNT(*) as total 
                        FROM noticias 
                        WHERE fecha_scraping BETWEEN %s AND %s
                        GROUP BY source 
                        ORDER BY total DESC 
                        LIMIT 5
                    """
                    local_cursor.execute(query, (start_date, end_date))
            else:
                # Si no se proporcionan fechas, usar la última semana por defecto
                semana_anterior = (datetime.now() - timedelta(weeks=1)).strftime('%Y-%m-%d')
                if diario:
                    query = """
                        SELECT source, COUNT(*) as total 
                        FROM noticias 
                        WHERE fecha_scraping >= %s AND diario = %s
                        GROUP BY source 
                        ORDER BY total DESC 
                        LIMIT 5
                    """
                    local_cursor.execute(query, (semana_anterior, diario))
                else:
                    query = """
                        SELECT source, COUNT(*) as total 
                        FROM noticias 
                        WHERE fecha_scraping >= %s
                        GROUP BY source 
                        ORDER BY total DESC 
                        LIMIT 5
                    """
                    local_cursor.execute(query, (semana_anterior,))

            result = local_cursor.fetchall()

        # Convertir los resultados a formato JSON
        data = [{"source": row[0], "total": row[1]} for row in result]
        db_connection.close()
        return jsonify(data)
    except Exception as e:
        print(f"Error en /graficos/top_sources_week: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500



from flask import request
from wordcloud import WordCloud


@app.route('/graficos/nube_de_palabras_titulos', methods=['GET'])
def graficar_nube_de_palabras_titulos():
    try:
        # Obtener los filtros desde el frontend
        diario = request.args.get('diario')
        categoria = request.args.get('categoria')

        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="noticias_db",
            port="3308"
        )
        with db_connection.cursor() as local_cursor:
            # Construir la consulta con los filtros
            query = "SELECT title FROM noticias WHERE 1=1"
            params = []
            if diario:
                query += " AND diario = %s"
                params.append(diario)
            if categoria:
                query += " AND source = %s"
                params.append(categoria)
            
            local_cursor.execute(query, tuple(params))
            result = local_cursor.fetchall()
        
        # Combinar todos los títulos en un solo texto
        text = " ".join([row[0] for row in result if row[0]])  # Evitar títulos nulos
        
        # Verificar si hay texto disponible
        if not text:
            return jsonify({"error": "No hay datos disponibles para generar la nube de palabras"}), 400

        # Generar la nube de palabras
        wordcloud = WordCloud(width=800, height=400, background_color='white', colormap='viridis').generate(text)
        
        # Mostrar la nube de palabras
        fig = plt.figure(figsize=(10, 6))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.tight_layout(pad=0)

        img = io.BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)
        plt.close(fig)
        db_connection.close()
        plt.close('all')
        return Response(img.getvalue(), mimetype='image/png')
    except Exception as e:
        print(f"Error en /graficos/nube_de_palabras_titulos: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500
    
@app.route('/graficos/listar_categorias', methods=['GET'])
def listar_categorias():
    try:
        # Conexión a la base de datos
        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="noticias_db",
            port="3308"
        )
        with db_connection.cursor() as local_cursor:
            query = "SELECT DISTINCT source FROM noticias ORDER BY source ASC"
            local_cursor.execute(query)
            result = local_cursor.fetchall()

        # Convertir el resultado en formato JSON
        categorias = [row[0] for row in result if row[0]]  # Excluir valores nulos o vacíos
        db_connection.close()
        return jsonify(categorias)
    except Exception as e:
        print(f"Error en /graficos/listar_categorias: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


    

@app.route('/graficos/tendencia_noticias_por_dia')
def graficar_tendencia_noticias_por_dia():
    try:
        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="noticias_db",
            port="3308"
        )
        with db_connection.cursor() as local_cursor:
            query = """
                SELECT DATE(date) as dia, COUNT(*) as total_noticias 
                FROM noticias 
                GROUP BY dia 
                ORDER BY dia ASC
            """
            local_cursor.execute(query)
            result = local_cursor.fetchall()
        
        df = pd.DataFrame(result, columns=['dia', 'total_noticias'])
        fig = plt.figure(figsize=(10, 6))
        plt.plot(df['dia'], df['total_noticias'], marker='o', linestyle='-', color='b')
        plt.xlabel('Día')
        plt.ylabel('Total de Noticias')
        plt.title('Tendencia de Noticias Publicadas por Día')
        plt.xticks(rotation=45)
        plt.tight_layout()

        img = io.BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)
        plt.close(fig)
        db_connection.close()
        plt.close('all')
        return Response(img.getvalue(), mimetype='image/png')
    except Exception as e:
        print(f"Error en /graficos/tendencia_noticias_por_dia: {e}")
        return "Error interno del servidor", 500
    
    
    


import io
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import mysql.connector
import pandas as pd
import seaborn as sns
from flask import Response


@app.route('/graficos/heatmap_noticias_por_dia_semana_mes', methods=['GET'])
def graficar_heatmap_noticias_por_dia_semana_mes():
    try:
        # Obtener filtros del frontend
        diario = request.args.get('diario')
        categoria = request.args.get('categoria')

        # Establecer conexión a la base de datos
        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="noticias_db",
            port="3308"
        )
        with db_connection.cursor() as local_cursor:
            # Construir la consulta SQL con filtros opcionales
            query = """
                SELECT WEEK(date, 1) as semana_mes, DAYOFWEEK(date) as dia_semana, COUNT(*) as total_noticias 
                FROM noticias 
                WHERE 1=1
            """
            params = []
            if diario:
                query += " AND diario = %s"
                params.append(diario)
            if categoria:
                query += " AND source = %s"
                params.append(categoria)
            query += " GROUP BY semana_mes, dia_semana"

            local_cursor.execute(query, tuple(params))
            result = local_cursor.fetchall()

        # Convertir los resultados en un DataFrame de Pandas
        df = pd.DataFrame(result, columns=['semana_mes', 'dia_semana', 'total_noticias'])

        # Mapear los días de la semana de números a nombres
        dias_semana = {1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes', 6: 'Sábado', 7: 'Domingo'}
        df['dia_semana'] = df['dia_semana'].map(dias_semana)

        # Pivotar el DataFrame para el formato adecuado del Heatmap
        df_pivot = df.pivot(index='semana_mes', columns='dia_semana', values='total_noticias').fillna(0)

        # Crear el Heatmap
        fig, ax = plt.subplots(figsize=(12, 6))
        sns.heatmap(df_pivot, annot=True, fmt=".0f", cmap="YlGnBu", cbar_kws={'label': 'Total de Noticias'}, ax=ax)
        ax.set_xlabel('Día de la Semana')
        ax.set_ylabel('Semana del Mes')
        ax.set_title('Distribución de Noticias por Semana del Mes y Día de la Semana')
        plt.tight_layout()

        # Guardar la imagen en memoria y devolverla como respuesta
        img = io.BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)
        plt.close(fig)
        db_connection.close()
        
        return Response(img.getvalue(), mimetype='image/png')
    
    except Exception as e:
        print(f"Error en /graficos/heatmap_noticias_por_dia_semana_mes: {e}")
        return "Error interno del servidor", 500

    
    
#--------------------------------

#------------API-----------------
def obtener_noticias_tesla():
    url = "https://newsapi.org/v2/everything?q=tesla&from=2024-10-22&sortBy=publishedAt&language=es&apiKey=93eb0cbb510e4ecab64d79ccb7c31973"
    response = requests.get(url)
    if response.status_code == 200:
        noticias = response.json().get("articles", [])
        # Mapeo para normalizar los datos
        for noticia in noticias:
            noticia['titulo'] = noticia.get('title', '')
            noticia['descripcion'] = noticia.get('description', '')
            noticia['fecha_publicacion'] = noticia.get('publishedAt', '').split('T')[0]
            noticia['fuente'] = noticia.get('source', {}).get('name', '')
            noticia['url_imagen'] = noticia.get('urlToImage', '')
        return noticias
    else:
        print(f"Error al obtener noticias: {response.status_code}")
        return []
    
@app.route('/noticias_tesla', methods=['GET'])
def noticias_tesla():
    noticias = obtener_noticias_tesla()  # Obtener todas las noticias para cargar por defecto
    return render_template('noticias_tesla.html', noticias=noticias)


@app.route('/api/filtrar_noticias', methods=['GET'])
def filtrar_noticias():
    noticias = obtener_noticias_tesla()

    # Obtener los parámetros de búsqueda de la solicitud
    titulo = request.args.get('titulo', '').lower()
    fecha = request.args.get('fecha', '')

    # Filtrar noticias
    if titulo:
        noticias = [n for n in noticias if titulo in n.get('titulo', '').lower()]
    if fecha:
        noticias = [n for n in noticias if n.get('fecha_publicacion', '') == fecha]

    return {"noticias": noticias}

#-----------------------

def obtener_noticias_apple():
    url = "https://newsapi.org/v2/everything?q=apple&from=2024-11-21&to=2024-11-21&sortBy=popularity&language=es&apiKey=93eb0cbb510e4ecab64d79ccb7c31973"
    response = requests.get(url)
    if response.status_code == 200:
        noticias = response.json().get("articles", [])
        # Mapeo para normalizar los datos
        for noticia in noticias:
            noticia['titulo'] = noticia.get('title', '')
            noticia['descripcion'] = noticia.get('description', '')
            noticia['fecha_publicacion'] = noticia.get('publishedAt', '').split('T')[0]
            noticia['fuente'] = noticia.get('source', {}).get('name', '')
            noticia['url_imagen'] = noticia.get('urlToImage', '')
        return noticias
    else:
        print(f"Error al obtener noticias: {response.status_code}")
        return []

@app.route('/noticias_apple', methods=['GET'])
def noticias_apple():
    noticias = obtener_noticias_apple()  # Obtener todas las noticias para cargar por defecto
    return render_template('noticias_apple.html', noticias=noticias)

@app.route('/api/filtrar_noticias_apple', methods=['GET'])
def filtrar_noticias_apple():
    noticias = obtener_noticias_apple()

    # Obtener los parámetros de búsqueda de la solicitud
    titulo = request.args.get('titulo', '').lower()
    fecha = request.args.get('fecha', '')

    # Filtrar noticias
    if titulo:
        noticias = [n for n in noticias if titulo in n.get('titulo', '').lower()]
    if fecha:
        noticias = [n for n in noticias if n.get('fecha_publicacion', '') == fecha]

    return {"noticias": noticias}



#------------------------



@app.route('/reportes', methods=['GET', 'POST'])
def ver_reportes():
    noticias = []
    categorias = get_categorias()  # Obteniendo categorías basadas en 'source'
    
    # Obtener diarios únicos de la tabla
    cursor.execute("SELECT DISTINCT diario FROM noticias")
    diarios = [row[0] for row in cursor.fetchall()]
    
    if request.method == 'POST':
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        diario = request.form.get('diario')
        categoria = request.form.get('categoria')  # Aquí es equivalente a 'source'
        
        query = "SELECT * FROM noticias WHERE 1=1"
        params = []
        
        if fecha_inicio and fecha_fin:
            query += " AND date BETWEEN %s AND %s"
            params.extend([fecha_inicio, fecha_fin])
        
        if categoria:  # Ahora usa 'source' en lugar de 'categoria'
            query += " AND source = %s"
            params.append(categoria)
        
        if diario:
            query += " AND diario = %s"
            params.append(diario)
        
        query += " ORDER BY date DESC"
        cursor.execute(query, params)
        noticias = cursor.fetchall()
    
    return render_template(
        'reportes.html',
        noticias=noticias,
        categorias=categorias,
        diarios=diarios
    )



@app.route('/descargar_pdf')
def descargar_pdf_rango():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    categoria = request.args.get('categoria')
    query = "SELECT * FROM noticias WHERE 1=1"
    params = []
    if fecha_inicio and fecha_fin:
        query += " AND date BETWEEN %s AND %s"
        params.extend([fecha_inicio, fecha_fin])
    if categoria:
        query += " AND source = %s"
        params.append(categoria)
    cursor.execute(query, params)
    noticias = cursor.fetchall()
    rendered_html = render_template('reporte_pdf.html', noticias=noticias, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, categoria=categoria)
    pdf = HTML(string=rendered_html).write_pdf()
    response = Response(pdf, mimetype="application/pdf")
    response.headers.set("Content-Disposition", "attachment", filename="reporte_noticias.pdf")
    return response

@app.route('/descargar_reporte_csv', methods=['GET'])
def descargar_reporte_csv():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    categoria = request.args.get('categoria')
    query = "SELECT * FROM noticias WHERE 1=1"
    params = []
    if fecha_inicio and fecha_fin:
        query += " AND date BETWEEN %s AND %s"
        params.extend([fecha_inicio, fecha_fin])
    if categoria:
        query += " AND source = %s"
        params.append(categoria)
    cursor.execute(query, params)
    noticias = cursor.fetchall()
    noticias_df = pd.DataFrame(noticias, columns=['ID', 'Título', 'Fecha', 'Contenido', 'Imagen', 'Fuente', 'Contenido Completo', 'Categoria', 'Fecha de Scraping', 'diario'])
    csv_data = noticias_df.to_csv(index=False)
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=reporte_noticias.csv'}
    )
    
# ------ CRUD noticias
@app.route('/admin/nueva', methods=['GET', 'POST'])
def nueva_noticia():
    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        content = request.form['content']
        image = request.form['image']
        url = request.form['url']
        source = request.form['source']
        full_content = request.form['full_content']

        # Llama a la función para insertar la noticia
        insert_noticia(title, date, content, image, url, source, full_content)
        return redirect(url_for('admin_page'))

    return render_template('nueva_noticia.html')

@app.route('/admin/editar/<int:noticia_id>', methods=['GET', 'POST'])
def editar_noticia(noticia_id):
    # Obtener la noticia desde la base de datos
    cursor.execute("SELECT * FROM noticias WHERE id = %s", (noticia_id,))
    noticia = cursor.fetchone()

    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        content = request.form['content']
        image = request.form['image']
        url = request.form['url']
        source = request.form['source']
        full_content = request.form['full_content']

        # Actualizar la noticia en la base de datos
        query = """
        UPDATE noticias SET title = %s, date = %s, content = %s, image = %s, url = %s, source = %s, full_content = %s 
        WHERE id = %s
        """
        cursor.execute(query, (title, date, content, image, url, source, full_content, noticia_id))
        db.commit()
        return redirect(url_for('admin_page'))

    # Formatea la fecha para el formulario si es un datetime
    noticia = list(noticia)
    if isinstance(noticia[2], datetime):
        noticia[2] = noticia[2].strftime('%Y-%m-%d')

    return render_template('editar_noticia.html', noticia=noticia)

@app.route('/admin/eliminar/<int:noticia_id>')
def eliminar_noticia(noticia_id):
    cursor.execute("DELETE FROM noticias WHERE id = %s", (noticia_id,))
    db.commit()
    return redirect(url_for('admin_page'))
# -------------

@app.route('/descargar_csv')
def descargar_csv():
    exportar_noticias_a_csv()
    return send_file('noticias_exportadas.csv', as_attachment=True)

def ejecutar_scraping_periodico():
    scrape_todas_las_categorias()
    print("Scraping periódico ejecutado.")

scheduler = BackgroundScheduler()
scheduler.add_job(ejecutar_scraping_periodico, 'interval', minutes=10)
scheduler.start()

@app.route('/')
def inicio():
    return render_template('index.html')

# Ruta para Diario Correo
@app.route('/diario_correo')
def diario_correo():
    return render_template('diario_correo.html')

# Ruta para Diario Sin Fronteras
@app.route('/diario_sin_fronteras')
def diario_sin_fronteras():
    return render_template('diario_sin_fronteras.html')  # Redirige a la misma página que la de inicio

# Ruta para Diario El Peruano
@app.route('/diario_el_peruano')
def diario_el_peruano():
    return render_template('diario_el_peruano.html')

def start_scraping():
    print("Iniciando scraping en segundo plano...")
    scrape_todas_las_categorias()
    run_scraper()
    exportar_noticias_a_csv()
    print("Scraping completado.")

if __name__ == '__main__':
    # scraping_thread = Thread(target=start_scraping)
    # scraping_thread.start()
    app.run(debug=True)
