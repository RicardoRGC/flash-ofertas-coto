import subprocess
import os

def run_cmd(cmd, cwd=None):
    """
    Ejecuta un comando en shell y devuelve (stdout, stderr, exit_code).
    """
    proceso = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,           # en Windows suele ser necesario para que reconozca git.exe
        universal_newlines=True
    )
    out, err = proceso.communicate()
    return out.strip(), err.strip(), proceso.returncode

def auto_push(repo_path, commit_message="Auto: cambios detectados", branch="main"):
    """
    1. Hace git add -A
    2. Hace git diff-index --quiet HEAD -- para ver si hay cambios (si no, sale)
    3. Si hay cambios, hace git commit -m commit_message
    4. Hace git push origin branch
    """
    # 1) Verificar que repo_path exista y sea carpeta
    if not os.path.isdir(repo_path):
        raise FileNotFoundError(f"La ruta {repo_path} no existe o no es un directorio.")
    
    # 2) git add -A
    out, err, code = run_cmd("git add -A", cwd=repo_path)
    if code != 0:
        print(f"[ERROR] git add falló:\n{err}")
        return False
    
    # 3) Verificar si hay algo para commitear
    #    git diff-index --quiet HEAD --  -> exit_code=0 si NO hay cambios; 1 si hay cambios
    _, _, diff_code = run_cmd("git diff-index --quiet HEAD --", cwd=repo_path)
    if diff_code == 0:
        print("No hay cambios para commitear.")
        return True  # ya está todo actualizado
    
    # 4) git commit -m "mensaje"
    out, err, code = run_cmd(f'git commit -m "{commit_message}"', cwd=repo_path)
    if code != 0:
        print(f"[ERROR] git commit falló:\n{err}")
        return False
    print(out)
    
    # 5) git push origin <branch>
    out, err, code = run_cmd(f"git push origin {branch}", cwd=repo_path)
    if code != 0:
        print(f"[ERROR] git push falló:\n{err}")
        return False
    print(out)
    return True

if __name__ == "__main__":
    # Si ejecutás auto_push.py directamente, podés probarlo así:
    repo_folder = r"C:\Users\PC\Desktop\asistente jarvis\proyectoCoto\flash-ofertas-coto"
    if auto_push(repo_folder, commit_message="Auto: cambios desde Python"):
        print("✅ Repo actualizado correctamente.")
    else:
        print("❌ Hubo un problema al actualizar el repo.")
