import mysql.connector
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Conexión a la base de datos MySQL
db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="sakiladw"
)

# Función para obtener datos desde la base de datos
def get_data_from_db(query):
    cursor = db_connection.cursor(dictionary=True)
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    return results

@app.route("/")
def dashboard():
    # Datos para las métricas generales
    total_ingresos = get_data_from_db("SELECT SUM(monto) AS total FROM fact_alquileres")[0]['total']
    total_alquileres = get_data_from_db("SELECT COUNT(*) AS total FROM fact_alquileres")[0]['total']

    # Ingresos por tienda
    ingresos_por_tienda = get_data_from_db("""
        SELECT dim_tienda.ciudad AS tienda, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_tienda ON fact_alquileres.tienda_id = dim_tienda.tienda_id
        GROUP BY dim_tienda.ciudad
    """)

    # Ingresos por categoría
    ingresos_por_categoria = get_data_from_db("""
        SELECT dim_pelicula.categoria AS categoria, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_pelicula ON fact_alquileres.pelicula_id = dim_pelicula.pelicula_id
        GROUP BY dim_pelicula.categoria
    """)

    # Ingresos por año
    ingresos_por_anio = get_data_from_db("""
        SELECT dim_fecha.anio AS anio, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_fecha ON fact_alquileres.fecha_alquiler_id = dim_fecha.fecha_id
        GROUP BY dim_fecha.anio
        ORDER BY dim_fecha.anio
    """)

    # Top 5 clientes
    top_clientes = get_data_from_db("""
        SELECT CONCAT(dim_cliente.nombre, ' ', dim_cliente.apellido) AS cliente, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_cliente ON fact_alquileres.cliente_id = dim_cliente.cliente_id
        GROUP BY dim_cliente.cliente_id
        ORDER BY ingresos DESC
        LIMIT 5
    """)

    # Ingresos por país
    ingresos_por_pais = get_data_from_db("""
        SELECT dim_cliente.pais AS pais, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_cliente ON fact_alquileres.cliente_id = dim_cliente.cliente_id
        GROUP BY dim_cliente.pais
        ORDER BY ingresos DESC
    """)

    # Filtros dinámicos
    categorias = get_data_from_db("SELECT DISTINCT categoria FROM dim_pelicula")
    anios = get_data_from_db("SELECT DISTINCT anio FROM dim_fecha ORDER BY anio")
    tiendas = get_data_from_db("SELECT DISTINCT ciudad FROM dim_tienda ORDER BY ciudad")

    # Enviar datos al frontend
    return render_template(
        "dashboard.html",
        total_ingresos=total_ingresos,
        ingresos_por_tienda=ingresos_por_tienda,
        categorias=categorias,
        anios=anios,
        tiendas=tiendas,
        total_alquileres=total_alquileres,
        ingresos_por_categoria=ingresos_por_categoria,
        ingresos_por_anio=ingresos_por_anio,
        top_clientes=top_clientes,
        ingresos_por_pais=ingresos_por_pais
    )

@app.route("/filtrar", methods=["POST"])
def filtrar():
    # Recibir datos del filtro desde el frontend
    categoria = request.json.get("categoria")
    anio = request.json.get("anio")
    tienda = request.json.get("tienda")
    activo = request.json.get("activo")

    # Construir la cláusula WHERE de forma dinámica
    filtros = []

    if categoria and categoria != "":
        filtros.append(f"dim_pelicula.categoria = '{categoria}'")
    if anio and anio != "":
        filtros.append(f"dim_fecha.anio = {anio}")
    if tienda and tienda != "":
        filtros.append(f"dim_tienda.ciudad = LOWER('{tienda}'")
    if activo and activo != "":  # Activo es un string ("1" o "0")
        filtros.append(f"dim_cliente.activo = {int(activo)}")

    where_clause = " WHERE " + " AND ".join(filtros) if filtros else ""

    # Consultas con filtros
    ingresos_por_tienda = get_data_from_db(f"""
        SELECT dim_tienda.ciudad AS tienda, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_tienda ON fact_alquileres.tienda_id = dim_tienda.tienda_id
        JOIN dim_pelicula ON fact_alquileres.pelicula_id = dim_pelicula.pelicula_id
        JOIN dim_fecha ON fact_alquileres.fecha_alquiler_id = dim_fecha.fecha_id
        JOIN dim_cliente ON fact_alquileres.cliente_id = dim_cliente.cliente_id
        {where_clause}
        GROUP BY dim_tienda.ciudad
    """)

    ingresos_por_categoria = get_data_from_db(f"""
        SELECT dim_pelicula.categoria AS categoria, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_pelicula ON fact_alquileres.pelicula_id = dim_pelicula.pelicula_id
        JOIN dim_fecha ON fact_alquileres.fecha_alquiler_id = dim_fecha.fecha_id
        JOIN dim_cliente ON fact_alquileres.cliente_id = dim_cliente.cliente_id
        {where_clause}
        GROUP BY dim_pelicula.categoria
    """)

    ingresos_por_anio = get_data_from_db(f"""
        SELECT dim_fecha.anio AS anio, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_fecha ON fact_alquileres.fecha_alquiler_id = dim_fecha.fecha_id
        JOIN dim_pelicula ON fact_alquileres.pelicula_id = dim_pelicula.pelicula_id
        JOIN dim_cliente ON fact_alquileres.cliente_id = dim_cliente.cliente_id
        {where_clause}
        GROUP BY dim_fecha.anio
        ORDER BY dim_fecha.anio
    """)

    top_clientes = get_data_from_db(f"""
        SELECT CONCAT(dim_cliente.nombre, ' ', dim_cliente.apellido) AS cliente, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_cliente ON fact_alquileres.cliente_id = dim_cliente.cliente_id
        JOIN dim_fecha ON fact_alquileres.fecha_alquiler_id = dim_fecha.fecha_id
        JOIN dim_pelicula ON fact_alquileres.pelicula_id = dim_pelicula.pelicula_id
        {where_clause}
        GROUP BY dim_cliente.cliente_id
        ORDER BY ingresos DESC
        LIMIT 5
    """)

    ingresos_por_pais = get_data_from_db(f"""
        SELECT dim_cliente.pais AS pais, SUM(fact_alquileres.monto) AS ingresos
        FROM fact_alquileres
        JOIN dim_cliente ON fact_alquileres.cliente_id = dim_cliente.cliente_id
        JOIN dim_fecha ON fact_alquileres.fecha_alquiler_id = dim_fecha.fecha_id
        JOIN dim_pelicula ON fact_alquileres.pelicula_id = dim_pelicula.pelicula_id
        {where_clause}
        GROUP BY dim_cliente.pais
        ORDER BY ingresos DESC
    """)

    # Retornar todos los datos filtrados
    return jsonify({
        "ingresos_por_tienda": ingresos_por_tienda,
        "ingresos_por_categoria": ingresos_por_categoria,
        "ingresos_por_anio": ingresos_por_anio,
        "top_clientes": top_clientes,
        "ingresos_por_pais": ingresos_por_pais
    })


if __name__ == "__main__":
    app.run(debug=True)
