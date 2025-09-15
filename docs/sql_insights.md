# Consultas SQL detectadas

_Proyecto_: CREATE_FLOW_FROM_CODE_TOOLS

## Índice

1. [Archivo: "carrito.py"](#$carritopy)
2. [Archivo: "historial.py"](#$historialpy)
3. [Archivo: "tomar_pedido.py"](#$tomar_pedidopy)

---

------------------------------------------------------------------------
## Archivo: "carrito.py"
<a id="carritopy"></a>

**Línea 193**

```sql
            SELECT sku, reglas_de_lista_de_precios_producto, reglas_de_lista_de_precios_precio_fijo
            FROM pricelist
            WHERE region = ?
              AND (sku LIKE ? OR reglas_de_lista_de_precios_producto LIKE ?)
            ORDER BY sku LIMIT 50
        
```

- Tipo: **Lectura (SELECT)**
- Tabla(s): **pricelist**
- Campos: sku, reglas_de_lista_de_precios_producto, reglas_de_lista_de_precios_precio_fijo
- Filtro: `region = ? AND (sku LIKE ? OR reglas_de_lista_de_precios_producto LIKE ?)`
- Ordena resultados con **ORDER BY**.
- Limita cantidad de filas con **LIMIT**.

---

**Línea 278**

```sql
            INSERT INTO order_drafts(user, cliente_rowid, payload_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user, cliente_rowid)
            DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at
        
```

- Tipo: **Escritura (INSERT)**
- Tabla(s): **order_drafts**

---

**Línea 288**

```sql
SELECT payload_json FROM order_drafts WHERE user=? AND cliente_rowid=?
```

- Tipo: **Lectura (SELECT)**
- Tabla(s): **order_drafts**
- Campos: payload_json
- Filtro: `user=? AND cliente_rowid=?`

---

**Línea 312**

```sql
SELECT nombre_real FROM usuarios WHERE username_ferro=? LIMIT 1
```

- Tipo: **Lectura (SELECT)**
- Tabla(s): **usuarios**
- Campos: nombre_real
- Filtro: `username_ferro=?`
- Limita cantidad de filas con **LIMIT**.

---

**Línea 332**

```sql
INSERT INTO orders(
```

- Tipo: **Escritura (INSERT)**
- Tabla(s): **orders**

---

**Línea 334**

```sql
INSERT INTO orders(?) VALUES(?)
```

- Tipo: **Escritura (INSERT)**
- Tabla(s): **orders**

---

**Línea 339**

```sql
                INSERT INTO order_items(order_id, sku, product, unit_price, qty, total)
                VALUES(?,?,?,?,?,?)
            
```

- Tipo: **Escritura (INSERT)**
- Tabla(s): **order_items**

---

**Línea 344**

```sql
SELECT marca, categoria_de_producto FROM productos WHERE sku=? LIMIT 1
```

- Tipo: **Lectura (SELECT)**
- Tabla(s): **productos**
- Campos: marca, categoria_de_producto
- Filtro: `sku=?`
- Limita cantidad de filas con **LIMIT**.

---

**Línea 349**

```sql
                INSERT INTO detalle_productos_orden(
                    order_no, region, sku, product, marca, categoria, unit_price, qty, total
                ) VALUES(?,?,?,?,?,?,?,?,?)
            
```

- Tipo: **Escritura (INSERT)**
- Tabla(s): **detalle_productos_orden**

---

**Línea 357**

```sql
DELETE FROM order_drafts WHERE user=?
```

- Tipo: **Eliminación (DELETE)**
- Tabla(s): **order_drafts**
- Filtro: `user=?`

------------------------------------------------------------------------
## Archivo: "historial.py"
<a id="historialpy"></a>

**Línea 156**

```sql
                    SELECT o.order_no, o.cliente_display, o.total, o.created_at
                    FROM orders o
                    WHERE o.user=?
                    ORDER BY o.id DESC
                    LIMIT 200
                
```

- Tipo: **Lectura (SELECT)**
- Tabla(s): **orders**
- Campos: o.order_no, o.cliente_display, o.total, o.created_at
- Filtro: `o.user=?`
- Ordena resultados con **ORDER BY**.
- Limita cantidad de filas con **LIMIT**.

---

**Línea 164**

```sql
                    SELECT o.order_no, o.cliente_display, o.total, o.created_at
                    FROM orders o
                    LEFT JOIN clientes c ON c.rowid = o.cliente_rowid
                    WHERE o.user=?
                      AND (
                           o.order_no LIKE ? COLLATE NOCASE
                        OR o.cliente_display LIKE ? COLLATE NOCASE
                        OR c.nombre_fantasia LIKE ? COLLATE NOCASE
                        OR c.nombre_completo LIKE ? COLLATE NOCASE
                        OR c.numero_identificacion_fiscal LIKE ? COLLATE NOCASE
                      )
                    ORDER BY o.id DESC
                    LIMIT 200
                
```

- Tipo: **Lectura (SELECT)**
- Tabla(s): **orders, clientes**
- Campos: o.order_no, o.cliente_display, o.total, o.created_at
- Filtro: `o.user=? AND ( o.order_no LIKE ? COLLATE NOCASE OR o.cliente_display LIKE ? COLLATE NOCASE OR c.nombre_fantasia LIKE ? COLLATE NOCASE OR c.nombre_completo LIKE ? COLLATE NOCASE OR c.numero_identificacion_fiscal LIKE ? COLLATE NOCASE )`
- Ordena resultados con **ORDER BY**.
- Limita cantidad de filas con **LIMIT**.

------------------------------------------------------------------------
## Archivo: "tomar_pedido.py"
<a id="tomar_pedidopy"></a>

**Línea 94**

```sql
        SELECT
            
```

- Tipo: **Lectura (SELECT)**

---

**Línea 106**

```sql
        SELECT
            ? AS display,
            ?,
            rowid AS cliente_id
        FROM clientes
        WHERE ?
        ORDER BY display
        LIMIT ?
        
```

- Tipo: **Lectura (SELECT)**
- Tabla(s): **clientes**
- Campos: ? AS display, ?, rowid AS cliente_id
- Filtro: `?`
- Ordena resultados con **ORDER BY**.
- Limita cantidad de filas con **LIMIT**.

---

**Línea 292**

```sql
                SELECT cliente_rowid, payload_json
                FROM order_drafts
                WHERE user=?
                ORDER BY id DESC
                LIMIT 1
            
```

- Tipo: **Lectura (SELECT)**
- Tabla(s): **order_drafts**
- Campos: cliente_rowid, payload_json
- Filtro: `user=?`
- Ordena resultados con **ORDER BY**.
- Limita cantidad de filas con **LIMIT**.
