#!/usr/bin/env python3
"""
Processador de PDFs bancários.

Etapa 1: Pergunta o banco.
Etapa 2: Verifica páginas — se > 1, separa em PDFs individuais.
Etapa 3: Identifica o tipo de pagamento e renomeia DATA BENEFICIARIO VALOR.
"""

import os
import re
import sys
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter


# ---------------------------------------------------------------------------
# Mapeamento de convênios BB DDA
# ---------------------------------------------------------------------------
CONVENIOS_BB = {
    "011015 VIVO FIXO NACIONAL 13 DIG": "VIVO FIXO NACIONAL",
    # adicione outros aqui conforme necessário
}


# ---------------------------------------------------------------------------
# Estatísticas de execução (resumo final)
# ---------------------------------------------------------------------------
ESTATISTICAS = {
    "renomeados": 0,
    "campos_nao_encontrados": 0,
    "nao_reconhecidos": 0,
    "erros": 0,
}


def avisar_campos_faltando(tipo: str):
    """Imprime aviso de campo(s) não encontrado(s) e contabiliza no resumo."""
    print(f"   [AVISO] {tipo} – campo(s) não encontrado(s). Arquivo não renomeado.")
    ESTATISTICAS["campos_nao_encontrados"] += 1


# ---------------------------------------------------------------------------
# Helpers gerais
# ---------------------------------------------------------------------------

def extrair_texto(caminho_pdf: Path) -> str:
    """Extrai todo o texto do PDF com pdfplumber."""
    partes = []
    with pdfplumber.open(str(caminho_pdf)) as pdf:
        for pagina in pdf.pages:
            partes.append(pagina.extract_text() or "")
    return "\n".join(partes)


def limpar_data(valor: str) -> str:
    """
    Remove tudo que não seja dígito e retorna apenas os 8 primeiros dígitos
    (DDMMAAAA).  Exemplos:
      '15/06/2026'              -> '15062026'
      '15/06/2026 - 14:30:55'  -> '15062026'
      '15.06.2026'              -> '15062026'
    """
    return re.sub(r"\D", "", valor)[:8]


def limpar_valor_monetario(valor: str) -> str:
    """
    Remove prefixos como 'R$' e espaços extras, mantendo o número formatado.
    Ex: 'R$ 1.200,00' -> '1.200,00'
    """
    valor = re.sub(r"R\$\s*", "", valor).strip()
    return valor


def limpar_nome_destinatario(valor: str) -> str:
    """
    Remove CPF/CNPJ que possam aparecer junto ao nome, seja antes ou depois.
    Ex: 'Douglas Gabriel 10845579401' -> 'Douglas Gabriel'
    Ex: '61 075 577 EDUARDO ARAUJO DA CONCEICAO' -> 'EDUARDO ARAUJO DA CONCEICAO'
    Ex: '28.192.898 ANDERSON ALEXANDRE SIMAO DE AZEVEDO SANTOS' -> 'ANDERSON ALEXANDRE SIMAO DE AZEVEDO SANTOS'
    Estratégia: remove sequências de 11 ou 14 dígitos (com ou sem máscara) e
    qualquer prefixo numérico (raiz de CNPJ/matrícula) antes do nome.
    """
    # Prefixo numérico no início (ex.: raiz de CNPJ "61 075 577 " ou "28.192.898 ")
    valor = re.sub(r"^[\d\.\/\-\s]+(?=[A-Za-zÀ-ÿ])", "", valor)
    valor = re.sub(r"\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}", "", valor)  # CPF
    valor = re.sub(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", "", valor)  # CNPJ
    valor = re.sub(r"\b\d{11}\b", "", valor)  # CPF sem formatação
    valor = re.sub(r"\b\d{14}\b", "", valor)  # CNPJ sem formatação
    return valor.strip()


def extrair_campo_linha(texto: str, rotulo: str) -> str | None:
    """
    Encontra a linha que contém o rótulo e retorna o que vem depois dele.
    Busca case-insensitive.
    """
    rotulo_lower = rotulo.lower()
    for linha in texto.splitlines():
        linha_strip = linha.strip()
        idx = linha_strip.lower().find(rotulo_lower)
        if idx != -1:
            valor = linha_strip[idx + len(rotulo):].strip()
            if valor:
                return valor
    return None


def extrair_linha_seguinte(texto: str, rotulo: str) -> str | None:
    """
    Encontra a linha cujo conteúdo é EXATAMENTE o rótulo (ignorando espaços
    nas pontas e maiúsculas/minúsculas) e retorna a próxima linha não-vazia.
    Útil para layouts onde o valor não fica na mesma linha do rótulo.
    Ex.:
      BENEFICIARIO:
      DIAGNOSTICOS DA AMERICA S.A .
    """
    rotulo_lower = rotulo.strip().lower()
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if linha.strip().lower() == rotulo_lower:
            for prox in linhas[i + 1:]:
                if prox.strip():
                    return prox.strip()
            return None
    return None


def sanitizar_nome(nome: str) -> str:
    """Remove caracteres inválidos para nome de arquivo."""
    nome = re.sub(r'[\\/*?:"<>|]', "", nome)
    nome = re.sub(r"\s+\.", ".", nome)  # corrige "S.A ." -> "S.A." (artefato comum em PDFs)
    return re.sub(r"\s+", " ", nome).strip()


def gerar_caminho_disponivel(pasta: Path, nome_base: str, ext: str = ".pdf") -> Path:
    """Retorna um caminho que não exista ainda; adiciona (1), (2)... se necessário."""
    candidato = pasta / f"{nome_base}{ext}"
    if not candidato.exists():
        return candidato
    i = 1
    while True:
        candidato = pasta / f"{nome_base} ({i}){ext}"
        if not candidato.exists():
            return candidato
        i += 1


def montar_nome(data: str, beneficiario: str, valor: str) -> str:
    partes = [p for p in [data, beneficiario, valor] if p]
    return sanitizar_nome(" ".join(partes))


def renomear_pdf(caminho: Path, nome_base: str) -> Path:
    novo = gerar_caminho_disponivel(caminho.parent, nome_base)
    caminho.rename(novo)
    print(f"     ✔ '{caminho.name}' → '{novo.name}'")
    ESTATISTICAS["renomeados"] += 1
    return novo


# ---------------------------------------------------------------------------
# Etapa 1 – Separar páginas
# ---------------------------------------------------------------------------

def separar_paginas(caminho_pdf: Path, pasta_saida: Path) -> list[Path]:
    """
    Se o PDF tiver > 1 página, separa e retorna lista de arquivos gerados.
    Se tiver 1 página, retorna lista com o próprio arquivo.
    """
    leitor = PdfReader(str(caminho_pdf))
    total = len(leitor.pages)

    if total <= 1:
        return [caminho_pdf]

    print(f"   PDF com {total} páginas — separando...")
    gerados = []
    for i, pag in enumerate(leitor.pages, start=1):
        escritor = PdfWriter()
        escritor.add_page(pag)
        nome_pag = f"{caminho_pdf.stem} - pagina {i}"
        destino = gerar_caminho_disponivel(pasta_saida, nome_pag)
        with open(destino, "wb") as f:
            escritor.write(f)
        print(f"     -> Página {i}/{total}: {destino.name}")
        gerados.append(destino)

    return gerados


# ---------------------------------------------------------------------------
# Handlers por banco / tipo
# ---------------------------------------------------------------------------

def handle_bb_dda(texto: str, caminho: Path):
    if "COMPROVANTE DE DEBITO AUTOMATICO" not in texto.upper():
        return False

    convenio_raw = extrair_campo_linha(texto, "CONVENIO:")
    data_raw     = extrair_campo_linha(texto, "DATA DO DEBITO:")
    valor_raw    = extrair_campo_linha(texto, "VALOR DO DEBITO R$")

    if not all([convenio_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB DDA")
        return True

    # Normaliza convênio
    convenio_upper = convenio_raw.upper().strip()
    convenio = CONVENIOS_BB.get(convenio_upper, convenio_raw.strip())

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, convenio, valor))
    return True


def handle_bb_folha(texto: str, caminho: Path):
    if "Visualizador de arquivos retorno" not in texto:
        return False

    favorecido_raw = extrair_campo_linha(texto, "Favorecido:")
    data_raw       = extrair_campo_linha(texto, "Data real pagamento:")
    valor_raw      = extrair_campo_linha(texto, "Valor real pagamento:")

    if not all([favorecido_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB Folha")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, favorecido_raw.strip(), valor))
    return True


def handle_bb_multa_transito(texto: str, caminho: Path):
    """
    Cobre comprovantes SISBB do tipo:
      COMPROVANTE DE PAGAMENTO — Multa de trânsito (DETRAN/SEFAZ)
    Layout tabular:
      TIPO DE PAGAMENTO   VENCIMENTO   VALOR (R$)
      MULTA D.E.R.        20/07/2026   104,12
    Precisa vir ANTES de handle_bb_boleto_convenio na lista de handlers,
    pois ambos compartilham o texto "COMPROVANTE DE PAGAMENTO".
    """
    texto_upper = texto.upper()
    if "MULTA DE TR" not in texto_upper:
        return False

    linha_tabela = re.compile(r"^(.+?)\s+(\d{2}/\d{2}/\d{4})\s+([\d\.]+,\d{2})\s*$")

    tipo_raw = data_raw = valor_raw = None
    for linha in texto.splitlines():
        m = linha_tabela.match(linha.strip())
        if m:
            tipo_raw, data_raw, valor_raw = m.groups()
            break

    # Prefere a data da transação/pagamento, se disponível; senão usa o vencimento da tabela
    data_transacao_raw = extrair_campo_linha(texto, "DATA DA TRANSAÇÃO:")
    if data_transacao_raw:
        data_raw = data_transacao_raw

    if not all([tipo_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB Multa de Trânsito")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, tipo_raw.strip(), valor))
    return True


def handle_bb_licenciamento(texto: str, caminho: Path):
    """
    Cobre comprovantes SISBB do tipo:
      COMPROVANTE DE PAGAMENTO — Licenciamento de veículo (DETRAN/SEFAZ)
    Layout tabular (sem data na linha, apenas o ano de exercício):
      TIPO DE PAGAMENTO   EXERC   VENCIMENTO   VALOR (R$)
      TAXA LICENCIAMENTO  2026                 174,08
      TOTAL                                    174,08
    Precisa vir ANTES de handle_bb_boleto_convenio na lista de handlers,
    pois ambos compartilham o texto "COMPROVANTE DE PAGAMENTO".
    """
    texto_upper = texto.upper()
    if "LICENCIAMENTO DE VEICULO" not in texto_upper and "LICENCIAMENTO DE VEÍCULO" not in texto_upper:
        return False

    linha_tabela = re.compile(r"^(.+?)\s+(\d{4})\s+([\d\.]+,\d{2})\s*$")

    tipo_raw = valor_raw = None
    for linha in texto.splitlines():
        m = linha_tabela.match(linha.strip())
        if m:
            tipo_raw, _exerc, valor_raw = m.groups()
            break

    data_raw = extrair_campo_linha(texto, "DATA DA TRANSAÇÃO:")

    if not all([tipo_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB Licenciamento")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, tipo_raw.strip(), valor))
    return True


def handle_bb_ipva(texto: str, caminho: Path):
    """
    Cobre comprovantes SISBB do tipo:
      COMPROVANTE DE PAGAMENTO — IPVA (DETRAN/SEFAZ)
    Layout tabular (com exercício E vencimento na mesma linha):
      TIPO DE PAGAMENTO   EXERC   VENCIMENTO   VALOR (R$)
      IPVA 5a PARCELA      2026   17/08/2026   1.486,66
    Precisa vir ANTES de handle_bb_boleto_convenio na lista de handlers,
    pois ambos compartilham o texto "COMPROVANTE DE PAGAMENTO".
    """
    texto_upper = texto.upper()
    if "IPVA" not in texto_upper:
        return False

    linha_tabela = re.compile(r"^(.+?)\s+(\d{4})\s+(\d{2}/\d{2}/\d{4})\s+([\d\.]+,\d{2})\s*$")

    tipo_raw = valor_raw = None
    for linha in texto.splitlines():
        m = linha_tabela.match(linha.strip())
        if m:
            tipo_raw, _exerc, _vencimento, valor_raw = m.groups()
            break

    data_raw = extrair_campo_linha(texto, "DATA DA TRANSAÇÃO:")

    if not all([tipo_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB IPVA")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, tipo_raw.strip(), valor))
    return True


def handle_bb_pagamento_titulos(texto: str, caminho: Path):
    """
    Cobre comprovantes BB do tipo:
      COMPROVANTE DE PAGAMENTO DE TITULOS
    Layout diferente: o nome do beneficiário fica na linha SEGUINTE ao
    rótulo "BENEFICIARIO:", não na mesma linha.
      BENEFICIARIO:
      DIAGNOSTICOS DA AMERICA S.A .
      ...
      DATA DO PAGAMENTO 28/08/2026
      VALOR COBRADO 314.976,20
    Precisa vir ANTES de handle_bb_boleto_convenio na lista de handlers,
    pois ambos compartilham o texto "COMPROVANTE DE PAGAMENTO".
    """
    if "COMPROVANTE DE PAGAMENTO DE TITULOS" not in texto.upper():
        return False

    beneficiario_raw = extrair_linha_seguinte(texto, "BENEFICIARIO:")
    data_raw         = extrair_campo_linha(texto, "DATA DO PAGAMENTO ")
    valor_raw        = extrair_campo_linha(texto, "VALOR COBRADO ")

    if not all([beneficiario_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB Pagamento de Títulos")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, beneficiario_raw.strip(), valor))
    return True


def handle_bb_boleto_convenio(texto: str, caminho: Path):
    """
    Cobre comprovantes SISBB do tipo:
      COMPROVANTE DE PAGAMENTO  (boleto / convênio)
    Campos: Convenio / Data do pagamento / Valor Total
    Obs: os rótulos NÃO têm ':' neste modelo.
    """
    texto_upper = texto.upper()
    # Garante que é este modelo e não o Pagamento Eletrônico
    if "COMPROVANTE DE PAGAMENTO" not in texto_upper:
        return False
    if "COMPROVANTE DE PAGAMENTO ELETRONICO" in texto_upper:
        return False

    convenio_raw = extrair_campo_linha(texto, "Convenio ")
    data_raw     = extrair_campo_linha(texto, "Data do pagamento ")
    valor_raw    = extrair_campo_linha(texto, "Valor Total ")

    if not all([convenio_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB Boleto/Convênio")
        return True

    # Convênio: usa mapeamento se existir, senão mantém como veio
    convenio_upper = convenio_raw.upper().strip()
    convenio = CONVENIOS_BB.get(convenio_upper, convenio_raw.strip())

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, convenio, valor))
    return True


def handle_bb_pagamento_eletronico(texto: str, caminho: Path):
    """
    Cobre comprovantes SISBB do tipo:
      COMPROVANTE DE PAGAMENTO ELETRONICO
    Campos: FAVORECIDO / DATA DE PAGAMENTO / VALOR CREDITADO (R$)
    """
    if "COMPROVANTE DE PAGAMENTO ELETRONICO" not in texto.upper():
        return False

    favorecido_raw = extrair_campo_linha(texto, "FAVORECIDO:")
    data_raw       = extrair_campo_linha(texto, "DATA DE PAGAMENTO:")
    valor_raw      = extrair_campo_linha(texto, "VALOR CREDITADO (R$):")

    if not all([favorecido_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB Pagamento Eletrônico")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, favorecido_raw.strip(), valor))
    return True


def handle_bb_pag_salario(texto: str, caminho: Path):
    """
    Cobre comprovantes BB do tipo:
      COMPROVANTE / PAG SALARIO C/CTA
    Campos: BENEFICIARIO / DATA DO PAGAMENTO / VALOR
    """
    if "PAG SALARIO C/CTA" not in texto.upper():
        return False

    beneficiario_raw = extrair_campo_linha(texto, "BENEFICIARIO:")
    data_raw         = extrair_campo_linha(texto, "DATA DO PAGAMENTO:")
    valor_raw        = extrair_campo_linha(texto, "VALOR:")

    if not all([beneficiario_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB Pag Salário")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, beneficiario_raw.strip(), valor))
    return True


def handle_bb_pix(texto: str, caminho: Path):
    """
    Cobre comprovantes BB (SISBB) do tipo:
      Comprovante Pix
    Campos: PAGO PARA / DATA / VALOR
    """
    if "COMPROVANTE PIX" not in texto.upper():
        return False

    beneficiario_raw = extrair_campo_linha(texto, "PAGO PARA:")
    data_raw         = extrair_campo_linha(texto, "DATA:")
    valor_raw        = extrair_campo_linha(texto, "VALOR:")

    if not all([beneficiario_raw, data_raw, valor_raw]):
        avisar_campos_faltando("BB Pix")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, beneficiario_raw.strip(), valor))
    return True


def handle_sicredi_boleto(texto: str, caminho: Path):
    """Cobre tanto 'Boleto' quanto 'Pagar Boletos Eletronicos' (DDA)."""
    texto_upper = texto.upper()
    if "BOLETO" not in texto_upper and "PAGAR BOLETOS" not in texto_upper:
        return False

    beneficiario_raw = extrair_campo_linha(texto, "Razao Social do Beneficiario:")
    if not beneficiario_raw:
        beneficiario_raw = extrair_campo_linha(texto, "Razão Social do Beneficiário:")
    data_raw         = extrair_campo_linha(texto, "Data do Pagamento:")
    if not data_raw:
        data_raw = extrair_campo_linha(texto, "Data do Pagamento:")
    valor_raw        = extrair_campo_linha(texto, "Valor Pago (R$):")

    if not all([beneficiario_raw, data_raw, valor_raw]):
        avisar_campos_faltando("Sicredi Boleto")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, beneficiario_raw.strip(), valor))
    return True


def handle_sicredi_pix(texto: str, caminho: Path):
    if "Comprovante de Pagamento Pix" not in texto:
        return False

    # Tenta com acento primeiro (formato real do Sicredi), depois sem
    destinatario_raw = extrair_campo_linha(texto, "Nome do destinatário:")
    if not destinatario_raw:
        destinatario_raw = extrair_campo_linha(texto, "Nome do destinatario:")

    data_raw  = extrair_campo_linha(texto, "Realizado em:")

    # Valor: ignora linha "Venc: ..." que também começa com "V"
    # Busca especificamente a linha que começa com "Valor: R$"
    valor_raw = None
    for linha in texto.splitlines():
        l = linha.strip()
        if l.lower().startswith("valor:"):
            valor_raw = l[len("Valor:"):].strip()
            break

    if not all([valor_raw, data_raw, destinatario_raw]):
        avisar_campos_faltando("Sicredi PIX")
        return True

    data         = limpar_data(data_raw)
    destinatario = limpar_nome_destinatario(destinatario_raw)
    valor        = limpar_valor_monetario(valor_raw)

    # Caso especial: quando o destinatário é LABFAR, inclui o nome do
    # devedor logo após "LABFAR" (antes do valor).
    if destinatario.strip().upper() == "LABFAR":
        devedor_raw = extrair_campo_linha(texto, "Nome do devedor:")
        if devedor_raw:
            devedor = limpar_nome_destinatario(devedor_raw)
            destinatario = f"{destinatario} {devedor}"

    renomear_pdf(caminho, montar_nome(data, destinatario, valor))
    return True


def handle_sicredi_debito_automatico(texto: str, caminho: Path):
    """
    Cobre comprovantes Sicredi do tipo:
      Comprovante de pagamento por débito automático
    Campos (layout de tabela — rótulo e valor na mesma linha):
      Empresa / Data de pagamento / Valor do débito automático
    """
    if "Comprovante de pagamento por débito automático" not in texto:
        return False

    empresa_raw = extrair_campo_linha(texto, "Empresa ")
    data_raw    = extrair_campo_linha(texto, "Data de pagamento ")
    valor_raw   = extrair_campo_linha(texto, "Valor do débito automático ")

    if not all([empresa_raw, data_raw, valor_raw]):
        avisar_campos_faltando("Sicredi Débito Automático")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, empresa_raw.strip(), valor))
    return True


def handle_sicredi_contas_consumo(texto: str, caminho: Path):
    """
    Cobre comprovantes Sicredi do tipo:
      Contas de Consumo  (água, luz, saneamento, etc.)
    Campos: Nome da Empresa / Data do Pagamento / Valor Total (R$)
    """
    if "Contas de Consumo" not in texto:
        return False

    empresa_raw = extrair_campo_linha(texto, "Nome da Empresa:")
    data_raw    = extrair_campo_linha(texto, "Data do Pagamento:")
    valor_raw   = extrair_campo_linha(texto, "Valor Total (R$):")

    if not all([empresa_raw, data_raw, valor_raw]):
        avisar_campos_faltando("Sicredi Contas de Consumo")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, empresa_raw.strip(), valor))
    return True


def handle_sicredi_folha(texto: str, caminho: Path):
    if "Folha de Pagamento" not in texto:
        return False

    favorecido_raw = extrair_campo_linha(texto, "Favorecido:")
    data_raw       = extrair_campo_linha(texto, "Data do Pagamento:")
    valor_raw      = extrair_campo_linha(texto, "Valor Total (R$):")

    if not all([favorecido_raw, data_raw, valor_raw]):
        avisar_campos_faltando("Sicredi Folha")
        return True

    data  = limpar_data(data_raw)
    valor = limpar_valor_monetario(valor_raw)

    renomear_pdf(caminho, montar_nome(data, favorecido_raw.strip(), valor))
    return True


# Mapa de bancos -> lista de handlers (ordem importa: testa um a um)
BANCOS = {
    "BB": [
        handle_bb_dda,
        handle_bb_folha,
        handle_bb_multa_transito,
        handle_bb_licenciamento,
        handle_bb_ipva,
        handle_bb_pagamento_titulos,
        handle_bb_boleto_convenio,
        handle_bb_pagamento_eletronico,
        handle_bb_pag_salario,
        handle_bb_pix,
    ],
    "Sicredi": [
        handle_sicredi_pix,
        handle_sicredi_debito_automatico,
        handle_sicredi_contas_consumo,
        handle_sicredi_boleto,
        handle_sicredi_folha,
    ],
}

BANCO_OPCOES = list(BANCOS.keys())


# ---------------------------------------------------------------------------
# Etapa 2 – Identificar tipo e renomear
# ---------------------------------------------------------------------------

def processar_renomeio(caminho: Path, banco: str):
    texto = extrair_texto(caminho)
    handlers = BANCOS.get(banco, [])

    for handler in handlers:
        if handler(texto, caminho):
            return

    print(f"   [AVISO] Nenhum tipo reconhecido para '{caminho.name}' no banco {banco}.")
    ESTATISTICAS["nao_reconhecidos"] += 1


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

def processar_arquivo(caminho_pdf: Path, pasta_saida: Path, banco: str):
    print(f"\n  Processando: {caminho_pdf.name}")
    arquivos = separar_paginas(caminho_pdf, pasta_saida)

    if len(arquivos) > 1:
        for arq in arquivos:
            processar_renomeio(arq, banco)
    else:
        processar_renomeio(arquivos[0], banco)


def main():
    print("=" * 50)
    print("   Processador de PDFs Bancários")
    print("=" * 50)

    # Step 1 – Escolha do banco
    print("\nBancos disponíveis:")
    for i, banco in enumerate(BANCO_OPCOES, start=1):
        print(f"  {i}. {banco}")

    while True:
        escolha = input("\nDigite o número do banco: ").strip()
        if escolha.isdigit() and 1 <= int(escolha) <= len(BANCO_OPCOES):
            banco = BANCO_OPCOES[int(escolha) - 1]
            break
        print("  Opção inválida. Tente novamente.")

    print(f"\nBanco selecionado: {banco}")

    # Entrada
    caminho_entrada = input("\nCaminho do arquivo PDF ou pasta com PDFs: ").strip().strip('"')
    caminho_entrada = Path(caminho_entrada)

    if not caminho_entrada.exists():
        print(f"\nErro: o caminho '{caminho_entrada}' não existe.")
        input("\nPressione ENTER para sair...")
        sys.exit(1)

    # Saída
    pasta_saida_str = input(
        "Pasta de saída para páginas separadas (ENTER = mesma pasta do arquivo): "
    ).strip().strip('"')

    if caminho_entrada.is_dir():
        pasta_padrao = caminho_entrada
        arquivos_pdf = sorted(caminho_entrada.glob("*.pdf"))
    else:
        pasta_padrao = caminho_entrada.parent
        arquivos_pdf = [caminho_entrada]

    pasta_saida = Path(pasta_saida_str) if pasta_saida_str else pasta_padrao
    pasta_saida.mkdir(parents=True, exist_ok=True)

    if not arquivos_pdf:
        print("Nenhum arquivo .pdf encontrado.")
        input("\nPressione ENTER para sair...")
        sys.exit(0)

    print(f"\nProcessando {len(arquivos_pdf)} arquivo(s)...")

    erros = []
    for pdf in arquivos_pdf:
        try:
            processar_arquivo(pdf, pasta_saida, banco)
        except Exception as e:
            print(f"  [ERRO] '{pdf.name}': {e}")
            ESTATISTICAS["erros"] += 1
            erros.append(pdf.name)

    # ------------------------------------------------------------------
    # Resumo final
    # ------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("RESUMO")
    print("=" * 50)
    print(f"PDF(s) de entrada processado(s)     : {len(arquivos_pdf)}")
    print(f"Arquivo(s) renomeado(s) com sucesso : {ESTATISTICAS['renomeados']}")
    print(f"Tipo não reconhecido                : {ESTATISTICAS['nao_reconhecidos']}")
    print(f"Campo(s) não encontrado(s)          : {ESTATISTICAS['campos_nao_encontrados']}")
    print(f"Erro(s) durante o processamento     : {ESTATISTICAS['erros']}")

    if erros:
        print(f"\n[!] PDF(s) de entrada com erro ({len(erros)}):")
        for nome in erros:
            print(f"   - {nome}")

    print("\nConcluído.")
    input("\nPressione ENTER para sair...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERRO INESPERADO] {e}")
        input("\nPressione ENTER para sair...")