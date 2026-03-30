#!/bin/bash
# ============================================================
# Script de configuración de MySQL para Pipeline ETL SIVIGILA
# ============================================================
# Este script:
#   1. Verifica que MySQL esté instalado y corriendo
#   2. Crea la base de datos sivigila_tolima
#   3. Crea un usuario dedicado para el pipeline
#   4. Actualiza el archivo .env con la configuración local
#
# Uso: bash setup_mysql.sh
# ============================================================

set -e

echo "============================================================"
echo "  CONFIGURACIÓN DE MYSQL - ETL SIVIGILA"
echo "============================================================"
echo ""

# ─── Colores para output ─────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # Sin color

# ─── PASO 1: Verificar si MySQL está instalado ──────────────
echo "1. Verificando instalación de MySQL..."

if command -v mysql &> /dev/null; then
    MYSQL_VERSION=$(mysql --version)
    echo -e "   ${GREEN}✓ MySQL encontrado:${NC} $MYSQL_VERSION"
else
    echo -e "   ${RED}✗ MySQL no está instalado.${NC}"
    echo ""
    echo "   Para instalar MySQL en macOS con Homebrew:"
    echo ""
    echo "   # Si no tienes Homebrew, instálalo primero:"
    echo '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo ""
    echo "   # Luego instala MySQL:"
    echo "   brew install mysql"
    echo ""
    echo "   # Inicia el servicio:"
    echo "   brew services start mysql"
    echo ""
    echo "   # Ejecuta la configuración de seguridad (opcional pero recomendado):"
    echo "   mysql_secure_installation"
    echo ""
    echo "   Después de instalar, ejecuta este script de nuevo."
    exit 1
fi

# ─── PASO 2: Verificar si MySQL está corriendo ──────────────
echo ""
echo "2. Verificando si el servicio MySQL está activo..."

if mysqladmin ping &> /dev/null 2>&1; then
    echo -e "   ${GREEN}✓ MySQL está corriendo.${NC}"
elif mysqladmin ping -u root &> /dev/null 2>&1; then
    echo -e "   ${GREEN}✓ MySQL está corriendo (requiere usuario root).${NC}"
else
    echo -e "   ${YELLOW}! MySQL no responde. Intentando iniciar...${NC}"
    if command -v brew &> /dev/null; then
        brew services start mysql
        sleep 3
        if mysqladmin ping &> /dev/null 2>&1; then
            echo -e "   ${GREEN}✓ MySQL iniciado correctamente.${NC}"
        else
            echo -e "   ${RED}✗ No se pudo iniciar MySQL.${NC}"
            echo "   Intenta manualmente: brew services start mysql"
            exit 1
        fi
    else
        echo -e "   ${RED}✗ No se pudo iniciar MySQL automáticamente.${NC}"
        echo "   Intenta manualmente: brew services start mysql"
        exit 1
    fi
fi

# ─── PASO 3: Solicitar contraseña de root ────────────────────
echo ""
echo "3. Configurando base de datos y usuario..."
echo ""

# Intentar sin contraseña primero (instalación fresca de Homebrew)
if mysql -u root -e "SELECT 1" &> /dev/null 2>&1; then
    ROOT_PASS=""
    echo -e "   ${GREEN}✓ Acceso root sin contraseña (instalación fresca).${NC}"
else
    echo -n "   Ingresa la contraseña de root de MySQL: "
    read -s ROOT_PASS
    echo ""

    if mysql -u root -p"$ROOT_PASS" -e "SELECT 1" &> /dev/null 2>&1; then
        echo -e "   ${GREEN}✓ Contraseña correcta.${NC}"
    else
        echo -e "   ${RED}✗ Contraseña incorrecta.${NC}"
        exit 1
    fi
fi

# ─── PASO 4: Crear base de datos ────────────────────────────
echo ""
echo "4. Creando base de datos 'sivigila_tolima'..."

MYSQL_CMD="mysql -u root"
if [ -n "$ROOT_PASS" ]; then
    MYSQL_CMD="mysql -u root -p$ROOT_PASS"
fi

$MYSQL_CMD -e "
    CREATE DATABASE IF NOT EXISTS sivigila_tolima
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
"
echo -e "   ${GREEN}✓ Base de datos 'sivigila_tolima' creada/verificada.${NC}"

# ─── PASO 5: Crear usuario dedicado ─────────────────────────
echo ""
echo "5. Creando usuario 'etl_sivigila'..."

ETL_PASSWORD="Sivigila2026ETL"

$MYSQL_CMD -e "
    CREATE USER IF NOT EXISTS 'etl_sivigila'@'localhost' IDENTIFIED BY '$ETL_PASSWORD';
    GRANT ALL PRIVILEGES ON sivigila_tolima.* TO 'etl_sivigila'@'localhost';
    FLUSH PRIVILEGES;
"
echo -e "   ${GREEN}✓ Usuario 'etl_sivigila' creado con permisos sobre sivigila_tolima.${NC}"

# ─── PASO 6: Actualizar .env ────────────────────────────────
echo ""
echo "6. Actualizando archivo .env..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    # Crear backup
    cp "$ENV_FILE" "$ENV_FILE.backup"
    echo "   Backup creado: .env.backup"
fi

cat > "$ENV_FILE" << 'ENVEOF'
# ============================================================
# Pipeline ETL SIVIGILA - Variables de Entorno
# ============================================================

# --- Ruta a los datos crudos ---
# Los archivos BD-*.xlsx estan en data/raw/ dentro del proyecto.
# Si no se define, el pipeline busca automaticamente en data/raw/
# Solo descomenta y cambia si tus archivos estan en otra ubicacion:
# RUTA_DATOS_CRUDOS=/Users/andresgomez/Documents/GDT/GDT 2025/FED/FED SIVIGILA

# --- Configuracion de MySQL (local) ---
DB_HOST=localhost
DB_PORT=3306
DB_USER=etl_sivigila
DB_PASSWORD=Sivigila2026ETL
DB_NAME=sivigila_tolima
ENVEOF

echo -e "   ${GREEN}✓ Archivo .env actualizado con configuración local.${NC}"

# ─── PASO 7: Verificar conexión ─────────────────────────────
echo ""
echo "7. Verificando conexión con el usuario del pipeline..."

if mysql -u etl_sivigila -p"$ETL_PASSWORD" -e "USE sivigila_tolima; SELECT 'Conexión exitosa' AS estado;" 2>/dev/null; then
    echo -e "   ${GREEN}✓ Conexión verificada correctamente.${NC}"
else
    echo -e "   ${YELLOW}! No se pudo verificar la conexión, pero la configuración se completó.${NC}"
fi

# ─── RESUMEN ─────────────────────────────────────────────────
echo ""
echo "============================================================"
echo -e "  ${GREEN}CONFIGURACIÓN COMPLETADA${NC}"
echo "============================================================"
echo ""
echo "  Base de datos:  sivigila_tolima"
echo "  Usuario:        etl_sivigila"
echo "  Contraseña:     $ETL_PASSWORD"
echo "  Host:           localhost:3306"
echo ""
echo "  Para ejecutar el pipeline:"
echo "    cd src"
echo "    python pipeline.py"
echo ""
echo "  Para verificar las tablas creadas después del pipeline:"
echo "    mysql -u etl_sivigila -p'$ETL_PASSWORD' sivigila_tolima -e 'SHOW TABLES;'"
echo ""
echo "============================================================"
