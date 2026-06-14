import sys
import os

def patch_ibom(file_path):
    if not os.path.exists(file_path):
        print(f"❌ Error: No se encontró el archivo '{file_path}'.")
        return

    try:
        # Abrimos el archivo en modo lectura usando utf-8
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # --- CAMBIO 1: El operador ?? ---
        viejo_codigo_1 = 'var name = node.firstChild.nodeValue ?? "";'
        nuevo_codigo_1 = 'var name = node.firstChild.nodeValue || "";'
        
        # --- CAMBIO 2: La función .flat() ---
        viejo_codigo_2 = "var allList = getBomListByLayer('FB').flat();"
        nuevo_codigo_2 = "var allList = getBomListByLayer('FB').reduce(function(acc, val) { return acc.concat(val); }, []);"

        # Verificamos si los cambios son necesarios
        cambios_realizados = False
        if viejo_codigo_1 in html_content:
            html_content = html_content.replace(viejo_codigo_1, nuevo_codigo_1)
            cambios_realizados = True
            
        if viejo_codigo_2 in html_content:
            html_content = html_content.replace(viejo_codigo_2, nuevo_codigo_2)
            cambios_realizados = True

        if cambios_realizados:
            # Guardamos el archivo sobrescribiendo el original
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"✅ ¡Éxito! El archivo '{file_path}' ha sido modificado y ahora es compatible con Safari antiguo.")
        else:
            print(f"⚠️ No se encontraron las líneas a cambiar en '{file_path}'. ¿Quizás ya estaba parcheado?")

    except Exception as e:
        print(f"❌ Ocurrió un error al procesar el archivo: {e}")

if __name__ == "__main__":
    # Si ejecutas el script arrastrando un archivo o pasando el nombre por terminal
    if len(sys.argv) > 1:
        archivo = sys.argv[1]
    else:
        # Si lo ejecutas sin parámetros, usa el nombre de tu archivo por defecto
        archivo = "poweramp_20260604.html"
        
    patch_ibom(archivo)
