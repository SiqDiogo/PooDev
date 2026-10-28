from types import SimpleNamespace
import pytest
from gestao_lab.dominio.usuarios import Perfil
from test_web import cliente

pytestmark = pytest.mark.integracao


def criar(sistema, token, recurso_id, inicio, fim):
    return SimpleNamespace(id=sistema.reservas.reservar(token, recurso_id=recurso_id, inicio=inicio, fim=fim))


def test_fluxo_completo_de_chaves_pela_interface_com_portador_e_ator_derivados(sistema, cliente, recursos, portador, periodo):
    usuario, token = portador
    reserva = criar(sistema, token, recursos[2].id, *periodo)
    cliente.entrar(sistema.chefe.email, sistema.senha)
    pagina = cliente.requisitar("/chaves/nova")
    assert pagina.status == 200
    dados = {"csrf": cliente.csrf(pagina), "codigo_copia": f'WEB-{sistema.chave}', "destino_id": recursos[0].id,
             "designada_para": usuario.id, "designada_por": usuario.id, "laboratorio_id": 999999}
    assert cliente.requisitar("/chaves/nova", dados).status == 303
    chave = sistema.chaves.painel(sistema.token)[0][0]
    pagina = cliente.requisitar(f'/chaves/retirar?id={chave.id}')
    assert pagina.status == 200 and usuario.nome in pagina.body and f'#{reserva.id}' in pagina.body
    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].estado == "DISPONIVEL"
    assert cliente.requisitar("/chaves/retirar", {"csrf": cliente.csrf(pagina), "chave_id": chave.id,
        "reserva_id": reserva.id, "usuario_id": sistema.chefe.id, "entregue_por": usuario.id}).status == 303
    emprestimo = sistema.chaves.painel(sistema.token)[2][0]
    assert emprestimo.usuario_id == usuario.id and emprestimo.entregue_nome == sistema.chefe.nome
    assert cliente.requisitar("/chaves").status == 200
    pagina = cliente.requisitar(f'/chaves/devolver?id={emprestimo.id}')
    assert pagina.status == 200 and "Confirmar recebimento físico" in pagina.body
    assert sistema.chaves.painel(sistema.token)[2][0].devolucao_em is None
    assert cliente.requisitar("/chaves/devolver", {"csrf": cliente.csrf(pagina), "emprestimo_id": emprestimo.id,
        "recebido_por": usuario.id, "devolucao_em": "2000-01-01"}).status == 303
    assert sistema.chaves.painel(sistema.token)[2][0].recebido_nome == sistema.chefe.nome
    pagina = cliente.requisitar("/historico")
    assert pagina.status == 200 and "Retirada de chave" in pagina.body and "Devolução de chave" in pagina.body

def test_designacao_e_ocorrencia_pelos_formularios_e_escape_do_historico(sistema, cliente, recursos, portador):
    usuario, _ = portador
    chave = sistema.chaves.cadastrar(sistema.token, codigo_copia=f'<b>WEB-{sistema.chave}</b>', destino_id=recursos[0].id)
    cliente.entrar(sistema.chefe.email, sistema.senha)
    pagina = cliente.requisitar(f'/chaves/designar?id={chave.id}')
    assert cliente.requisitar("/chaves/designar", {"csrf": cliente.csrf(pagina), "chave_id": chave.id, "designada_para": usuario.id}).status == 303
    pagina = cliente.requisitar(f'/chaves/ocorrencia?id={chave.id}')
    assert cliente.requisitar("/chaves/ocorrencia", {"csrf": cliente.csrf(pagina), "chave_id": chave.id,
        "condicao": "EXTRAVIADA", "descricao": "<script>ocorrencia</script>"}).status == 303
    pagina = cliente.requisitar("/historico")
    assert pagina.status == 200 and "Designação de chave" in pagina.body
    assert "&lt;script&gt;ocorrencia&lt;/script&gt;" in pagina.body and "<script>ocorrencia</script>" not in pagina.body
    assert f'<b>WEB-{sistema.chave}</b>' not in pagina.body

def test_professor_responsavel_pode_cadastrar_chave_mas_nao_gerenciar_outros_locais(sistema, cliente, recursos, dados_professor):
    professor = sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, dados_professor)
    cliente.entrar(sistema.chefe.email, sistema.senha)
    pagina = cliente.requisitar("/cadastros/sala")
    assert professor.nome in pagina.body
    assert cliente.requisitar("/cadastros/sala", {"csrf": cliente.csrf(pagina), "nome": "Sala do Professor", "identificacao": "PROF",
        "localizacao": "Bloco P", "capacidade": "5", "responsavel_id": professor.id}).status == 303
    sala = next(s for s in sistema.recursos.listar(sistema.token)[0] if s.identificacao == "PROF")
    chave_alheia = sistema.chaves.cadastrar(sistema.token, codigo_copia=f'ALHEIA-{sistema.chave}', destino_id=recursos[0].id)
    cliente.entrar(professor.email, sistema.senha)
    pagina = cliente.requisitar("/chaves/nova")
    assert pagina.status == 200 and 'Sala do Professor' in pagina.body
    assert cliente.requisitar("/chaves/nova", {"csrf": cliente.csrf(pagina), "codigo_copia": f'PROF-WEB-{sistema.chave}', "destino_id": sala.id}).status == 303
    for rota in ("designar", "retirar", "ocorrencia"):
        assert cliente.requisitar(f'/chaves/{rota}?id={chave_alheia.id}').status == 403
    assert cliente.requisitar("/cadastros/sala").status == 403

def test_aluno_consulta_chaves_e_recursos_sem_controles_administrativos(sistema, cliente, recursos, portador):
    usuario, _ = portador
    chave = sistema.chaves.cadastrar(sistema.token, codigo_copia=f'CONSULTA-{sistema.chave}', destino_id=recursos[0].id)
    cliente.entrar(usuario.email, sistema.senha)
    pagina = cliente.requisitar("/chaves")
    assert pagina.status == 200 and chave.codigo_copia in pagina.body
    assert 'href="/chaves/nova"' not in pagina.body and 'Registrar retirada' not in pagina.body
    pagina = cliente.requisitar("/recursos")
    assert pagina.status == 200 and "Posição 1" in pagina.body
    assert 'href="/cadastros/sala"' not in pagina.body and "Alterar localização" not in pagina.body
    assert cliente.requisitar("/chaves/nova").status == 403
    assert cliente.requisitar(f'/recursos/localizacao?id={recursos[2].id}').status == 403
    assert cliente.requisitar(f'/historico?usuario_id={sistema.chefe.id}').status == 403

def test_chaves_post_exige_csrf_e_ids_nao_podem_gerar_mudancas_por_get(sistema, cliente, recursos):
    cliente.entrar(sistema.chefe.email, sistema.senha)
    chave = sistema.chaves.cadastrar(sistema.token, codigo_copia=f'CSRF-{sistema.chave}', destino_id=recursos[0].id)
    for rota in ("nova", "designar", "retirar", "devolver", "ocorrencia"):
        assert cliente.requisitar(f'/chaves/{rota}', {"chave_id": chave.id}).status == 403
    assert cliente.requisitar(f'/chaves/designar?id={chave.id}&id={chave.id}').status == 400
    assert cliente.requisitar('/chaves/designar?id=999999999999999999999999').status == 400
    assert cliente.requisitar('/historico?recurso_id=1&recurso_id=2').status == 400
    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].estado == "DISPONIVEL"

def test_alteracao_de_localizacao_pela_interface_e_bloqueio_por_reserva(sistema, cliente, recursos, periodo):
    cliente.entrar(sistema.chefe.email, sistema.senha)
    pagina = cliente.requisitar(f'/recursos/localizacao?id={recursos[2].id}')
    assert pagina.status == 200
    dados = {"csrf": cliente.csrf(pagina), "equipamento_id": recursos[2].id,
        "bancada_id": recursos[1].id, "complemento_local": "Posição 4"}
    reserva = criar(sistema, sistema.token, recursos[2].id, *periodo)
    resposta = cliente.requisitar("/recursos/localizacao", dados)
    assert resposta.status == 400 and "reserva ativa ou futura" in resposta.body
    sistema.reservas.cancelar(sistema.token, reserva_id=reserva.id, motivo="Cancelamento de teste")
    assert cliente.requisitar("/recursos/localizacao", dados).status == 303
    assert "Posição 4" in cliente.requisitar("/recursos").body
    assert "Localização alterada" in cliente.requisitar("/historico").body
