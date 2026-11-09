#!/bin/bash
# Script rápido de pruebas para la API de Tareas

URL="http://127.0.0.1:5000/api/tareas"
PASS=0
FAIL=0

check() {
  local desc="$1"
  local expected="$2"
  local actual="$3"
  if [ "$expected" == "$actual" ]; then
    echo "✅ $desc"
    PASS=$((PASS+1))
  else
    echo "❌ $desc (esperado: $expected, obtenido: $actual)"
    FAIL=$((FAIL+1))
  fi
}

echo "--- Limpiando base de datos vía API ---"
# Obtener todas las tareas y borrarlas una a una
TAREAS=$(curl -s -X GET $URL | python3 -c "import sys, json; print(' '.join(str(t['id']) for t in json.load(sys.stdin)))")
for ID in $TAREAS; do
  curl -s -X DELETE $URL/$ID > /dev/null
done

echo "--- Iniciando pruebas ---"

# R1, R2: Crear tarea válida
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST $URL -H "Content-Type: application/json" -d '{"titulo":"  Prueba de título  ", "prioridad":"alta", "fecha_limite":"2026-12-01"}')
check "R1: Crear tarea (201)" "201" "$STATUS"

# R2: Título corto
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST $URL -H "Content-Type: application/json" -d '{"titulo":"ab"}')
check "R2: Título corto (400)" "400" "$STATUS"

# R4: Prioridad inválida
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST $URL -H "Content-Type: application/json" -d '{"titulo":"Prueba", "prioridad":"Alta"}')
check "R4: Prioridad inválida (400)" "400" "$STATUS"

# R5: Fecha en el pasado
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST $URL -H "Content-Type: application/json" -d '{"titulo":"Prueba", "fecha_limite":"2020-01-01"}')
check "R5: Fecha pasada (400)" "400" "$STATUS"

# R6: Listar tareas
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET $URL)
check "R6: Listar tareas (200)" "200" "$STATUS"

# R8: Consultar tarea existente e inexistente
# (La tarea 1 es la que se creó en R1, pero como la base de datos puede no ser la misma
# si se ha ejecutado antes, creamos una nueva para asegurar el ID).
curl -s -X POST $URL -H "Content-Type: application/json" -d '{"titulo":"Consulta"}' > /dev/null
ID_CONSULTA=$(curl -s -X GET $URL | python3 -c "import sys, json; print(json.load(sys.stdin)[-1]['id'])")

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET $URL/$ID_CONSULTA)
check "R8: Consultar tarea existente (200)" "200" "$STATUS"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET $URL/999)
check "R8: Consultar tarea inexistente (404)" "404" "$STATUS"

# R9: Editar tarea (404 -> 409 -> 400)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PUT $URL/999 -H "Content-Type: application/json" -d '{"titulo":"Edit"}')
check "R9: Editar tarea inexistente (404)" "404" "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PUT $URL/$ID_CONSULTA -H "Content-Type: application/json" -d '{"titulo":"ab"}')
check "R9: Editar tarea inválida (400)" "400" "$STATUS"

# R10: Completar tarea
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST $URL/$ID_CONSULTA/completar)
check "R10: Completar tarea (200)" "200" "$STATUS"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST $URL/$ID_CONSULTA/completar)
check "R10: Completar tarea ya completada (409)" "409" "$STATUS"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PUT $URL/$ID_CONSULTA -H "Content-Type: application/json" -d '{"titulo":"Edit"}')
check "R9: Editar tarea completada (409)" "409" "$STATUS"

# R11: Eliminar tarea
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE $URL/$ID_CONSULTA)
check "R11: Eliminar tarea (204)" "204" "$STATUS"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET $URL/$ID_CONSULTA)
check "R11: Consultar tarea eliminada (404)" "404" "$STATUS"

# R12: Cuerpo no JSON
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST $URL -H "Content-Type: application/json" -d 'no-es-json')
check "R12: Cuerpo no JSON (400)" "400" "$STATUS"

echo "-------------------------"
echo "Pruebas superadas: $PASS"
echo "Pruebas fallidas: $FAIL"

if [ $FAIL -eq 0 ]; then
  echo " Todo listo para entregar."
else
  echo " Revisa los errores antes de entregar."
fi