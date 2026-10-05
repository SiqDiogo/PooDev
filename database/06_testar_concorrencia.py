"""Testes com duas conexões reais a PostgreSQL; usar somente a massa demonstrativa.

pip install 'psycopg[binary]>=3.2,<4'
Definir DATABASE_URL com a conexão local e executar este arquivo.
Os testes criam histórico; ao final cancelam reservas e devolvem chaves utilizadas.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from threading import Barrier

import psycopg


def conectar():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True,
                          options="-c search_path=gestao_lab,public -c lock_timeout=10000 -c statement_timeout=20000")


def competir(sql, parametros, codigo_esperado, nome, confirmados):
    barreira = Barrier(2)

    def executar(args):
        with conectar() as conn:
            with conn.transaction():
                barreira.wait(timeout=15)
                try:
                    registro = conn.execute(sql, args).fetchone()[0]
                    return {"estado": "CONFIRMADO", "id": registro}
                except psycopg.Error as erro:
                    # A exceção atravessa o bloco da transação e provoca rollback.
                    raise erro

    resultados = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(executar, args) for args in parametros]
        for futuro in futures:
            try:
                resultados.append(futuro.result(timeout=40))
            except psycopg.Error as erro:
                resultados.append({"estado": "REJEITADO", "sqlstate": erro.sqlstate})
    aprovados = [r for r in resultados if r["estado"] == "CONFIRMADO"]
    rejeitados = [r for r in resultados if r["estado"] == "REJEITADO"]
    confirmados.update(r["id"] for r in aprovados)
    if len(aprovados) != 1 or len(rejeitados) != 1 or rejeitados[0]["sqlstate"] != codigo_esperado:
        raise AssertionError(f"{nome}: resultado inesperado {resultados}")
    return {"teste": nome, "resultado": "PASSOU", "detalhes": resultados}, aprovados[0]["id"]


def main():
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("Defina DATABASE_URL para o banco de testes PostgreSQL.")
    resultados = []
    reservas = set()
    emprestimos = set()
    with conectar() as admin:
        demo = admin.execute("SELECT email FROM usuario WHERE id=1").fetchone()
        if demo != ("chefe.a@example.org",):
            raise SystemExit("Execute somente no banco carregado com 03_dados_exemplo.sql.")
        config_anterior = admin.execute("SELECT duracao_maxima_reserva,max_reservas_simultaneas FROM laboratorio WHERE id=1").fetchone()
        # Evita colisão com execuções anteriores e com os exemplos de datas fixas.
        inicio = datetime.now(timezone.utc) + timedelta(days=30)
        fim = inicio + timedelta(hours=1)
        try:
            with admin.transaction():
                admin.execute("SELECT contexto_operacao(1,'Configuração de teste de concorrência')")
                admin.execute("UPDATE laboratorio SET duracao_maxima_reserva=NULL,max_reservas_simultaneas=NULL WHERE id=1")
            resultado, rid = competir(
                "SELECT criar_reserva(%s,%s,%s,%s)",
                [(3, 304, inicio, fim), (4, 304, inicio, fim)], "23P01", "Mesmo equipamento: uma confirmação", reservas)
            resultados.append(resultado)
            reservas.add(rid)
            admin.execute("SELECT cancelar_reserva(1,%s,'Encerramento de teste de concorrência')", (rid,))
            reservas.remove(rid)

            # Duas reservas válidas distintas dão acesso à mesma sala.
            rid_a = admin.execute("SELECT criar_reserva(3,301,%s,%s)", (inicio, fim)).fetchone()[0]
            reservas.add(rid_a)
            rid_b = admin.execute("SELECT criar_reserva(4,302,%s,%s)", (inicio, fim)).fetchone()[0]
            reservas.add(rid_b)
            resultado, eid = competir(
                "SELECT retirar_chave(%s,%s,6,2)", [(3, rid_a), (4, rid_b)], "23505", "Mesma cópia: um empréstimo aberto", emprestimos)
            resultados.append(resultado)
            emprestimos.add(eid)
            admin.execute("SELECT devolver_chave(%s,2)", (eid,))
            emprestimos.remove(eid)
            for rid in (rid_a, rid_b):
                admin.execute("SELECT cancelar_reserva(1,%s,'Encerramento de teste de concorrência')", (rid,))
                reservas.remove(rid)

            with admin.transaction():
                admin.execute("SELECT contexto_operacao(1,'Limite de teste de concorrência')")
                admin.execute("UPDATE laboratorio SET max_reservas_simultaneas=1 WHERE id=1")
            resultado, rid = competir(
                "SELECT criar_reserva(3,%s,%s,%s)", [(301, inicio, fim), (302, inicio, fim)], "23514",
                "Recursos distintos: limite simultâneo do usuário respeitado", reservas)
            resultados.append(resultado)
            reservas.add(rid)
        finally:
            for eid in emprestimos:
                admin.execute("SELECT devolver_chave(%s,2)", (eid,))
            for rid in reservas:
                admin.execute("SELECT cancelar_reserva(1,%s,'Encerramento de teste de concorrência')", (rid,))
            with admin.transaction():
                admin.execute("SELECT contexto_operacao(1,'Restauração da configuração após testes')")
                admin.execute("UPDATE laboratorio SET duracao_maxima_reserva=%s,max_reservas_simultaneas=%s WHERE id=1",config_anterior)
    print(json.dumps(resultados, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
