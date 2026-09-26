import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente import interpretar_relato


ARQUIVO = RAIZ / "tests" / "casos_ia.json"


def main():
    casos = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    acertos_categoria = 0
    acertos_prioridade = 0
    acertos_emergencia = 0

    print("Avaliação local do agente de triagem\n")
    for caso in casos:
        resultado, meta = interpretar_relato(caso["relato"])
        ok_categoria = resultado["categoria"] == caso["categoria_esperada"]
        ok_prioridade = resultado["prioridade"] in caso["prioridades_aceitas"]
        ok_emergencia = bool(resultado["possivel_emergencia"]) == caso["emergencia_esperada"]
        acertos_categoria += int(ok_categoria)
        acertos_prioridade += int(ok_prioridade)
        acertos_emergencia += int(ok_emergencia)
        print(
            f"- {caso['nome']}: categoria={resultado['categoria']} "
            f"prioridade={resultado['prioridade']} emergencia={resultado['possivel_emergencia']} "
            f"[{'OK' if ok_categoria and ok_prioridade and ok_emergencia else 'REVISAR'}]"
        )

    total = len(casos)
    print("\nResumo")
    print(f"Categoria: {acertos_categoria}/{total}")
    print(f"Prioridade: {acertos_prioridade}/{total}")
    print(f"Emergência: {acertos_emergencia}/{total}")


if __name__ == "__main__":
    main()
