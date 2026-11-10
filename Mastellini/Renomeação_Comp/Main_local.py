import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
import os

# ============================================================
# Configurações (versão local, sem GitHub)
# ============================================================
# Pasta onde os scripts já estão salvos no computador
PASTA_REPO_LOCAL = r"C:\Users\Usuario\Desktop\GitHub\Master"

# Subpasta dentro da pasta local onde ficam os scripts
SUBPASTA_SCRIPTS = os.path.join("Mastellini", "Renomeação_Comp")

# Caminho final usado pelo restante do programa
PASTA_BASE = os.path.join(PASTA_REPO_LOCAL, SUBPASTA_SCRIPTS)

RENOMEAR_PDFS = os.path.join(PASTA_BASE, "renomear_pdfs.py")
REMOVER_PONTOS_VIRGULAS = os.path.join(PASTA_BASE, "Remover_Pontos_Virgulas.py")
RENOMEAR_CRBM = os.path.join(PASTA_BASE, "Renomear_CRBM.py")
RENOMEAR_MVF = os.path.join(PASTA_BASE, "Renomear_MVF.py")


def rodar_script(caminho, nome_script, precisa_console=False):
    """Executa o script local em um processo separado, sem consultar o GitHub."""
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
janela.title("Painel de Renomeação de PDFs (Local)")
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

btn5 = tk.Button(
    janela, text="Taubaté", width=28, height=2,
    command=lambda: rodar_script(Lista_Taubate, "Taubaté", precisa_console=True)
)
btn5.pack(pady=5)

status_label = tk.Label(janela, text="", fg="green")
status_label.pack(pady=10)

janela.mainloop()