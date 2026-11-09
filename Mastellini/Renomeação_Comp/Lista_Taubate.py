from pathlib import Path
import shutil

nomes = [
"Alessandra de Carvalho Sousa",
"Amanda Macedo Silva Alves da Cruz",
"Ana Julia do Nascimento Santos",
"Caroline de Oliveira Soares",
"Cláudio Henrique da Silva",
"Cristiane Canettieri Ferrari",
"Dara Mariane Conceição da Costa Reis",
"Dominyck Costa dos Santos Santana",
"Fernanda dos Santos",
"Gabriela Coelho Guimarães",
"Gabriela Messias kamischiro Quintiliano",
"Gabriely Caroline de Freitas Mello",
"Gidalia de Oliveira Lemes",
"Graziela Aparecida de Paula Cruz",
"Isabella da Cruz Nogueira",
"Jenifer Toledo Guarnieri",
"Jessica Natani Lemes Loreno",
"João Victor Silva Ferreira",
"Julia gabriele santos paiva",
"Julia saruba da silvia Savio",
"Juliana Barbosa Batista",
"Juliana Cristina Lemes de Oliveira",
"Kelly dos Reis Rosa de Oliveira",
"Lindomar dos Anjos Fonseca de Jesu",
"Luana Cristina Caetano",
"Luis Eduardo Delgado Santos",
"Maria Jose Gomes de Lima",
"Marlene Moreira de Mattos Moura",
"Nicole Vitoria da Silva Barbosa",
"Priscila Erika Borges Franca",
"Renata de Castro Santos",
"Rosileide Monteiro cordeiro",
"Silvia Helena de Paula",
"Tatiane Cristina de Oliveira"
]

def listar_arquivos(pasta: Path):
    destino = pasta / "Taubate"
    destino.mkdir(exist_ok=True)
    for arquivo in pasta.iterdir():
        if arquivo.suffix.lower() == ".pdf":
            for nome in nomes:
                if nome.upper() in arquivo.stem.upper():
                    print(f"Arquivo encontrado: {arquivo.name} | Nome correspondente: {nome}")
                    shutil.copy(arquivo, destino)

caminho = Path(input("Digite o caminho da pasta: "))
listar_arquivos(caminho)