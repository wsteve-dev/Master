import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
import os

# ============================================================
# Configurações do repositório GitHub
# ============================================================
REPO_URL = "https://github.com/wsteve-dev/Master.git"
REPO_BRANCH = "main"

# Pasta local onde o repositório será clonado/atualizado
PASTA_REPO_LOCAL = r"C:\Users\Usuario\Desktop\GitHub\Master"

# Subpasta dentro do repositório onde ficam os scripts
SUBPASTA_SCRIPTS = os.path.join("Mastellini", "Renomeação_Comp")

# Caminho final usado pelo restante do programa
PASTA_BASE = os.path.join(PASTA_REPO_LOCAL, SUBPASTA_SCRIPTS)

RENOMEAR_PDFS = os.path.join(PASTA_BASE, "renomear_pdfs.py")
REMOVER_PONTOS_VIRGULAS = os.path.join(PASTA_BASE, "Remover_Pontos_Virgulas.py")
RENOMEAR_CRBM = os.path.join(PASTA_BASE, "Renomear_CRBM.py")
RENOMEAR_MVF = os.path.join(PASTA_BASE, "Renomear_MVF.py")


def git_disponivel():
    """Verifica se o comando git está disponível no sistema."""
    try:
        subprocess.run(
            ["git", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def atualizar_repositorio():
    """
    Clona o repositório se ele ainda não existir localmente,
    ou faz um pull para atualizar a versão local.
    Retorna True se tudo ocorreu bem, False caso contrário.
    """
    if not git_disponivel():
        messagebox.showerror(
            "Git não encontrado",
            "O Git não foi encontrado no sistema.\n"
            "Instale o Git (https://git-scm.com/) e tente novamente."
        )
        return False

    try:
        pasta_git = os.path.join(PASTA_REPO_LOCAL, ".git")

        if os.path.isdir(pasta_git):
            # Repositório já existe -> atualizar
            status_label.config(text="Atualizando repositório...")
            janela.update_idletasks()

            resultado = subprocess.run(
                ["git", "-C", PASTA_REPO_LOCAL, "pull", "origin", REPO_BRANCH],
                capture_output=True,
                text=True
            )

            if resultado.returncode != 0:
                messagebox.showerror(
                    "Erro ao atualizar repositório",
                    resultado.stderr or "Erro desconhecido ao executar git pull."
                )
                return False

        else:
            # Repositório ainda não existe -> clonar
            os.makedirs(os.path.dirname(PASTA_REPO_LOCAL), exist_ok=True)

            status_label.config(text="Clonando repositório...")
            janela.update_idletasks()

            resultado = subprocess.run(
                ["git", "clone", "-b", REPO_BRANCH, REPO_URL, PASTA_REPO_LOCAL],
                capture_output=True,
                text=True
            )

            if resultado.returncode != 0:
                messagebox.showerror(
                    "Erro ao clonar repositório",
                    resultado.stderr or "Erro desconhecido ao executar git clone."
                )
                return False

        status_label.config(text="Repositório atualizado ✅")
        return True

    except Exception as e:
        messagebox.showerror("Erro ao atualizar repositório", str(e))
        return False


def rodar_script(caminho, nome_script, precisa_console=False):
    """Atualiza o repositório e executa o script em um processo separado."""
    if not atualizar_repositorio():
        return

    if not os.path.exists(caminho):
        messagebox.showerror("Erro", f"Arquivo não encontrado:\n{caminho}")
        return

    try:
        if precisa_console:
            # Abre em um console novo (necessário para scripts com input())
            subprocess.Popen(
                [sys.executable, caminho],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            subprocess.Popen([sys.executable, caminho])
        status_label.config(text=f"'{nome_script}' iniciado ✅")
    except Exception as e:
        messagebox.showerror("Erro ao executar", str(e))


# ---------------- Interface ----------------
janela = tk.Tk()
janela.title("Painel de Renomeação de PDFs")
janela.geometry("320x300")
janela.resizable(False, False)

titulo = tk.Label(janela, text="Escolha a automação", font=("Segoe UI", 13, "bold"))
titulo.pack(pady=15)

btn1 = tk.Button(
    janela, text="Renomear PDFs (Bancos)", width=28, height=2,
    command=lambda: rodar_script(RENOMEAR_PDFS, "Renomear PDFs (Bancos)", precisa_console=True)
)
btn1.pack(pady=5)

btn2 = tk.Button(
    janela, text="Remover Pontos e Vírgulas", width=28, height=2,
    command=lambda: rodar_script(REMOVER_PONTOS_VIRGULAS, "Remover Pontos e Vírgulas", precisa_console=True)
)
btn2.pack(pady=5)

btn3 = tk.Button(
    janela, text="Renomear CRBM", width=28, height=2,
    command=lambda: rodar_script(RENOMEAR_CRBM, "Renomear CRBM", precisa_console=True)
)
btn3.pack(pady=5)

btn4 = tk.Button(
    janela, text="Renomear MVF", width=28, height=2,
    command=lambda: rodar_script(RENOMEAR_MVF, "Renomear MVF", precisa_console=True)
)
btn4.pack(pady=5)

status_label = tk.Label(janela, text="", fg="green")
status_label.pack(pady=10)

janela.mainloop()